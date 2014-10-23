import os
import tweepy

consumer_key = os.environ["CONSUMER_KEY"]
consumer_secret = os.environ["CONSUMER_SECRET"]
auth = tweepy.OAuthHandler(consumer_key, consumer_secret, secure=True)

redirect_url = auth.get_authorization_url()
print "go to %s" % redirect_url

verifier = raw_input('Verifier:')

try:
    auth.get_access_token(verifier)
except tweepy.TweepError as e:
    print 'Error! Failed to get access token.'
    print e

print 'ACCESS_TOKEN="%s"' % auth.access_token.key
print 'ACCESS_TOKEN_SECRET="%s"' % auth.access_token.secret
