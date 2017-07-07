#!/usr/bin/env python3
import argparse
import logging
import os
import re
import textblob
import tracery
import tweepy
import yaml

from tracery.modifiers import base_english

from fewerror.twitter import auth_from_env, status_url
from fewerror import checkedshirt

SOURCE = os.path.join(os.path.dirname(__file__), 'thatsnotmybot.yaml')
traceryish_rx = re.compile(r'#(\w+)(?:\.\w+)*#')

log = logging.getLogger(__name__)


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

    def generate(self):
        return self.grammar.flatten('#origin#')

    def sample(self, n):
        '''Print out n sample texts'''
        for _ in range(n):
            print(self.generate())

    def tweet(self, state_filename):
        '''🐦🐦🐦'''
        log.info('Loading state from %s', state_filename)
        try:
            with open(state_filename, 'r', encoding='utf-8') as f:
                state = yaml.load(f)
        except FileNotFoundError:
            state = {}

        try:
            object_ = state['object']
            last_id = state['last_id']
        except KeyError:
            object_ = self.grammar.flatten('#object#')
            last_id = None

        self.grammar.pop_rules('object')
        self.grammar.push_rules('object', object_)

        n = state.get('n', 0) + 1
        yes = n >= 8

        status = self.grammar.flatten('#{}#'.format('is' if yes else 'not'))
        log.info("Posting “%s”", status)
        if last_id is not None:
            log.info("  in reply to %s", last_id)

        auth = auth_from_env()
        api = tweepy.API(auth,
                         wait_on_rate_limit=True,
                         wait_on_rate_limit_notify=True,
                         retry_count=1)
        r = api.update_status(status, in_reply_to_status_id=last_id)
        log.info("Posted %s", status_url(r))

        if yes:
            state = {}
        else:
            state['object'] = object_
            state['last_id'] = r.id
            state['n'] = n
        log.info('Saving state to %s', state_filename)
        with open(state_filename, 'w', encoding='utf-8') as f:
            yaml.dump(state, f)

    def normalize(self):
        '''Write back the source. This would be more useful if I knew how to
        dump YAML in JSON style, and preserve comments.'''
        with open(SOURCE, 'w', encoding='utf-8') as f:
            yaml.dump(self.source, f, Dumper=yaml.CDumper,
                      indent=4, default_flow_style=False)

    def main(self, argv=None):
        p = argparse.ArgumentParser()
        checkedshirt.add_arguments(p)
        s = p.add_subparsers(title='commands')

        s.add_parser('validate',
                     help='Just validate the tracery source (default)')

        def add_argument(x, *args, **kwargs):
            kwargs['help'] += ' (default: {})'.format(kwargs['default'])
            return x.add_argument(*args, **kwargs)

        sample_parser = s.add_parser('sample', help=self.sample.__doc__)
        add_argument(sample_parser, 'n', type=int, nargs='?', default=5,
                     help='Number of sample texts')
        sample_parser.set_defaults(cmd=lambda args: self.sample(args.n))

        tweet_parser = s.add_parser('tweet', help=self.tweet.__doc__)
        add_argument(tweet_parser, '--state',
                     default=os.path.abspath('thatsnotmybot.state.yaml'),
                     help='Load and save state to STATE')
        tweet_parser.set_defaults(cmd=lambda args: self.tweet(args.state))

        normalize = s.add_parser('normalize', help=self.normalize.__doc__)
        normalize.set_defaults(cmd=lambda args: self.normalize())

        args = p.parse_args(argv)
        checkedshirt.init(args)
        if hasattr(args, 'cmd'):
            args.cmd(args)


if __name__ == '__main__':
    ThatsNotMyBot().main()
