# coding=utf-8
import logging

from tweepy.streaming import StreamListener
from tweepy import OAuthHandler, Stream, API
from tweepy.utils import import_simplejson, parse_datetime
from tweepy.models import Model

json = import_simplejson()
import argparse
import cPickle as pickle
import datetime
import errno
import itertools
import os
import random

from textblob import TextBlob

from util import iflatmap, reverse_inits, OrderedSet


log = logging.getLogger('fewerror')

def looks_like_retweet(text):
    return "RT" in text or "MT" in text or text.startswith('"') or text.startswith(u'“')


def make_reply(text):
    """
    A generator of 0 or 1 replies to 'text' (without @username).
    """
    if looks_like_retweet(text):
        # We can't (reliably) figure out who to admonish so always skip these.
        return

    if 'less' not in text.lower():
        return

    if 'could care less' in text.lower():
        yield 'could care fewer'
        return

    blob = TextBlob(text)
    for q in iflatmap(find_an_indiscrete_quantity, blob.sentences):
        yield 'fewer ' + q
        break


class POS:
    """
    https://www.ling.upenn.edu/courses/Fall_2003/ling001/penn_treebank_pos.html
    http://www.surdeanu.info/mihai/teaching/ista555-fall13/readings/PennTreebankTagset.html
    """

    # 1. Coordinating conjunction
    CC = 'CC'

    # 2. Cardinal number
    CD = 'CD'

    # 3. Determiner
    DT = 'DT'

    # 4. Existential there
    EX = 'EX'

    # 5. Foreign word
    FW = 'FW'

    # 6. Preposition or subordinating conjunction
    IN = 'IN'

    # 7. Adjective or numeral, ordinal
    JJ = 'JJ'

    # 8. Adjective, comparative
    JJR = 'JJR'

    # 9. Adjective, superlative
    JJS = 'JJS'

    # 10. List item marker
    LS = 'LS'

    # 11. Modal
    MD = 'MD'

    # Unfortunately there is no POS tag for mass nouns specifically:
    # 12. Noun, singular or mass
    NN = 'NN'

    # 13. Noun, plural
    NNS = 'NNS'

    # 14. Proper noun, singular
    NNP = 'NNP'

    # 15. Proper noun, plural
    NNPS = 'NNPS'

    # 16. Predeterminer
    PDT = 'PDT'

    # 17. Possessive ending
    POS = 'POS'

    # 18. Personal pronoun
    PRP = 'PRP'

    # 19. Possessive pronoun
    PRP_ = 'PRP$'

    # 20. Adverb
    RB = 'RB'

    # 21. Adverb, comparative
    RBR = 'RBR'

    # 22. Adverb, superlative
    RBS = 'RBS'

    # 23. Particle
    RP = 'RP'

    # 24. Symbol
    SYM = 'SYM'

    # 25. to
    TO = 'TO'

    # 26. Interjection
    UH = 'UH'

    # 27. Verb, base form
    VB = 'VB'

    # 28. Verb, past tense
    VBD = 'VBD'

    # 29. Verb, gerund or present participle
    VBG = 'VBG'

    # 30. Verb, past participle
    VBN = 'VBN'

    # 31. Verb, non-3rd person singular present
    VBP = 'VBP'

    # 32. Verb, 3rd person singular present
    VBZ = 'VBZ'

    # 33. Wh-determiner
    WDT = 'WDT'

    # 34. Wh-pronoun
    WP = 'WP'

    # 35. Possessive wh-pronoun
    WP_ = 'WP$'

    # 36. Wh-adverb
    WRB = 'WRB'

    @staticmethod
    def nounish(word, pos):
        # nltk apparently defaults to 'NN' for smileys :) so special-case those
        return pos in (POS.NN, POS.NNS, POS.NNP, POS.NNPS) and \
            any(c.isalpha() for c in word)


def find_an_indiscrete_quantity(blob):
    tags_from_less = itertools.dropwhile((lambda (word, tag): word.lower() != 'less'),
                                         blob.tags)
    try:
        less, less_pos = next(tags_from_less)
        assert less.lower() == 'less'
    except StopIteration:
        return

    try:
        w, w_pos = next(tags_from_less)
    except StopIteration:
        return

    if w_pos not in (POS.JJ, POS.VBN, POS.NNP):
        return

    # Avoid replying "fewer lonely" to "less lonely girl"
    # FIXME: why? this is "right"! but it would be better to say "fewer lonely girl"
    # ... hmm
    # because "less happy sheep" -> "fewer happy sheep" is bad
    v, v_pos = next(tags_from_less, (None, None))
    if POS.nounish(v, v_pos):
        return

    yield w

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
    def __init__(self, olde=None):
        self.replied_to = getattr(olde, 'replied_to', {})
        self.last_time_for_word = getattr(olde, 'last_time_for_word', {})
        self.replied_to_user_and_word = getattr(olde, 'replied_to_user_and_word', {})

    def __str__(self):
        return '<State: {} replied_to, {} last_time_for_word, {} replied_to_user_and_word>'.format(
            len(self.replied_to), len(self.last_time_for_word), len(self.replied_to_user_and_word))


