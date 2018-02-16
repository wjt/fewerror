#!/usr/bin/env python3
import argparse
import logging
import os

import tweepy

from . import auth_from_env, batch, stream
from .. import checkedshirt

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

    batch.add_subcommands(subparsers, var)

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
