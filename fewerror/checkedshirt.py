import argparse
import json
import logging


def add_arguments(parser):
    g = parser.add_argument_group('logging')
    g.add_argument('--log-config',
                   type=argparse.FileType('r'),
                   metavar='FILE.json',
                   help='Read logging config from FILE.json (default: DEBUG to stdout)')


def init(args):
    if args.log_config:
        log_config = json.load(args.log_config)
        logging.config.dictConfig(log_config)
    else:
        logging.basicConfig(level='DEBUG',
                            format='%(asctime)s %(levelname)8s [%(name)s] %(message)s')