class LessListener(StreamListener):
    TIMEOUT = datetime.timedelta(seconds=120)
    PER_WORD_TIMEOUT = datetime.timedelta(seconds=60 * 60)
    HEARTBEAT_INTERVAL = 1
    HEARTS = [u'♥', u'💓']

    def __init__(self, *args, **kwargs):
        self.post_replies = kwargs.pop('post_replies', False)
        self.reply_to_rts = kwargs.pop('reply_to_rts', False)
        StreamListener.__init__(self, *args, **kwargs)
        self.last = datetime.datetime.now() - self.TIMEOUT
        self.me = self.api.me()

        self._state_filename = 'state.{}.pickle'.format(self.me.screen_name)
        self._load_state()
        log.info('%s: %s', self._state_filename, self._state)
        self._hb = 0

    def _load_state(self):
        try:
            with open(self._state_filename, 'rb') as f:
                self._state = State(olde=pickle.load(f))
        except IOError as e:
            if e.errno != errno.ENOENT:
                raise

            self._state = State()

            try:
                with open('state.json', 'r') as f:
                    obj = json.load(f)
                    self._state.replied_to = obj.get('replied_to', {})
                    self._save_state()
            except IOError as e:
                if e.errno != errno.ENOENT:
                    raise

    def _save_state(self):
        tmp = self._state_filename + '.tmp'
        with open(tmp, 'wb') as f:
            pickle.dump(self._state, f, protocol=pickle.HIGHEST_PROTOCOL)
        os.rename(tmp, self._state_filename)

    def on_connect(self):
        me = self.me
        log.info("streaming as @%s (#%d)", me.screen_name, me.id)

    def on_data(self, data):
        self._hb = (self._hb + 1) % self.HEARTBEAT_INTERVAL
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

        text = status.text.replace("&amp;", "&")
        screen_name = status.author.screen_name

        try:
            quantity = next(make_reply(text))
        except StopIteration:
            return
        except Exception:
            log.warning(u'exception while wrangling ‘%s’:', text, exc_info=True)
            return

        now = datetime.datetime.now()
        log.info("[%s@%s] %s", rt_log_prefix, screen_name, text)
        r_id = self._state.replied_to.get(status.id, None)
        if r_id is not None:
            log.info(u"…already replied: %d", r_id)
            return

        r_id = self._state.replied_to_user_and_word.get((screen_name, quantity.lower()), None)
        if r_id is not None:
            log.info(u"…already corrected @%s about '%s': %d", screen_name, quantity, r_id)
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

        to_mention.add(screen_name)
        for x in status.entities['user_mentions']:
            to_mention.add(x['screen_name'])

        to_mention.discard(self.me.screen_name)

        # Keep dropping mentions until the reply is short enough
        reply = None
        for mentions in reverse_inits([ u'@' + sn for sn in to_mention.keys() ]):
            reply = u'%s I think you mean “%s”.' % (u' '.join(mentions), quantity)
            if len(reply) <= 140:
                break

        if reply is not None and len(reply) <= 140:
            log.info('--> %s', reply)

            if self.post_replies:
                r = self.api.update_status(reply, in_reply_to_status_id=received_status.id)
                log.info("  https://twitter.com/_/status/%s", r.id)
                self.last = now
                self._state.replied_to[status.id] = r.id
                self._state.replied_to_user_and_word[(screen_name, quantity.lower())] = r.id

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
    parser.add_argument('--reply-to-retweets', action='store_true',
                        help='reply to retweets (makes the bot a little less opt-in)')

    parser.add_argument('--log',
                        metavar='FILE',
                        help='log activity to FILE')
    parser.add_argument('--log-level',
                        metavar='LEVEL',
                        default='INFO',
                        choices=('WARNING', 'INFO', 'DEBUG'),
                        help='default: INFO')

    args = parser.parse_args()

    logging.basicConfig(level=args.log_level,
                        format='%(asctime)s %(levelname)8s [%(name)s] %(message)s',
                        filename=args.log)

    consumer_key = os.environ["CONSUMER_KEY"]
    consumer_secret = os.environ["CONSUMER_SECRET"]

    access_token = os.environ["ACCESS_TOKEN"]
    access_token_secret = os.environ["ACCESS_TOKEN_SECRET"]

    auth = OAuthHandler(consumer_key, consumer_secret)
    auth.set_access_token(access_token, access_token_secret)

    api = API(auth)
    l = LessListener(api, post_replies=args.post_replies, reply_to_rts=args.reply_to_retweets)

    stream = Stream(auth, l)
    if args.use_public_stream:
        stream.filter(track=['less'])
    else:
        stream.userstream()
