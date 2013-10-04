# coding=utf-8
from tweepy.streaming import StreamListener
from tweepy import OAuthHandler, Stream, API
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
        less = tags_from_less.next()
        w, w_pos = tags_from_less.next()
    except StopIteration:
        return None

    # http://bulba.sdsu.edu/jeanette/thesis/PennTags.html#JJ
    # Unfortunately there is no POS tag for mass nouns specifically:
    # http://bulba.sdsu.edu/jeanette/thesis/PennTags.html#NN is "Noun, singular or mass".
    if w_pos not in ['JJ', 'VBN']:
        return None

    # Avoid replying "fewer lonely" to "less lonely girl"
    try:
        v, v_pos = tags_from_less.next()
        if v_pos == 'NN':
            return None
    except StopIteration:
        pass

    return u'I think you mean “fewer %s”.' % (w.lower())


class LessListener(StreamListener):
    TIMEOUT = datetime.timedelta(seconds=120)

    def __init__(self, *args):
        StreamListener.__init__(self, *args)

        self.last = datetime.datetime.now() - self.TIMEOUT

    def on_connect(self):
        print "connected."

    def on_status(self, status):
        print status.text

        now = datetime.datetime.now()
        if now - self.last < self.TIMEOUT:
            return

        bare_reply = make_reply(status.text)
        if bare_reply is None:
            return

        reply = u"@%s %s" % (status.author.screen_name, bare_reply)

        if len(reply) <= 140:
            print '--> %s' % reply
            r = self.api.update_status(reply, in_reply_to_status_id=status.id)
            print "  https://twitter.com/_/status/%s" % r.id
            self.last = now


if __name__ == '__main__':
    consumer_key = os.environ["CONSUMER_KEY"]
    consumer_secret = os.environ["CONSUMER_SECRET"]

    access_token = os.environ["ACCESS_TOKEN"]
    access_token_secret = os.environ["ACCESS_TOKEN_SECRET"]

    auth = OAuthHandler(consumer_key, consumer_secret)
    auth.set_access_token(access_token, access_token_secret)

    api = API(auth)
    l = LessListener(api)

    stream = Stream(auth, l)
    #stream.filter(track=['less'])
    stream.userstream()
