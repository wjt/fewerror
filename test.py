import fewerror
import codecs
import sys

for name in sys.argv[1:]:
    print name
    print "=" * len(name)
    with codecs.open(name, 'r', 'utf-8') as f:
        for tweet in f:
            print tweet.strip()
            reply = fewerror.make_reply(tweet)
            if reply is not None:
                print reply
            else:
                print "[speechless]"
            print
    print
