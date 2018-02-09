#!/usr/bin/env python3
# vim: tw=79
import argparse
import dotenv
import logging
import os
import subprocess
import tweepy

from . import checkedshirt

log = logging.getLogger(__name__)


def main():
    default_path = os.path.join(os.path.dirname(__file__),
                                '..',
                                '.env')
    default_path = os.path.abspath(default_path)

    parser = argparse.ArgumentParser(
        description='''
            Get OAuth tokens, using CONSUMER_KEY and CONSUMER_SECRET
            from env and writing the new ACCESS_TOKEN and
            ACCESS_TOKEN_SECRET back to it.''',
        epilog='''
            If env does not exist, but env.asc does, it will be decrypted with
            gpg2 to provide CONSUMER_KEY and CONSUMER_SECRET. If env already
            exists and contains ACCESS_TOKEN/ACCESS_TOKEN_SECRET, they will be
            preserved.''')
    parser.add_argument('env', nargs='?', default=default_path,
                        help='environment file to read and update '
                             '(default: {}'.format(default_path))
    checkedshirt.add_arguments(parser)

    args = parser.parse_args()
    checkedshirt.init(args)

    try:
        with open(args.env, 'x') as env_f:
            asc = args.env + '.asc'
            log.info("Populating %s from %s", args.env, asc)
            subprocess.call(('gpg2', '--decrypt', asc), stdout=env_f)
    except FileExistsError:
        pass

    dotenv.load_dotenv(args.env)
    consumer_key = os.environ["CONSUMER_KEY"]
    consumer_secret = os.environ["CONSUMER_SECRET"]
    ks = ('ACCESS_TOKEN', 'ACCESS_TOKEN_SECRET')
    if all(k in os.environ for k in ks):
        log.info('%s already contains %s', args.env, ' & '.join(ks))
        return

    auth = tweepy.OAuthHandler(consumer_key, consumer_secret)

    try:
        redirect_url = auth.get_authorization_url()
    except tweepy.TweepError:
        log.exception('Failed to get authorization URL')
        exit(1)

    print()
    print("Go to %s" % redirect_url)
    verifier = input('Verifier: ')
    print()

    try:
        access_token, access_token_secret = auth.get_access_token(verifier)
        dotenv.set_key(args.env, 'ACCESS_TOKEN', access_token)
        dotenv.set_key(args.env, 'ACCESS_TOKEN_SECRET', access_token_secret)
    except tweepy.TweepError:
        log.exception('Failed to get access token')
        exit(1)


if __name__ == '__main__':
    main()
