import os
import tweepy

consumer_key = os.environ["CONSUMER_KEY"]
consumer_secret = os.environ["CONSUMER_SECRET"]
auth = tweepy.OAuthHandler(consumer_key, consumer_secret)

redirect_url = auth.get_authorization_url()
print("go to %s" % redirect_url)

verifier = input('Verifier:')

try:
    access_token, access_token_secret = auth.get_access_token(verifier)
    print(u'ACCESS_TOKEN="%s"' % access_token)
    print(u'ACCESS_TOKEN_SECRET="%s"' % access_token_secret)
except tweepy.TweepError as e:
    print('Error! Failed to get access token.')
    print(e)
