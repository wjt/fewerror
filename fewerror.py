# coding=utf-8
import logging

from tweepy.streaming import StreamListener
from tweepy import OAuthHandler, Stream, API
from tweepy.utils import import_simplejson, parse_datetime
from tweepy.models import Model

json = import_simplejson()
import argparse
import cPickle as pickle
import os
import sys
import itertools
import datetime
import tempfile
import errno

from textblob import TextBlob

import dateutil.parser

log = logging

def looks_like_retweet(text):
    return "RT" in text or "MT" in text or text.startswith('"') or text.startswith(u'“')


class FewerLess(Exception):
    """'less' is not in the tweet"""
    pass


def make_reply(text):
    """
    Returns a reply to 'text' (without @username), or None if the 'less' might
    not be correct. Raises FewerLess if 'text' doesn't contain 'less'.
    """
    if looks_like_retweet(text):
        # We can't (reliably) figure out who to admonish so always skip these.
        raise FewerLess()

    blob = TextBlob(text)
    for sentenceish in blob.sentences:
        try:
            q = find_an_indiscrete_quantity(sentenceish)
            if q is not None:
                return q
        except FewerLess:
            pass

    raise FewerLess()


class POS:
    # adjective or numeral, ordinal
    JJ = 'JJ'

    # verb, past participle
    VBN = 'VBN'

    # noun, proper, singular
    NNP = 'NNP'

    # Unfortunately there is no POS tag for mass nouns specifically:
    # noun, singular or mass
    NN = 'NN'


def find_an_indiscrete_quantity(blob):
    tags_from_less = itertools.dropwhile((lambda (word, tag): word.lower() != 'less'),
                                         blob.tags)
    try:
        less = next(tags_from_less)
    except StopIteration:
        raise FewerLess()

    try:
        w, w_pos = next(tags_from_less)
    except StopIteration:
        return None

    if w_pos not in (POS.JJ, POS.VBN, POS.NNP):
        return None

    # Avoid replying "fewer lonely" to "less lonely girl"
    # but nltk apparently defaults to 'NN' for smileys :) so special-case those
    v, v_pos = next(tags_from_less, (None, None))
    if v_pos == 'NN' and any(c.isalpha() for c in v):
        return None

    return w

class Event(Model):
    @classmethod
    def parse(cls, api, json):
        event = cls(api)
        for k, v in json.items():
            if k == 'target':
                user_model = getattr(api.parser.model_factory, 'user')
                user = user_model.parse(api, v)
                setattr(event, 'target', user)
            elif k == 'source':
                user_model = getattr(api.parser.model_factory, 'user')
                user = user_model.parse(api, v)
                setattr(event, 'source', user)
            elif k == 'created_at':
                setattr(event, k, parse_datetime(v))
            elif k == 'target_object':
                setattr(event, 'target_object', v)
            elif k == 'event':
                setattr(event, 'event', v)
            else:
                setattr(event, k, v)
        return event


class State(object):
    def __init__(self):
        self.replied_to = {}
        self.last_time_for_word = {}


