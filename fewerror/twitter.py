# coding=utf-8
import argparse
import logging
import logging.config
import os
import random
import time

from tweepy import OAuthHandler, Stream, API, RateLimitError
from tweepy.streaming import StreamListener
from tweepy.utils import import_simplejson, parse_datetime
from tweepy.models import Model, Status, User, List

json = import_simplejson()
log = logging.getLogger(__name__)

from . import find_corrections, format_reply
from .state import State
from .util import reverse_inits, OrderedSet, mkdir_p


class Event(Model):
    """https://dev.twitter.com/streaming/overview/messages-types#Events_event

    TODO: upstream this. Currently you get a Status object.
    """

    @classmethod
    def parse(cls, api, json):
        event = cls(api)
        event_name = json['event']
        user_model = getattr(api.parser.model_factory, 'user') if api else User
        status_model = getattr(api.parser.model_factory, 'status') if api else Status
        list_model = getattr(api.parser.model_factory, 'list') if api else List

        for k, v in json.items():
            if k == 'target':
                user = user_model.parse(api, v)
                setattr(event, 'target', user)
            elif k == 'source':
                user = user_model.parse(api, v)
                setattr(event, 'source', user)
            elif k == 'created_at':
                setattr(event, k, parse_datetime(v))
            elif k == 'target_object':
                if event_name in ('favorite', 'unfavorite'):
                    status = status_model.parse(api, v)
                    setattr(event, 'target_object', status)
                elif event_name.startswith('list_'):
                    list_ = list_model.parse(api, v)
                    setattr(event, 'target_object', list_)
                else:
                    # at the time of writing, the only other event defined to have a non-null
                    # target_object is 'access_revoked', defined to be a 'client'. I don't have one
                    # of those to hand.
                    setattr(event, 'target_object', v)
            elif k == 'event':
                setattr(event, 'event', v)
            else:
                setattr(event, k, v)
        return event


def get_sanitized_text(status):
    text = status.text

    flat_entities = [
        e
        for k in ('media', 'urls')  # TODO: what about hashtags?
        if k in status.entities
        for e in status.entities[k]
    ]
    flat_entities.sort(key=lambda e: e['indices'], reverse=True)

    for e in flat_entities:
        i, j = e['indices']
        text = text[:i] + text[j:]

    text = text.replace("&amp;", "&")
    return text.strip()


def looks_like_retweet(text):
    return "RT" in text or "MT" in text or text.startswith('"') or text.startswith(u'“')


class LessListener(StreamListener):
    HEARTS = [u'♥', u'💓']

    def __init__(self, *args, **kwargs):
        self.post_replies = kwargs.pop('post_replies', False)
        self.reply_to_rts = kwargs.pop('reply_to_rts', False)
        self.follow_on_favs = kwargs.pop('follow_on_favs', False)
        self.heartbeat_interval = kwargs.pop('heartbeat_interval', 500)
        self.gather = kwargs.pop('gather', None)
        StreamListener.__init__(self, *args, **kwargs)
        self.me = self.api.me()

        self._state = State.load(self.me.screen_name)
        self._hb = 0

        if self.gather:
            mkdir_p(self.gather)

    def on_connect(self):
        me = self.me
        log.info("streaming as @%s (#%d)", me.screen_name, me.id)

    def on_error(self, status_code):
        log.info("HTTP status %d", status_code)
        return True  # permit tweepy.Stream to retry

    def on_data(self, data):
        self._hb = (self._hb + 1) % self.heartbeat_interval
        if self._hb == 0:
            log.info(random.choice(self.HEARTS))

        message = json.loads(data)
        if message.get('event') is not None:
            event = Event.parse(self.api, message)
            self.on_event(event)
        else:
            super(LessListener, self).on_data(data)

    def on_status(self, received_status):
        to_mention = OrderedSet()

        # Reply to the original when a tweet is RTed properly
        if hasattr(received_status, 'retweeted_status'):
            if not self.reply_to_rts:
                return

            status = received_status.retweeted_status
            rt_log_prefix = '@%s RT ' % received_status.author.screen_name
            to_mention.add(received_status.author.screen_name)
        else:
            status = received_status
            rt_log_prefix = ''

            # Don't log RTs, no point in getting a million duplicates in the corpus.
        if self.gather and 'less' in status.text:
            filename = os.path.join(self.gather, '{}.json'.format(received_status.id))
            with open(filename, 'w') as f:
                json.dump(obj=received_status._json, fp=f)

        text = get_sanitized_text(status)
        screen_name = status.author.screen_name

        if looks_like_retweet(text):
            # We can't (reliably) figure out who to admonish so always skip these.
            return

        try:
            quantities = find_corrections(text)
        except Exception:
            log.warning(u'exception while wrangling ‘%s’:', text, exc_info=True)
            return

        if not quantities:
            return

        log.info("[%s@%s] %s", rt_log_prefix, screen_name, text)
        if not self._state.can_reply(status.id, quantities):
            return

        to_mention.add(screen_name)
        for x in status.entities['user_mentions']:
            to_mention.add(x['screen_name'])

        to_mention.discard(self.me.screen_name)
        for rel in self.api.lookup_friendships(screen_names=tuple(to_mention)):
            if not rel.is_followed_by:
                to_mention.discard(rel.screen_name)

                if rel.is_following:
                    log.info(u"%s no longer follows us; unfollowing", rel.screen_name)
                    self.api.destroy_friendship(user_id=rel.id)

        if not to_mention:
            log.info('no-one who follows us to reply to')
            return

        # Keep dropping mentions until the reply is short enough
        # TODO: hashtags?
        reply = None
        for mentions in reverse_inits([u'@' + sn for sn in to_mention]):
            reply = u'%s %s.' % (u' '.join(mentions), format_reply(quantities))
            if len(reply) <= 140:
                break

        if reply is not None and len(reply) <= 140:
            log.info('--> %s', reply)

            if self.post_replies:
                # TODO: I think tweepy commit f99b1da broke calling this without naming the status
                # parameter by adding media_ids before *args -- why do the tweepy tests pass?
                r = self.api.update_status(status=reply, in_reply_to_status_id=received_status.id)
                log.info("  https://twitter.com/_/status/%s", r.id)

                self._state.record_reply(status.id, quantities, r.id)
        else:
            log.info('too long, not replying')

    def on_event(self, event):
        if event.source.id == self.me.id:
            return

        if event.event == 'follow' and event.target.id == self.me.id:
            log.info("followed by @%s", event.source.screen_name)
            self.maybe_follow(event.source)

        if self.follow_on_favs:
            if event.event == 'favorite' and event.target.id == self.me.id:
                log.info("tweet favorited by @%s", event.source.screen_name)
                self.maybe_follow(event.source)

    def maybe_follow(self, whom):
        if not whom.following:
            log.info("... following back")
            whom.follow()


