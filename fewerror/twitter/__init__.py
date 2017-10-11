# coding=utf-8
import argparse
import enum
import json
import logging
import logging.config
import os
import random
import re
import time

import tweepy
from tweepy.streaming import StreamListener

from .. import checkedshirt, find_corrections, format_reply
from ..state import State
from ..util import reverse_inits, OrderedSet

log = logging.getLogger(__name__)


def get_sanitized_text(status):
    if hasattr(status, 'extended_tweet'):
        # https://dev.twitter.com/overview/api/upcoming-changes-to-tweets#compatibility-mode-json-rendering
        # Note that the field containing “The full set of entities” is helpfully
        # documented as “entities/extended_entities, etc.” We could use
        # display_text_range to strip leading usernames and trailing URLs but we
        # also want to remove internal entities.
        text = status.extended_tweet['full_text']
        for key in ('entities', 'extended_entities'):
            if key in status.extended_tweet:
                entities = status.extended_tweet[key]
                break
        else:
            raise ValueError("Can't find entities in extended_tweet", status._json)
    else:
        text = status.text
        entities = status.entities

    flat_entities = [
        e
        for k in ('media', 'urls', 'user_mentions')  # TODO: what about hashtags?
        if k in entities
        for e in entities[k]
    ]
    flat_entities.sort(key=lambda e: e['indices'], reverse=True)

    for e in flat_entities:
        i, j = e['indices']
        text = text[:i] + text[j:]

    text = text.replace("&amp;", "&")
    return text.strip()


manual_rt_rx = re.compile(r'''\b[RM]T\b''')
quote_rx = re.compile(r'''^['"‘“]''')


def looks_like_retweet(text):
    return manual_rt_rx.search(text)  # or quote_rx.match(text)


def user_url(user):
    return "https://twitter.com/{}".format(user.screen_name)


def status_url(status):
    return "{}/status/{}".format(user_url(status.author), status.id)


def lang_base(lang):
    base, *rest = lang.split('-')
    return base


class FMK(enum.Enum):
    '''Classification for new followers.'''
    FOLLOW_BACK = 1
    NEUTRAL = 2
    BLOCK = 3


def classify_user(api, whom, fetch_statuses=True):
    '''Crude attempt to identify spammy followers. It appears that this bot
    was used to boost follower counts since it always followed back.

    Returns an entry from FMK.'''
    label = '{} (#{})'.format(user_url(whom), whom.id)

    # Sorry if you speak these languages, but after getting several
    # thousand spam followers I needed a crude signal.
    forbidden_langs = {'ar', 'ja', 'tr', 'zh'}
    if lang_base(whom.lang) in forbidden_langs:
        log.info('%s has forbidden lang %s',
                 label, whom.lang)
        return FMK.BLOCK

    # Many spam users had user.lang == 'en' but tweet only in those languages.
    try:
        # "fully-hydrated" users have a status on them
        statuses = [whom.status]
    except AttributeError:
        # (if they're not protected...)
        if whom.protected:
            log.info('%s is protected; assume they are okay', label)
            return FMK.FOLLOW_BACK

        if whom.statuses_count == 0 and whom.followers_count > 1000:
            log.info('%s has never tweeted but has %d followers',
                     label, whom.followers_count)
            return FMK.BLOCK

        # but users in follow notifications do not; and nor do users who
        # haven't tweeted for a while (or ever)
        if fetch_statuses:
            # TODO: this fails for protected accounts who haven't accepted our request
            statuses = api.user_timeline(user_id=whom.id, count=20)
        else:
            log.info('%s: not enough information', label)
            return FMK.NEUTRAL

    langs = {lang_base(status.lang) for status in statuses}
    if langs & forbidden_langs:
        log.info('%s tweets in forbidden lang %s',
                 label, ', '.join(langs & forbidden_langs))
        return FMK.BLOCK

    if 'en' not in langs:
        log.info('%s tweets in %s, not en -- why are they following us?',
                 label, ', '.join(langs))
        return FMK.NEUTRAL

    return FMK.FOLLOW_BACK


