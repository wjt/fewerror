# vim: fileencoding=utf-8
import fewerror
import codecs
import string
import pytest

from textblob import TextBlob


def tweets_from(filename):
    with codecs.open(filename, 'r', 'utf-8') as f:
        for tweet in f:
            tweet = tweet.strip()
            reply = None
            for reply in fewerror.make_reply(tweet):
                break
            yield (tweet, reply)

def do(filename, expect_replies=None):
    for tweet, reply in tweets_from(filename):
        check(tweet, reply, expect_replies=expect_replies)

def check(tweet, reply, expect_replies=None):
    if expect_replies is None:
        print tweet
        blob = TextBlob(tweet)

        for sentence in blob.sentences:
            words = []
            tags = []
            for word, tag in sentence.tags:
                length = max(len(word), len(tag))
                words.append(string.rjust(word, length))
                tags.append(string.rjust(tag, length))

            print ' '.join(words)
            print ' '.join(tags)

        if reply is not None:
            print reply
        else:
            print "[speechless]"
        print
    elif expect_replies:
        assert reply is not None, tweet
    else:
        assert reply is None, (tweet, reply)

@pytest.mark.parametrize("tweet,reply", tweets_from('true-positive.txt'))
def test_true_positives(tweet, reply):
    check(tweet,reply, expect_replies=True)

@pytest.mark.parametrize("tweet,reply", tweets_from('false-positive.txt'))
def test_false_positives(tweet, reply):
    check(tweet,reply, expect_replies=False)

@pytest.mark.parametrize("tweet,reply", tweets_from('false-negative.txt'))
def test_false_negatives(tweet, reply):
    check(tweet,reply, expect_replies=True)
