# coding=utf-8
import argparse
import json
import logging
import os

from tweepy import OAuthHandler, Stream, API
from . import LessListener

log = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(
        description=u'annoy some tweeps',
        epilog=u'Note that --post-replies --use-public-stream will get you banned pretty quickly')
    parser.add_argument('--post-replies', action='store_true',
                        help='post (rate-limited) replies, rather than just printing them locally')
    parser.add_argument('--gather', metavar='DIR', nargs='?', const='tweets', default=None,
                        help='save matched tweets in DIR for later degustation')
    parser.add_argument('--use-public-stream', action='store_true',
                        help='search public tweets for "less", rather than your own stream')
    parser.add_argument('--reply-to-retweets', action='store_true',
                        help='reply to retweets (makes the bot a little less opt-in)')
    parser.add_argument('--follow-on-favs', action='store_true',
                        help='follow people who fav us (makes the bot a little less opt-in)')
    parser.add_argument('--heartbeat-interval', type=int, default=500)

    parser.add_argument('--log-config',
                        type=argparse.FileType('r'),
                        metavar='FILE.json',
                        help='Read logging config from FILE.json (default: DEBUG to stdout)')

    args = parser.parse_args()

    if args.log_config:
        log_config = json.load(args.log_config)
        logging.config.dictConfig(log_config)
    else:
        logging.basicConfig(level='DEBUG',
                            format='%(asctime)s %(levelname)8s [%(name)s] %(message)s')

    consumer_key = os.environ["CONSUMER_KEY"]
    consumer_secret = os.environ["CONSUMER_SECRET"]

    access_token = os.environ["ACCESS_TOKEN"]
    access_token_secret = os.environ["ACCESS_TOKEN_SECRET"]

    auth = OAuthHandler(consumer_key, consumer_secret)
    auth.set_access_token(access_token, access_token_secret)

    api = API(auth)
    l = LessListener(api, post_replies=args.post_replies, reply_to_rts=args.reply_to_retweets,
                     follow_on_favs=args.follow_on_favs,
                     heartbeat_interval=args.heartbeat_interval, gather=args.gather)

    stream = Stream(auth, l)
    if args.use_public_stream:
        stream.filter(track=['less'])
    else:
        stream.userstream()

if __name__ == '__main__':
    try:
        main()
    except SystemExit:
        raise
    except:
        log.error('Bye :-(', exc_info=True)
        raise