class LessListener(StreamListener):
    def __init__(self, *args, **kwargs):
        state_dir = kwargs.pop('state_dir')
        self.post_replies = kwargs.pop('post_replies', False)
        self.gather = kwargs.pop('gather', None)
        StreamListener.__init__(self, *args, **kwargs)
        self.me = self.api.me()

        self._state = State.load(self.me.screen_name, state_dir)

        if self.gather:
            os.makedirs(self.gather, exist_ok=True)

    def on_connect(self):
        me = self.me
        log.info("streaming as @%s (#%d)", me.screen_name, me.id)

    def on_error(self, status_code):
        log.info("HTTP status %d", status_code)
        return True  # permit tweepy.Stream to retry

    december_greetings = (
        'Ho ho ho!',
        'Merry Christmas!',
        '🎅🎅🎅',
        '🎄🎄🎄',
    )
    festive_probability = 0.25

    def get_festive_probability(self, d):
        """Festivities increase linearly as crim cram approaches"""
        if d.month != 12 or d.day > 25:
            return 0

        x = (d.day - 1) / 24
        c = self.festive_probability
        m = 1 - c
        p = m * x + c
        log.info("%s -> %.2f", d, p)
        return p

    def get_festive_greeting(self, d):
        p = self.get_festive_probability(d)
        if random.random() < p:
            return random.choice(self.december_greetings)
        else:
            return ''

    def save_tweet(self, received_status):
        if not self.gather:
            return

        id_ = received_status.id_str
        id_bits = [
            id_[0:-16],
        ]
        dir_ = os.path.join(self.gather, *id_bits)
        os.makedirs(dir_, exist_ok=True)

        filename = os.path.join(dir_, '{}.json'.format(id_))
        with open(filename, 'w') as f:
            json.dump(obj=received_status._json, fp=f)

    def on_status(self, status):
        to_mention = OrderedSet()

        # Reply to the original when a tweet is RTed properly
        if hasattr(status, 'retweeted_status'):
            # Ignore real RTs
            return

        text = get_sanitized_text(status)
        if 'less' not in text.lower():
            return

        log.info("%s %s", status_url(status), text)

        self.save_tweet(status)

        if looks_like_retweet(text):
            log.info('…looks like a manual RT, skipping')
            return

        try:
            quantities = find_corrections(text)
        except Exception:
            log.exception(u'exception while wrangling ‘%s’:', text)
            return

        if not quantities:
            return

        if not self._state.can_reply(status.id, quantities):
            return

        to_mention.add(status.author.screen_name)
        for x in status.entities['user_mentions']:
            to_mention.add(x['screen_name'])

        mentioned_me = self.me.screen_name in to_mention
        to_mention.discard(self.me.screen_name)
        log.info('would like to mention %s', to_mention)

        for rel in self.api.lookup_friendships(screen_names=tuple(to_mention)):
            if not rel.is_followed_by:
                # If someone explicitly tags us, they're fair game
                is_author = rel.screen_name == status.author.screen_name
                if not (is_author and mentioned_me):
                    to_mention.discard(rel.screen_name)

                if rel.is_following:
                    log.info(u"%s no longer follows us; unfollowing", rel.screen_name)
                    self.api.destroy_friendship(screen_name=rel.screen_name)

        if status.author.screen_name not in to_mention:
            log.info('sender %s does not follow us (any more), not replying',
                     status.author.screen_name)
            return

        # Keep dropping mentions until the reply is short enough
        # TODO: hashtags?
        correction = format_reply(quantities)
        greeting = self.get_festive_greeting(status.created_at)
        reply = None
        for mentions in reverse_inits([u'@' + sn for sn in to_mention]):
            reply = u'{mentions} {correction}. {greeting}'.format(
                mentions=u' '.join(mentions),
                correction=correction,
                greeting=greeting).strip()
            if len(reply) <= 140:
                break

        if reply is not None and len(reply) <= 140:
            log.info('--> %s', reply)

            if self.post_replies:
                # TODO: I think tweepy commit f99b1da broke calling this without naming the status
                # parameter by adding media_ids before *args -- why do the tweepy tests pass?
                r = self.api.update_status(status=reply, in_reply_to_status_id=status.id)
                log.info("  %s", status_url(r))

                self._state.record_reply(status.id, quantities, r.id)
        else:
            log.info('too long, not replying')

    def on_event(self, event):
        if event.source.id == self.me.id:
            return

        if event.event == 'follow' and event.target.id == self.me.id:
            self.on_follow(event.source)

        if event.event == 'favorite' and event.target.id == self.me.id:
            log.info("tweet favorited by %s: %s",
                     user_url(event.source),
                     status_url(event.target_object))

    def on_follow(self, whom):
        log.info("followed by %s", user_url(whom))
        if whom.following:
            return

        classification = classify_user(self.api, whom)
        if classification == FMK.BLOCK:
            log.info('blocking %s', user_url(whom))
            self.block(whom.id)
        elif classification == FMK.FOLLOW_BACK:
            # TODO: delay this
            log.info("following %s back", user_url(whom))
            whom.follow()

    def block(self, user_id):
        self.api.create_block(user_id=user_id,
                              include_entities=False,
                              skip_status=True)


