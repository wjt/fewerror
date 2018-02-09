#!/usr/bin/env python3
import argparse
import logging
import os

import tweepy

from . import auth_from_env, stream
from .. import checkedshirt
from .batch import block, classify, fetch_followers, fetch_mutuals

log = logging.getLogger(__name__)


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

    # fetch-mutuals
    fetch_m = subparsers.add_parser('fetch-mutuals', help='intersect some tweeps',
                                    description=fetch_mutuals.__doc__)
    fetch_m.set_defaults(func=fetch_mutuals)
    fetch_m.add_argument('directory')
    fetch_m.add_argument('id', type=int)

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
    except KeyboardInterrupt:
        exit(1)
    except SystemExit:
        raise
    except Exception:
        log.info('oh no', exc_info=True)
        raise
