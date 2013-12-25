import fewerror
import codecs
import sys

def do(filename, expect_replies=None):
    with codecs.open(filename, 'r', 'utf-8') as f:
        for tweet in f:
            tweet = tweet.strip()
            try:
                reply = fewerror.make_reply(tweet)
            except:
                reply = None

            if expect_replies is None:
                print tweet
                if reply is not None:
                    print reply
                else:
                    print "[speechless]"
                print
            elif expect_replies:
                assert reply is not None, tweet
            else:
                assert reply is None, (tweet, reply)

def test_true_positives():
    do('true-positive.txt', expect_replies=True)

def test_false_positives():
    do('false-positive.txt', expect_replies=False)

def test_false_negatives():
    do('false-negative.txt', expect_replies=True)

if __name__ == '__main__':
    for name in sys.argv[1:]:
        print name
        print "=" * len(name)
        do(name, expect_replies=None)
        print