def auth_from_env():
    consumer_key = os.environ["CONSUMER_KEY"]
    consumer_secret = os.environ["CONSUMER_SECRET"]

    access_token = os.environ["ACCESS_TOKEN"]
    access_token_secret = os.environ["ACCESS_TOKEN_SECRET"]

    auth = tweepy.OAuthHandler(consumer_key, consumer_secret)
    auth.set_access_token(access_token, access_token_secret)

    return auth


def stream(api, args):
    while True:
        try:
            l = LessListener(api,
                             post_replies=args.post_replies,
                             gather=args.gather,
                             state_dir=args.state)

            stream = tweepy.Stream(api.auth, l)
            if args.use_public_stream:
                stream.filter(track=['less'])
            else:
                stream.userstream(replies='all')
        except tweepy.RateLimitError:
            log.warning("Rate-limited, and Tweepy didn't save us; time for a nap",
                        exc_info=True)
            time.sleep(15 * 60)


def save_user(user, directory):
    path = os.path.join(directory, 'user.{}.json'.format(user.id_str))
    with open(path, 'w') as f:
        json.dump(obj=user._json, fp=f)


def fetch_followers(api, args):
    '''Fetches all followers' JSON and saves them to the given directory.

    Files will have names of the form 'user.<numeric id>.json'.'''
    os.makedirs(args.directory, exist_ok=True)

    n = api.me().followers_count
    g = tweepy.Cursor(api.followers, count=200).items()

    for i, follower in enumerate(g, 1):
        log.info('[%d/%d] %s', i, n, follower.screen_name)
        save_user(follower, args.directory)


def classify(api, args):
    classes = {e: set() for e in FMK}
    for dirpath, _, filenames in os.walk(args.directory):
        for filename in filenames:
            if not re.match(r'user.\d+.json', filename):
                continue

            with open(os.path.join(dirpath, filename), 'rb') as f:
                j = json.load(f)

            user = tweepy.models.User.parse(api, j)
            c = classify_user(api, user, fetch_statuses=False)
            classes[c].add(user)

    for user in classes[FMK.BLOCK]:
        args.block_file.write('{}\n'.format(user.id))

    already_following = {u for u in classes[FMK.FOLLOW_BACK] if u.following}
    classes[FMK.FOLLOW_BACK] -= already_following

    results = {'already following': len(already_following)}
    for e, us in classes.items():
        results[e.name.lower().replace('_', ' ')] = len(us)

    w = max(map(len, results))
    v = max(len(str(n)) for n in results.values())
    for label, n in results.items():
        print('{:>{w}}: {:{v}} users'.format(label, n, w=w, v=v))


def report_spam(api, *args, **kwargs):
    sleep_time = 15 * 60

    for i in reversed(range(5)):
        try:
            return api.report_spam(*args, **kwargs)
        except tweepy.TweepError as e:
            if e.api_code == 205 and i > 0:
                # “You are over the limit for spam reports.  The account limit
                # for reporting spam has been reached. Try again later.”
                #
                # Annoyingly, this is a different error code to the normal
                # “rate-limited“ error code so tweepy's built-in rate limiting
                # doesn't apply.
                log.info("Over the spam-report limit; sleeping for %ds",
                         sleep_time, exc_info=True)
                time.sleep(sleep_time)
                sleep_time *= 1.5
            else:
                raise


