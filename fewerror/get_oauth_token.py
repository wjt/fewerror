#!/usr/bin/env python3
import argparse
import logging
import os
import tweepy

from . import checkedshirt

log = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(
        description='Get OAuth tokens. CONSUMER_KEY and CONSUMER_SECRET must '
                    'be set in the environment.')
    checkedshirt.add_arguments(parser)

    args = parser.parse_args()
    checkedshirt.init(args)

    consumer_key = os.environ["CONSUMER_KEY"]
    consumer_secret = os.environ["CONSUMER_SECRET"]
    auth = tweepy.OAuthHandler(consumer_key, consumer_secret)

    try:
        redirect_url = auth.get_authorization_url(access_type='write')
    except tweepy.TweepError:
        log.exception('Failed to get authorization URL')
        exit(1)

    print("Go to %s" % redirect_url)
    verifier = input('Verifier: ')

    try:
        access_token, access_token_secret = auth.get_access_token(verifier)
        print(u'CONSUMER_KEY=%s' % consumer_key)
        print(u'CONSUMER_SECRET=%s' % consumer_secret)
        print(u'ACCESS_TOKEN=%s' % access_token)
        print(u'ACCESS_TOKEN_SECRET=%s' % access_token_secret)
    except tweepy.TweepError:
        log.exception('Failed to get access token')
        exit(1)


if __name__ == '__main__':
    main()
