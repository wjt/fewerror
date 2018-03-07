import argparse
import collections
import json
import random

from nltk.corpus import wordnet as wn

from google.cloud import vision, language


class Reply(collections.namedtuple('Reply', 'whole part adj')):
    def display(self, sense=False):
        if sense:
            template = "That's my {whole}! Its {part} is so {adj}."
        else:
            template = "That's not my {whole}! Its {part} is too {adj}."
        return template.format(**self._asdict())


MERONYM_KINDS = ('member_meronyms', 'part_meronyms', 'substance_meronyms')


def meronyms(synset):
    '''Fetches all kinds of (direct) meronyms for synset.'''
    return [
        meronym
        for kind in MERONYM_KINDS
        for meronym in getattr(synset, kind)()
    ]


def flatten(xs):
    # TODO: just a variation of breadth_first below
    if not isinstance(xs, list):
        raise TypeError

    def _flatten(obj, depth):
        if isinstance(obj, list):
            for y in obj:
                yield from _flatten(y, depth + 1)
        else:
            yield depth, obj

    return _flatten(xs, -1)


def breadth_first(treelist, max_depth=None):
    '''Flattens a Synset.tree() in breadth-first order, annotating each node with its depth.

    >>> breadth_first(['a'])
    [(0, 'a')]
    >>> breadth_first(['a', ['b', ['c']], ['d']])
    [(0, 'a'), (1, 'b'), (1, 'c'), (2, 'd')]
    >>> breadth_first(['a', ['b', ['c']], ['c']])
    [(0, 'a'), (1, 'b'), (1, 'c'), (2, 'c')]
    '''
    result = []
    queue = collections.deque()

    def push(depth, xs):
        queue.extend(((depth, x) for x in xs))

    push(0, treelist)
    while queue:
        depth, x = queue.popleft()
        if max_depth is not None and depth > max_depth:
            continue
        if isinstance(x, list):
            push(depth + 1, x)
        else:
            result.append((depth, x))
    return result


BARRIERS = {
    wn.synset('organism.n.01'),
    wn.synset('whole.n.02'),
}


def relevant_hypernyms(synset):
    return list(set(synset.hypernyms()) - BARRIERS)


def relative_meronyms(synset, relation=relevant_hypernyms):
    relatives = synset.tree(relation)
    seen = set()

    def is_stale(s):
        if s in seen:
            return True
        seen.add(s)
        return False

    for distance, relative in breadth_first(relatives):
        if is_stale(relative):
            continue

        for meronym in meronyms(relative):
            if is_stale(meronym):
                continue

            yield distance, relative, meronym, meronym.definition()
            # Could take hyponyms() of meronym but it yields increasingly stupid results.
            # for subdistance, submeronym in breadth_first(meronym.tree(Synset.hyponyms), 1):
            #     yield distance + subdistance, relative, meronym, submeronym


with open('/home/wjt/src/corpora/data/words/adjs.json') as f:
    ADJS = tuple(json.load(f)['adjs'])


def adjs_for(meronym):
    # TODO: not good enough in general.
    # In [184]: t.adjs_for(wn.synset('belly.n.05'))
    # Out[184]: frozenset({'certain', 'such'})
    # In [185]: wn.synset('belly.n.05').definition()
    # Out[185]: 'the underpart of the body of certain vertebrates such as snakes or fish'

    client = language.LanguageServiceClient()
    document = language.types.Document(
        content=meronym.definition(),
        type=language.enums.Document.Type.PLAIN_TEXT)
    tokens = client.analyze_syntax(document).tokens
    return frozenset({
        token.text.content
        for token in tokens
        if token.part_of_speech.tag == language.enums.PartOfSpeech.Tag.ADJ
    })


def replies_for_labels(labels):
    # Deduplicate synonyms, eg for https://twitter.com/wjjjjt/status/880118729052487681 we have
    # "goats" with score 0.9534318447113037 vs "goat" with score 0.9079196453094482
    # TODO: weight by label.score?
    label_synsets = []
    for label in labels:
        word = getattr(label, 'description', label)
        synsets = wn.synsets(word.replace(' ', '_'), pos=wn.NOUN)
        if synsets and synsets[0] not in label_synsets:
            label_synsets.append(synsets[0])

    for synset in label_synsets:
        for distance, relative, meronym, _ in relative_meronyms(synset):
            adj = random.choice(ADJS)
            yield Reply(synset.lemma_names()[0].replace('_', ' '),
                        meronym.lemma_names()[0].replace('_', ' '),
                        adj)


def main():
    client = vision.ImageAnnotatorClient()

    parser = argparse.ArgumentParser()
    parser.add_argument('image_file', type=argparse.FileType('rb'))
    args = parser.parse_args()

    content = args.image_file.read()
    image = vision.types.Image(content=content)

    response = client.label_detection(image=image)
    labels = response.label_annotations

    for reply in list(replies_for_labels(labels)):
        print(reply.display())


if __name__ == '__main__':
    main()