def auth_from_env():
    consumer_key = os.environ["CONSUMER_KEY"]
    consumer_secret = os.environ["CONSUMER_SECRET"]

    access_token = os.environ["ACCESS_TOKEN"]
    access_token_secret = os.environ["ACCESS_TOKEN_SECRET"]

    auth = OAuthHandler(consumer_key, consumer_secret)
    auth.set_access_token(access_token, access_token_secret)

    return auth


def main():
    parser = argparse.ArgumentParser(
        description=u'annoy some tweeps',
        epilog=u'Note that --post-replies --use-public-stream will get you banned pretty quickly')
    parser.add_argument('--post-replies', action='store_true',
                        help='post (rate-limited) replies, rather than just printing them locally')
    parser.add_argument('--gather', metavar='DIR', nargs='?', const='tweets', default=None,
                        help='save matched tweets in DIR for later degustation')
    parser.add_argument('--use-public-stream', action='store_true',
                        help='search public tweets for "less", rather than your own stream')
    parser.add_argument('--reply-to-retweets', action='store_true',
                        help='reply to retweets (makes the bot a little less opt-in)')
    parser.add_argument('--follow-on-favs', action='store_true',
                        help='follow people who fav us (makes the bot a little less opt-in)')
    parser.add_argument('--heartbeat-interval', type=int, default=500)

    parser.add_argument('--log-config',
                        type=argparse.FileType('r'),
                        metavar='FILE.json',
                        help='Read logging config from FILE.json (default: DEBUG to stdout)')

    args = parser.parse_args()

    if args.log_config:
        log_config = json.load(args.log_config)
        logging.config.dictConfig(log_config)
    else:
        logging.basicConfig(level='DEBUG',
                            format='%(asctime)s %(levelname)8s [%(name)s] %(message)s')

    auth = auth_from_env()
    api = API(auth,
              wait_on_rate_limit=True,
              wait_on_rate_limit_notify=True,
              # It looks like if retry_count is 0 (the default), wait_on_rate_limit=True will not
              # actually retry after a rate limit.
              retry_count=1)
    while True:
        try:
            l = LessListener(api,
                             post_replies=args.post_replies,
                             reply_to_rts=args.reply_to_retweets,
                             follow_on_favs=args.follow_on_favs,
                             heartbeat_interval=args.heartbeat_interval,
                             gather=args.gather)

            stream = Stream(auth, l)
            if args.use_public_stream:
                stream.filter(track=['less'])
            else:
                stream.userstream(replies='all')
        except RateLimitError:
            log.warning("Rate-limited, and Tweepy didn't save us; time for a nap",
                        exc_info=True)
            time.sleep(15 * 60)


if __name__ == '__main__':
    try:
        main()
    except SystemExit:
        raise
    except:
        log.error('Bye :-(', exc_info=True)
        raise
