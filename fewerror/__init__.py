# coding=utf-8
import logging

from tweepy.streaming import StreamListener
from tweepy.utils import import_simplejson, parse_datetime
from tweepy.models import Model, Status, User, List

json = import_simplejson()
import itertools
import os
import random

from textblob import TextBlob
from nltk.corpus.reader import WordListCorpusReader

from .util import iflatmap, reverse_inits, OrderedSet, mkdir_p
from .state import State


log = logging.getLogger(__name__)


def looks_like_retweet(text):
    return "RT" in text or "MT" in text or text.startswith('"') or text.startswith(u'“')


def make_reply(text):
    """
    Returns a reply to 'text' (without @username) or None if there is none.
    """
    if looks_like_retweet(text):
        # We can't (reliably) figure out who to admonish so always skip these.
        return

    if 'less' not in text.lower():
        return

    if 'could care less' in text.lower():
        return 'could care fewer'

    blob = TextBlob(text)
    for q in iflatmap(find_an_indiscrete_quantity, blob.sentences):
        return 'fewer ' + q


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


mass_noun_corpora = WordListCorpusReader('wordlist/massnoun', r'[a-z]+')
mass_nouns = mass_noun_corpora.words()

QUANTITY_POS_TAGS = (POS.JJ, POS.VBN, POS.NN, POS.NNP, POS.RB, POS.RBR, POS.RBS)


def find_an_indiscrete_quantity(blob):
    tags_from_less = itertools.dropwhile((lambda word_tag: word_tag[0].lower() != 'less'),
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

    if w_pos not in QUANTITY_POS_TAGS and w not in mass_nouns:
        return

    for v, v_pos in tags_from_less:
        # Avoid replying "fewer lonely" to "less lonely girl"
        # why? this is "right"! but it would be better to say "fewer lonely girl"
        # but: "less happy sheep" -> "fewer happy sheep" is bad
        if POS.nounish(v, v_pos):
            return

        # if we reject "less happy sheep" we should also reject "less happy fluffy sheep".
        if v_pos not in (POS.JJ, POS.VBG):
            break

    yield w


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

        try:
            quantity = make_reply(text)
        except Exception:
            log.warning(u'exception while wrangling ‘%s’:', text, exc_info=True)
            return

        if quantity is None:
            return

        log.info("[%s@%s] %s", rt_log_prefix, screen_name, text)
        if not self._state.can_reply(status.id, quantity):
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
            reply = u'%s I think you mean “%s”.' % (u' '.join(mentions), quantity)
            if len(reply) <= 140:
                break

        if reply is not None and len(reply) <= 140:
            log.info('--> %s', reply)

            if self.post_replies:
                # TODO: I think tweepy commit f99b1da broke calling this without naming the status
                # parameter by adding media_ids before *args -- why do the tweepy tests pass?
                r = self.api.update_status(status=reply, in_reply_to_status_id=received_status.id)
                log.info("  https://twitter.com/_/status/%s", r.id)

                self._state.record_reply(status.id, quantity, r.id)
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
