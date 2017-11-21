#!/usr/bin/env python3
import argparse
import dotenv
import logging
import os
import tweepy

from . import checkedshirt

log = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(
        description='''Get OAuth tokens, using CONSUMER_KEY and
        CONSUMER_SECRET from ENV and writing the new ACCESS_TOKEN and
        ACCESS_TOKEN_SECRET back to it.''')
    parser.add_argument('env',
                        help='environment file to read and update')
    checkedshirt.add_arguments(parser)

    args = parser.parse_args()
    checkedshirt.init(args)

    dotenv.load_dotenv(args.env)
    consumer_key = os.environ["CONSUMER_KEY"]
    consumer_secret = os.environ["CONSUMER_SECRET"]
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
