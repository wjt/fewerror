[@fewerror][] is a Twitter bot in the [@StealthMountain][] genre. It corrects people when they say “less” but *should* have said “fewer”. It is 100% accurate all of the time.

It originally used the [statuses/filter](https://dev.twitter.com/docs/api/1.1/post/statuses/filter) streaming API to receive all tweets containing the word *less*, and replied to one at most every two minutes. Unfortunately, it was quickly banned for “sending multiple unsolicited mentions to other users”. (I'm not sure how [@StealthMountain][] escapes the same fate.) It did manage to earn itself a [threat of physical violence][violence] during its short life as a spambot!

Anyway, now it just follows people who follow it, and “helps” them out with their grammar.

Thanks to the unstoppable [@aparrish][] for pointing me in the direction of [TextBlob][] in his post on [the making of @VoynichTechNews][voynich].

[@fewerror]: https://twitter.com/fewerror/
[@StealthMountain]: https://twitter.com/StealthMountain
[violence]: https://twitter.com/iwritememories/status/386084492685115392
[@aparrish]: https://twitter.com/aparrish
[voynich]: http://www.decontextualize.com/2013/10/voynich-tech-news/
[TextBlob]: https://github.com/sloria/TextBlob

This thing expects to fetch authorization credentials from environment variables. I `source` a file like this:

    export CONSUMER_KEY="..."
    export CONSUMER_SECRET="..."
    export ACCESS_TOKEN="..."
    export ACCESS_TOKEN_SECRET="..."

To get values for those variables, why not follow [Adam Parrish's instructions for everywordbot](https://github.com/aparrish/everywordbot#obtaining-twitter-authorization-credentials)? You might alternatively find `get_oauth_token.py` useful for `ACCESS_TOKEN` and `ACCESS_TOKEN_SECRET`.

## TODO

- favourite replies
- log tweets that contain the word "less" but didn't match our rules, for later analysis
- match more things (see `false-negative.txt` and `no-idea.txt`)
- seek back in our timeline for things we should have replied to but didn't?
- remember what we have replied to?
- follow people who enjoy our replies
