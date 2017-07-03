#!/usr/bin/env python3
import argparse
import os
import re
import textblob
import tracery
import yaml

from tracery.modifiers import base_english

SOURCE = os.path.join(os.path.dirname(__file__), 'thatsnotmybot.yaml')
traceryish_rx = re.compile(r'#(\w+)(?:\.\w+)*#')


def fmap(f, val):
    if isinstance(val, list):
        return [fmap(f, x) for x in val]
    else:
        return f(val)


def validate(j):
    used = {'origin', }
    for k, v in j.items():
        def _validate(val, k=k):
            for var in traceryish_rx.findall(val):
                if var not in j:
                    raise ValueError(k, val, var)
                used.add(var)
        fmap(_validate, v)

    unused = j.keys() - used
    if unused:
        raise ValueError(unused)


def modifier_is(noun_phrase):
    '''Extremely crude noun_phrase + {is,are} agreement.'''
    s = textblob.Sentence(noun_phrase)
    _, pos_tag = s.pos_tags[-1]
    verb = ' are' if pos_tag in ('NNS', 'NNPS') else ' is'
    return noun_phrase + verb


class ThatsNotMyBot(object):
    def __init__(self):
        with open(SOURCE, 'r', encoding='utf-8') as f:
            self.source = yaml.load(f, Loader=yaml.CLoader)

        validate(self.source)
        self.grammar = tracery.Grammar(self.source)
        self.grammar.add_modifiers(base_english)
        self.grammar.add_modifiers({'is': modifier_is})

    def sample(self, n):
        for _ in range(n):
            print(self.grammar.flatten('#origin#'))

    def tweet(self):
        raise ValueError('oh no')

    def normalize(self):
        with open(SOURCE, 'w', encoding='utf-8') as f:
            yaml.dump(self.source, f, Dumper=yaml.CDumper, indent=4, default_flow_style=False)

    def main(self, argv=None):
        p = argparse.ArgumentParser()
        s = p.add_subparsers()

        s.add_parser('validate',
                     help='Just validate the tracery source (default)')

        sample_parser = s.add_parser('sample', help='Print sample output')
        sample_parser.add_argument('n', type=int, nargs='?', default=5)
        sample_parser.set_defaults(cmd=lambda args: self.sample(args.n))

        tweet_parser = s.add_parser('tweet', help='toot toot motherfucker')
        tweet_parser.set_defaults(cmd=lambda args: self.tweet())

        normalize = s.add_parser('normalize', help='normalize YAML source')
        normalize.set_defaults(cmd=lambda args: self.normalize())

        args = p.parse_args(argv)
        if hasattr(args, 'cmd'):
            args.cmd(args)


if __name__ == '__main__':
    ThatsNotMyBot().main()
