# coding=utf-8
import logging

from textblob import TextBlob, Word
from nltk.corpus.reader import WordListCorpusReader

from .util import OrderedSet

log = logging.getLogger(__name__)


def furthermore(qs):
    if len(qs) > 1:
        return "{}, and furthermore {}".format(
            ", ".join(qs[:-1]),
            qs[-1]
        )
    else:
        return qs[0]


def format_reply(corrections):
    return "I think you mean " + furthermore(["“{}”".format(c) for c in corrections])


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

QUANTITY_POS_TAGS = frozenset((
    POS.JJ,
    POS.VBN,
    POS.VBP,
    POS.NN,
    POS.NNP,
    POS.RB,
    POS.RBR,
    POS.RBS,
))

bad_words_corpora = WordListCorpusReader('wordlist/shutterstock-bad-words', r'[a-z]{2,3}')
bad_words_en = bad_words_corpora.words('en')


def match(blob_tags, i):
    if ["could", "care", "less"] == [w.lower() for w, tag in blob_tags[i-2:i+1]]:
        return "could care fewer"

    if ["less", "than", "jake"] == [w.lower() for w, tag in blob_tags[i:i+3]]:
        return "Fewer Than Jake"

    reply_words = []

    if i > 0:
        v, v_pos = blob_tags[i - 1]
        if v_pos == POS.CD and not v.endswith('%'):
            # ignore "one less xxx" but allow "100% less xxx"
            return

        if i > 1:
            u, u_pos = blob_tags[i - 2]

            if u.lower() == 'more' and v.lower() == 'or':
                reply_words.extend([u, v])
            elif u.isdigit() and v == '%':
                reply_words.append(u + v)

        if not reply_words:
            if v_pos in (POS.RB, POS.DT):
                reply_words.append(v)

    less, _less_pos = blob_tags[i]
    if less.isupper():
        fewer = 'FEWER'
    elif less.istitle() and i != 0:
        fewer = 'Fewer'
    else:
        fewer = 'fewer'

    try:
        w, w_pos = blob_tags[i + 1]
    except IndexError:
        return

    if w_pos not in QUANTITY_POS_TAGS and w not in mass_nouns:
        return

    if not w.replace('/', '').isalpha():
        return

    for v, v_pos in blob_tags[i + 2:]:
        # Avoid replying "fewer lonely" to "less lonely girl"
        # why? this is "right"! but it would be better to say "fewer lonely girl"
        # but: "less happy sheep" -> "fewer happy sheep" is bad
        if POS.nounish(v, v_pos):
            return

        # less than 5 Seconds
        if v_pos in (POS.CD,):
            return

        # if we reject "less happy sheep" we should also reject "less happy fluffy sheep".
        if v_pos not in (POS.JJ, POS.VBG):
            break

    reply_words.extend([fewer, w])
    return ' '.join(reply_words)


def find_corrections(text):
    blob = TextBlob(text)

    words = OrderedSet()
    for s in blob.sentences:
        # blob.tags excludes punctuation, but we need that to avoid correcting
        # across a comma, ellipsis, etc. In fact, it's not clear there is
        # all that much point splitting into sentences…
        s_tags = [(Word(word, pos_tag=t), str(t))
                  for word, t in s.pos_tagger.tag(s.raw)]
        less_indices = [i for i, (word, tag) in enumerate(s_tags) if word.lower() == 'less']

        for i in less_indices:
            q = match(s_tags, i)
            if q is not None:
                words.add(q)

    words = list(words)
    for word in words:
        if any(w in word for w in bad_words_en):
            return []

    return words
