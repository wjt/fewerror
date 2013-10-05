# coding=utf-8
from tweepy.streaming import StreamListener
from tweepy import OAuthHandler, Stream, API
import argparse
import os
import sys
import itertools
import datetime

from text.blob import TextBlob

"""
TODO:

[ ] favourite replies
[ ] log parse tree
[ ] log skipped tweets
"""

def looks_like_retweet(text):
    return "RT" in text or "MT" in text or text.startswith('"') or text.startswith(u'“')

def make_reply(text):
    """
    Returns a reply to 'text' (without @username) or None if we can't help.
    """
    if looks_like_retweet(text):
        return None

    # Avoid "less #lol"
    if "less " not in text.lower():
        return None

    blob = TextBlob(text)
    tags_from_less = itertools.dropwhile((lambda (word, tag): word.lower() != 'less'),
                                         blob.tags)
    try:
        less = next(tags_from_less)
        w, w_pos = next(tags_from_less)
    except StopIteration:
        return None

    # http://bulba.sdsu.edu/jeanette/thesis/PennTags.html#JJ
    # Unfortunately there is no POS tag for mass nouns specifically:
    # http://bulba.sdsu.edu/jeanette/thesis/PennTags.html#NN is "Noun, singular or mass".
    if w_pos not in ['JJ', 'VBN']:
        return None

    # Avoid replying "fewer lonely" to "less lonely girl"
    v, v_pos = next(tags_from_less, (None, None))
    if v_pos == 'NN':
        return None

    return w.lower()


class LessListener(StreamListener):
    TIMEOUT = datetime.timedelta(seconds=120)

    def __init__(self, *args, **kwargs):
        self.post_replies = kwargs.pop('post_replies', False)
        StreamListener.__init__(self, *args, **kwargs)
        self.last = datetime.datetime.now() - self.TIMEOUT

    def on_connect(self):
        print "connected."

    def on_status(self, status):
        now = datetime.datetime.now()
        if self.post_replies and now - self.last < self.TIMEOUT:
            return

        quantity = make_reply(status.text)
        if quantity is None:
            return

        reply = u'@%s I think you mean “fewer %s”.' % (status.author.screen_name, quantity)

        if len(reply) <= 140:
            print status.text
            print '--> %s' % reply

            if self.post_replies:
                r = self.api.update_status(reply, in_reply_to_status_id=status.id)
                print "  https://twitter.com/_/status/%s" % r.id
                self.last = now


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=u'annoy some tweeps',
                                     epilog='Note that --post-replies --use-public-stream will get you banned pretty quickly')
    parser.add_argument('--post-replies', action='store_true',
                        help='post (rate-limited) replies, rather than just printing them locally')
    parser.add_argument('--use-public-stream', action='store_true',
                        help='search public tweets for "less", rather than your own stream')
    args = parser.parse_args()

    consumer_key = os.environ["CONSUMER_KEY"]
    consumer_secret = os.environ["CONSUMER_SECRET"]

    access_token = os.environ["ACCESS_TOKEN"]
    access_token_secret = os.environ["ACCESS_TOKEN_SECRET"]

    auth = OAuthHandler(consumer_key, consumer_secret)
    auth.set_access_token(access_token, access_token_secret)

    api = API(auth)
    l = LessListener(api, post_replies=args.post_replies)

    stream = Stream(auth, l)
    if args.use_public_stream:
        stream.filter(track=['less'])
    else:
        stream.userstream()
