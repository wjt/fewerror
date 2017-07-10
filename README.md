# @fewerror

[@fewerror][] is a Twitter (and [Telegram](http://telegram.me/fewerrorbot)) bot in the [@StealthMountain][] genre. If you follow it, it will correct you when you say “less” but *should* have said “fewer”. It is 100% accurate all of the time.

## Context

Here's a piece reflecting on [three years of @fewerror](http://t.wjt.me.uk/post/151462998480/three-years-of-fewerror).

## Praise for [@fewerror][]

So much praise, it now lives in [a separate file](PRAISE.md).

## For those who care about software

Thanks to the unstoppable [@aparrish][] for pointing me in the direction of [TextBlob][] in her post on [the making of @VoynichTechNews][voynich].

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

To get values for those variables, why not follow [Allison Parrish's instructions for everywordbot](https://github.com/aparrish/everywordbot#obtaining-twitter-authorization-credentials)? You might alternatively find `get_oauth_token.py` useful for `ACCESS_TOKEN` and `ACCESS_TOKEN_SECRET`.

It originally used the [statuses/filter](https://dev.twitter.com/docs/api/1.1/post/statuses/filter) streaming API to receive all tweets containing the word *less*, and replied to one at most every two minutes. Unfortunately, it was quickly banned for “sending multiple unsolicited mentions to other users”. (I'm not sure how [@StealthMountain][] escapes the same fate.)

[![Build Status](https://travis-ci.org/wjt/fewerror.svg?branch=master)](https://travis-ci.org/wjt/fewerror)
[![Coverage Status](https://coveralls.io/repos/wjt/fewerror/badge.svg?branch=master&service=github)](https://coveralls.io/github/wjt/fewerror?branch=master)
[![Code Health](https://landscape.io/github/wjt/fewerror/landscape/landscape.svg?style=flat)](https://landscape.io/github/wjt/fewerror/landscape)

# Other bots live here too

## Bots run by [Cheap Bots, Done Quick!](http://cheapbotsdonequick.com/)

These live in the [cbdq](./cbdq) directory.

* [@gnuerror](https://twitter.com/gnuerror/): an incoherent activist for an
  incoherent age.
* [@xbotsdoney](https://twitter.com/xbotsdoney): Yet another sixpenny
  automaton, furnished promptly as a paean to the service which powers it.

## [That's Not My Bot](https://twitter.com/thatsnotmybot)

Inspired by a series of books for young children. More details in [this blog post](http://t.wjt.me.uk/post/162583526405/thats-not-my-bot). [source](fewerror/thatsnotmybot.py), [unnecessarily large grammar](fewerror/thatsnotmybot.yaml).