def block(api, args):
    '''Unfollow, block, and optionally report as spam many user IDs.'''
    report = args.report

    to_block_ids = set(map(int, args.block_file))
    log.info('would like to unfollow block %d ids', len(to_block_ids))

    existing_block_ids = set(tweepy.Cursor(api.blocks_ids).items())
    log.info('%d existing blocks', len(existing_block_ids))
    # to_block_ids.difference_update(existing_block_ids)

    n = len(to_block_ids)
    for i, to_block_id in enumerate(to_block_ids, 1):
        try:
            if to_block_id in existing_block_ids:
                log.info('[%d/%d] #%d already blocked', i, n, to_block_id)
            elif report:
                log.info('[%d/%d] reporting #%d', i, n, to_block_id)
                u = report_spam(api, user_id=to_block_id, perform_block=True)
                log.info('reported and blocked %s (#%d)', user_url(u), to_block_id)
            else:
                log.info('[%d/%d] blocking #%d', i, n, to_block_id)
                u = api.create_block(user_id=to_block_id,
                                     include_entities=False,
                                     skip_status=True)
                log.info('blocked %s (#%d)', user_url(u), to_block_id)

            api.destroy_friendship(user_id=to_block_id)
            log.info('Unfollowed #%d', to_block_id)
        except tweepy.TweepError as e:
            if e.api_code in (
                34,  # reported by report_spam
                50,  # reported by create_block
            ):
                log.info('#%d no longer exists', to_block_id)
            else:
                raise

        if i < n and to_block_id not in existing_block_ids:
            # Experimentation suggests the limit is 50 spam reports per 30 minute window,
            # or 1 spam report per 36 seconds. Round up...
            time.sleep(45)


def main():
    var = os.path.abspath('var')

    parser = argparse.ArgumentParser()

    # Annoyingly you really do have to write
    #   python -m fewerror.twitter --log-level DEBUG stream
    # rather than
    #   python -m fewerror.twitter stream --log-level DEBUG
    # but life is too short.
    checkedshirt.add_arguments(parser)

    subparsers = parser.add_subparsers(help='subcommand', dest='mode')
    subparsers.required = True

    # stream
    stream_p = subparsers.add_parser('stream', help=u'annoy some tweeps')
    stream_p.set_defaults(func=stream)
    gather_dir = os.path.join(var, 'tweets')
    stream_p.add_argument('--gather', metavar='DIR', nargs='?',
                          const=gather_dir, default=None,
                          help='save matched tweets in DIR for later '
                               'degustation (default: {})'.format(gather_dir))
    stream_p.add_argument('--state', metavar='DIR', default=var,
                          help='store state in DIR (default: {})'.format(var))

    modes = stream_p.add_argument_group('stream mode').add_mutually_exclusive_group()
    modes.add_argument('--post-replies', action='store_true',
                       help='post (rate-limited) replies, rather than just printing them locally')
    modes.add_argument('--use-public-stream', action='store_true',
                       help='search public tweets for "less", rather than your own stream')

    # fetch-followers
    fetch_p = subparsers.add_parser('fetch-followers', help='fetch some tweeps',
                                    description=fetch_followers.__doc__)
    fetch_p.set_defaults(func=fetch_followers)
    default_fetch_directory = os.path.join(var, 'followers')
    fetch_p.add_argument('directory', default=default_fetch_directory,
                         help='(default: {})'.format(default_fetch_directory))

    # classify
    classify_p = subparsers.add_parser('classify', help='group some tweeps')
    classify_p.set_defaults(func=classify)
    classify_p.add_argument('directory', default=default_fetch_directory,
                            help='(default: {})'.format(default_fetch_directory))
    classify_p.add_argument('block_file', type=argparse.FileType('w'),
                            help='file to store one numeric user id per line, '
                                 'as used by "block" command')

    # block
    block_p = subparsers.add_parser('block', help='block some tweeps',
                                    description=block.__doc__)
    block_p.set_defaults(func=block)
    block_p.add_argument('block_file', type=argparse.FileType('r'),
                         help='file with one numeric user id per line')
    block_p.add_argument('--report', action='store_true',
                         help='with --block, also report for spam')

    args = parser.parse_args()
    checkedshirt.init(args)

    log.info('Initializing API')
    auth = auth_from_env()
    api = tweepy.API(
        auth,
        wait_on_rate_limit=True,
        wait_on_rate_limit_notify=True,
        # It looks like if retry_count is 0 (the default), wait_on_rate_limit=True will not
        # actually retry after a rate limit.
        retry_count=1)
    args.func(api, args)


if __name__ == '__main__':
    try:
        main()
    except SystemExit:
        raise
    except:
        log.info('oh no', exc_info=True)
        raise
