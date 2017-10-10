import argparse
import json
import logging
import os
import raven
from raven.handlers.logging import SentryHandler

log = logging.getLogger(__name__)


def add_arguments(parser):
    g = parser.add_argument_group('logging').add_mutually_exclusive_group()
    g.add_argument('--log-config',
                   type=argparse.FileType('r'),
                   metavar='FILE.json',
                   help='Read logging config from FILE.json (default: LEVEL to stderr)')
    g.add_argument('--log-level',
                   default='DEBUG',
                   help='Log at this level to stderr (default: DEBUG)')


def init(args):
    if args.log_config:
        log_config = json.load(args.log_config)
        logging.config.dictConfig(log_config)
    else:
        logging.basicConfig(level=args.log_level,
                            format='%(asctime)s %(levelname)8s [%(name)s] %(message)s')

    log.info('--- Starting ---')
    git_sha = raven.fetch_git_sha(os.path.dirname(os.path.dirname(__file__)))
    log.info('Git commit: %s', git_sha)

    # Log errors to Sentry
    client = raven.Client(
        # dsn=os.environ.get('SENTRY_DSN'),
        include_paths=['fewerror'],
        release=git_sha,
        ignore_exceptions=[
            KeyboardInterrupt,
        ],
    )
    handler = SentryHandler(client)
    handler.setLevel(logging.WARNING)
    raven.conf.setup_logging(handler)
