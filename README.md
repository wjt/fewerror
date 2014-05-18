[@fewerror][] is a Twitter bot in the [@StealthMountain][] genre. It corrects people when they say “less” but *should* have said “fewer”. It is 100% accurate all of the time.

It originally used the [statuses/filter](https://dev.twitter.com/docs/api/1.1/post/statuses/filter) streaming API to receive all tweets containing the word *less*, and replied to one at most every two minutes. Unfortunately, it was quickly banned for “sending multiple unsolicited mentions to other users”. (I'm not sure how [@StealthMountain][] escapes the same fate.) So now it just follows people who follow it, and “helps” them out with their grammar.

## Praise for [@fewerror][]

> lolllll check ur algorithm assbag robot !!!!!!!!! <cite>– [@dudehugs](https://twitter.com/dudehugs/status/418455551383588864)</cite>

> what sort of person do you have to be to sit down at your computer and create that twitter account. <cite>– [@edgardavidsgeps](https://twitter.com/edgardavidsgeps/status/416620250877399041)

> i think i meant that if u do that again u gonna be a less fortunate invalid. <cite>– [@iwritememories](https://twitter.com/iwritememories/status/386084492685115392)

> […] definitely a bot. A poorly programmed one at that. <cite>– [@parimalkumar](https://twitter.com/parimalkumar/status/419552596131454977)</cite>

> the world needs less of these bots due to their creators being punched to death <cite>– [@pattymo](https://twitter.com/pattymo/status/420262996586151936)</cite>

> lol nope fuck you robopedant <cite>– [@iphisol](https://twitter.com/iphisol/status/422046676648726528)</cite>

> Failiest bot ever <cite>– [@C_Halestorm](https://twitter.com/C_Halestorm/status/426510945423478784)</cite>

> in love with you, fewerror <cite>– [@pigthe](https://twitter.com/pigthe/status/431211363889713152)</cite>

> murder is not becoming of a believer & is disrespectful of God's creations <cite>– [@wshemp](https://twitter.com/wshemp/status/428203543980290048)</cite>

> I like @fewerror. Should be called @JeremyPaxman he's always trying to pull that shit <cite>– [@YellowRoss](https://twitter.com/YellowRoss/status/444977740287340544)</cite>

> GO FUCK YOURSELF <cite>– [@janhopis](https://twitter.com/janhopis/status/447396453808603136)</cite>

> [I LOVE U](https://twitter.com/mama_tuna/status/450597264466399232) / [YOU RESPOND SO QUICKLY](https://twitter.com/mama_tuna/status/450597290659819520) <cite>– @mama_tuna</cite>

> the natural language processing of the day award goes to @fewerror
 <cite>– [@vogon](https://twitter.com/vogon/status/451087365079973888)</cite>

> the worst spelling bot that exists on twitter <cite>– [@shifty_11](https://twitter.com/shifty_11/status/452746071530569728)</cite>

> fucktastic bot <cite>– [@ebassi](https://twitter.com/ebassi/status/451851394535153664)</cite>

> If all trolls were like this, I'd have no problem with the activity <cite>– [@hyperdeath128k](https://twitter.com/hyperdeath128k/status/462522298998992896)</cite>

> "I love @fewerror ." "Me too. I feel like we've built a rapport."
 <cite>– [@drmoonpants](https://twitter.com/drmoonpants/status/467446078082531328)</cite>

> Someday the clerk in the "10 Items or Less" aisle is gonna smash your skull in with a can of cling peaches. <cite>– [@KevinCarson1](https://twitter.com/KevinCarson1/status/467889956027781120)</cite>


## For those who care about software

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
