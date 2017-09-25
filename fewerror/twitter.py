# coding=utf-8
import argparse
import json
import logging
import logging.config
import os
import random
import re
import time

import tweepy
from tweepy.streaming import StreamListener

from . import checkedshirt, find_corrections, format_reply
from .state import State
from .util import reverse_inits, OrderedSet

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


class LessListener(StreamListener):
    def __init__(self, *args, **kwargs):
        self.post_replies = kwargs.pop('post_replies', False)
        self.gather = kwargs.pop('gather', None)
        StreamListener.__init__(self, *args, **kwargs)
        self.me = self.api.me()

        self._state = State.load(self.me.screen_name)

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

        # zh-cn => zh
        langs = {x.split('-')[0] for x in (whom.lang, whom.status.lang)}
        # Sorry if you speak these languages, but after getting several
        # thousand spam followers I needed a crude signal.
        forbidden_langs = {'ar', 'ja', 'zh'}
        oh_no = langs & forbidden_langs
        if oh_no:
            log.info("%s has bad lang %s; blocking",
                     user_url(whom), ', '.join(oh_no))
            self.api.create_block(user_id=whom.id,
                                  include_entities=False,
                                  skip_status=True)
        else:
            log.info("following %s back", user_url(whom))
            whom.follow()


def auth_from_env():
    consumer_key = os.environ["CONSUMER_KEY"]
    consumer_secret = os.environ["CONSUMER_SECRET"]

    access_token = os.environ["ACCESS_TOKEN"]
    access_token_secret = os.environ["ACCESS_TOKEN_SECRET"]

    auth = tweepy.OAuthHandler(consumer_key, consumer_secret)
    auth.set_access_token(access_token, access_token_secret)

    return auth


def stream(api, auth, args):
    while True:
        try:
            l = LessListener(api,
                             post_replies=args.post_replies,
                             gather=args.gather)

            stream = tweepy.Stream(auth, l)
            if args.use_public_stream:
                stream.filter(track=['less'])
            else:
                stream.userstream(replies='all')
        except tweepy.RateLimitError:
            log.warning("Rate-limited, and Tweepy didn't save us; time for a nap",
                        exc_info=True)
            time.sleep(15 * 60)


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


def mass_report(api, args):
    '''Block (and report as spam) many user IDs.'''
    report = args.report

    to_block_ids = set(map(int, args.block))
    log.info('would like to block %d ids', len(to_block_ids))

    existing_block_ids = set(tweepy.Cursor(api.blocks_ids).items())
    log.info('%d existing blocks', len(existing_block_ids))
    to_block_ids.difference_update(existing_block_ids)

    n = len(to_block_ids)
    for i, to_block_id in enumerate(to_block_ids, 1):
        if report:
            log.info('[%d/%d] reporting #%d', i, n, to_block_id)
            u = report_spam(api, user_id=to_block_id, perform_block=True)
            log.info('reported and blocked %s (#%d)', user_url(u), to_block_id)
        else:
            log.info('[%d/%d] blocking #%d', i, n, to_block_id)
            u = api.create_block(user_id=to_block_id,
                                 include_entities=False,
                                 skip_status=True)
            log.info('blocked %s (#%d)', user_url(u), to_block_id)

        if i < n:
            # Experimentation suggests the limit is 50 spam reports per 30 minute window,
            # or 1 spam report per 36 seconds. Round up...
            time.sleep(45)


def main():
    parser = argparse.ArgumentParser(description=u'annoy some tweeps')
    parser.add_argument('--gather', metavar='DIR', nargs='?', const='tweets', default=None,
                        help='save matched tweets in DIR for later degustation')

    modes = parser.add_mutually_exclusive_group()
    modes.add_argument('--post-replies', action='store_true',
                       help='post (rate-limited) replies, rather than just printing them locally')
    modes.add_argument('--use-public-stream', action='store_true',
                       help='search public tweets for "less", rather than your own stream')
    modes.add_argument('--block', metavar='ID_FILE', type=argparse.FileType('r'),
                       help='Block numeric user ids in ID_FILE (one per line)')

    parser.add_argument('--report', action='store_true',
                        help='with --block, also report for spam')

    checkedshirt.add_arguments(parser)

    args = parser.parse_args()

    checkedshirt.init(args)

    auth = auth_from_env()
    api = tweepy.API(
        auth,
        wait_on_rate_limit=True,
        wait_on_rate_limit_notify=True,
        # It looks like if retry_count is 0 (the default), wait_on_rate_limit=True will not
        # actually retry after a rate limit.
        retry_count=1)
    if args.block:
        mass_report(api, args)
    else:
        stream(api, auth, args)


if __name__ == '__main__':
    try:
        main()
    except SystemExit:
        raise
    except:
        log.exception('Bye :-(')
        raise