class LessListener(StreamListener):
    TIMEOUT = datetime.timedelta(seconds=120)
    PER_WORD_TIMEOUT = datetime.timedelta(seconds=60 * 60)

    STATE_FILENAME = 'state.pickle'

    def __init__(self, *args, **kwargs):
        self.post_replies = kwargs.pop('post_replies', False)
        StreamListener.__init__(self, *args, **kwargs)
        self.last = datetime.datetime.now() - self.TIMEOUT
        self.me = self.api.me()

        self._load_state()

    def _load_state(self):
        try:
            with open(self.STATE_FILENAME, 'rb') as f:
                self._state = pickle.load(f)
        except IOError as e:
            if e.errno != errno.ENOENT:
                raise

            self._state = State()

            try:
                with open('state.json', 'r') as f:
                    obj = json.load(f)
                    self._state.replied_to = obj.get('replied_to', {})
            except IOError as e:
                if e.errno != errno.ENOENT:
                    raise

    def _save_state(self):
        with open(self.STATE_FILENAME + '.tmp', 'wb') as f:
            pickle.dump(self._state, f, protocol=pickle.HIGHEST_PROTOCOL)
        os.rename(self.STATE_FILENAME + '.tmp', self.STATE_FILENAME)

    def on_connect(self):
        me = self.me
        log.info("streaming as @%s (#%d)", me.screen_name, me.id)

    def on_data(self, data):
        message = json.loads(data)
        if message.get('event') is not None:
            event = Event.parse(self.api, message)
            self.on_event(event)
        else:
            super(LessListener, self).on_data(data)

    def on_status(self, received_status):
        # Reply to the original when a tweet is RTed properly
        status = getattr(received_status, 'retweeted_status', received_status)

        text = status.text.replace("&amp;", "&")
        screen_name = status.author.screen_name

        try:
            quantity = make_reply(text)
        except FewerLess:
            return
        except Exception:
            log.warning(u'exception while wrangling ‘%s’:', text, exc_info=True)
            raise

        if status == received_status:
            rt_log_prefix = ''
        else:
            rt_log_prefix = '@%s RT ' % received_status.author.screen_name

        now = datetime.datetime.now()
        log.info("[%s@%s] %s", rt_log_prefix, screen_name, text)
        r_id = self._state.replied_to.get(status.id, None)
        if r_id is not None:
            log.info(u"…already replied: %d", r_id)
            return

        last_for_this = self._state.last_time_for_word.get(quantity.lower(), None)
        if last_for_this and now - last_for_this < self.PER_WORD_TIMEOUT:
            log.info(u"…corrected '%s' at %s, waiting till %s", quantity, last_for_this,
                     last_for_this + self.PER_WORD_TIMEOUT)
            return

        if self.post_replies and now - self.last < self.TIMEOUT:
            log.info(u"rate-limiting until %s…", self.last + self.TIMEOUT)
            return

        if quantity is None:
            return

        reply = u'@%s I think you mean “fewer %s”.' % (screen_name, quantity)

        if len(reply) <= 140:
            log.info('--> %s', reply)

            if self.post_replies:
                r = self.api.update_status(reply, in_reply_to_status_id=status.id)
                log.info("  https://twitter.com/_/status/%s", r.id)
                self.last = now
                self._state.replied_to[status.id] = r.id

            self._state.last_time_for_word[quantity.lower()] = now
            self._save_state()
        else:
            log.info('too long, not replying')

    def on_event(self, event):
        if event.event == 'follow' and event.target.id == self.me.id:
            log.info("followed by @%s", event.source.screen_name)
            self.maybe_follow(event.source)

        if event.event == 'favorite' and event.target.id == self.me.id:
            log.info("tweet favorited by @%s", event.source.screen_name)
            self.maybe_follow(event.source)

    def maybe_follow(self, whom):
        if not whom.following:
            log.info("... following back")
            whom.follow()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=u'annoy some tweeps',
                                     epilog='Note that --post-replies --use-public-stream will get you banned pretty quickly')
    parser.add_argument('--post-replies', action='store_true',
                        help='post (rate-limited) replies, rather than just printing them locally')
    parser.add_argument('--use-public-stream', action='store_true',
                        help='search public tweets for "less", rather than your own stream')
    parser.add_argument('--log',
                        metavar='FILE',
                        help='log activity to FILE')

    args = parser.parse_args()

    logging.basicConfig(level=logging.DEBUG,
                        format='%(asctime)s %(message)s',
                        filename=args.log)

    consumer_key = os.environ["CONSUMER_KEY"]
    consumer_secret = os.environ["CONSUMER_SECRET"]

    access_token = os.environ["ACCESS_TOKEN"]
    access_token_secret = os.environ["ACCESS_TOKEN_SECRET"]

    auth = OAuthHandler(consumer_key, consumer_secret)
    auth.set_access_token(access_token, access_token_secret)

    api = API(auth)
    l = LessListener(api, post_replies=args.post_replies)

    stream = Stream(auth, l)
    if args.use_public_stream:
        stream.filter(track=['less'])
    else:
        stream.userstream()
