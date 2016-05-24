# vim: fileencoding=utf-8
import fewerror
import codecs
import string
import pytest

from textblob import TextBlob


true_positives = [
    (u"I don't know whether I find the Believe.in thing more or less offensive than Tesco Clubcard sending HTML with `text/plain`",

     'fewer offensive',
    ),

    pytest.mark.xfail(reason='regressed at some point; maybe splitting subclauses would help')(
        (u"Good: Sweet puppies sleeping. Less Good: Vet tells us they will be 50-60lbs instead of the 25-30 the Rescue group... pic.twitter.com/CBUpjZyxLu",
         'fewer good',
        ),
    ),
    (u"Sitting next to Dan Winship here at the @WebKitGTK hackfest, turned out it was a missing TCP_NODELAY. Fixed! HTTPS now 33% less slow :)",
     'fewer slow',
    ),
    (u"My phone is more or less screwed.",
     'fewer screwed',
    ),
    (u"One broken string, one shock from a microphone, and one admonition from the sound guy to rock less hard. Success! Thanks for coming.",
     'fewer hard',
    ),
    (u"Hispanic-American Adults Are Less Catholic and More ‘Unaffiliated’ Than Ever Before",
     'fewer Catholic',
    ),
    (u"Okay, it was an ad for an emergency-alarm watch. I feel less annoyed now.",
     'fewer annoyed',
    ),
    (u"We're not from a faraway country. We were just less lucky than you.",
     'fewer lucky',
    ),

    # pytest.mark.xfail(reason='POS tagger thinks "janky" is a noun')(
        (u"@tellingfibulas Awww cheers mate. That's much appreciated :D I'm getting less janky hopefully.",
         'fewer janky',
        ),
    # ),

    (u"(And I know it's heresy to say it, but while Hissing Fauna is excellent I'm less keen on the direction it heralded)",
     'fewer keen',
    ),

    # mass noun          vvvvvvvvvv
    (u"Reckon you'd lose less blood having a major heart op!!",
     'fewer blood',
    ),

    # Would be nice to get this right. "a less theatrical version" -> "I think you mean 'a fewer
    # theatrical version'" would be funny, whereas "I think you mean 'fewer theatrical'" is less
    # good.
    pytest.mark.xfail(reason='a less adj noun')(
        (u"hey, remember that google bus thing? sf delivers a less theatrical version http://t.co/YxVq1JYZP9",
         'fewer theatrical',
        ),
    ),

    # https://github.com/wjt/fewerror/issues/2
    (u"In the context of https://medium.com/@b_k/https-the-end-of-an-era-c106acded474 … it’s striking that the problems setting up ssh are much much less onerous",
     'fewer onerous',
    ),

    pytest.mark.xfail(reason='not implemented')(
        ("which is to say I found it no less surprising than 'with' itself.",
         'no fewer surprising',
        ),
    ),

    (u"So if I say fewer less often all is well?",
     u"fewer often",
    ),

    (u"Less monitoring if you ask me",
     u"fewer monitoring",
    ),

    # [100%] fewer exercise is be ungrammatical, though "100% fewer exercises" would be grammatical...
    (u"I've eaten 50% more food and done 100% less exercise since I got to NY.",
     "fewer exercise",
    ),

    (u"The One True Syntax Pedant Bot is @fewerror. Much less bad than all others.",
     "fewer bad",
    ),

    (u"it’s WAY less spiritually exhausting than constantly having to educate about race/gender/etc.",
     "fewer spiritually",  # TODO: would be nice to say "fewer spiritually exhausting"
    ),

    (u"""Telegram is certainly less popular, but WhatsApp is much less open.""",
     ["fewer popular", "fewer open"],
    ),

    (u"""I could care less""",
     "could care fewer",
    ),

    (u"""Goals\n\nLess hate.\nLess stress.\nLess pain.\nMore love.\nMore rest.\nMore joy.""",
     [
         "fewer hate",  # VBP
         "fewer stress",  # NN
         "fewer pain",  # NN
     ],
    ),
]


@pytest.mark.parametrize("tweet,reply", true_positives)
def test_true_positives(tweet, reply):
    replies = [reply] if isinstance(reply, str) else reply
    actual_replies = fewerror.find_corrections(tweet)
    assert actual_replies == replies, str(TextBlob(tweet).tags)


false_positives = [
    u"The fact that @merrittwhitley can Instagram me but not text me back.... haha I expect nothing less. #Cool #IllJustWait #MyBestFriendIsSlow",

    u"one less lonely girl is my song",
    u"There's going to be one less lonely girl",

    # Less JJ JJ+ nounish. "Fewer successful political unions" is not what the speaker meant, but it
    # is grammatical.
    u"@AdamRamsay @dhothersall For sake of balance; Less successful political unions include USSR and Yugoslavia.",

    # Similar. https://twitter.com/kiehlmanniac/status/578486683353661441
    u"@resiak @fewerror @travisci Are there any less over-engineered satirical grammar bots?",

    u"oh yh due to there being less gender-neutral people, right? :D",
    u"Yes, Fred Phelps did horrible things, said horrible things. That doesn't mean you can do slightly less horrible things and be a good person.",
    u"There are people with life sentences for way less: Tim Allen arrested for over 650 grams (1.43 lb) of cocaine. 1978. http://twitter.com/History_Pics/status/442776869742854145/photo/1pic.twitter.com/EtUND0xYxm ",

    u"I wish there were less pretentious motherfucking ass holes on this planet...i feel so worthless right now",

    pytest.mark.xfail(reason='TODO: split on/strip out links?')(
        u"Firefox Tweaks – An attempt to make Firefox suck less http://ift.tt/1MuFeCN",
    ),

    # https://twitter.com/fewerror/status/659747048099618825
    pytest.mark.xfail(reason='quotes')(
        u'''I was about to do this but then realised they have reveals that say “show less” rather than “show fewer” so now _I’m_ angry :-\\''',
    ),

    u"""it's like four swords but with one less person and internet rando multiplayer""",

    # wordfilter errs on the side of caution, that's a good idea
    u"""I want less Scunthorpe in my life""",
    u"""That bath was less therapeutic than I had hoped""",

    pytest.mark.xfail(reason='''Should be "bore me fewer" or nothing;
                      "less given" is at least still wrong I suppose!''')(
        u"""I would have thought a comic book movie might bore me less, given my history!""",
    ),
]


@pytest.mark.parametrize("tweet", false_positives)
def test_false_positives(tweet):
    assert fewerror.find_corrections(tweet) == []


def test_mass_nouns():
    assert fewerror.find_corrections("I wish I had studied less mathematics") == ['fewer mathematics']
    assert fewerror.find_corrections("I wish I had studied less mathematics students") == []


@pytest.mark.parametrize("corrections,reply", [
    (("a"), "I think you mean “a”"),
    (("a", "b"), "I think you mean “a”, and furthermore “b”"),
    (("a", "b", "c"), "I think you mean “a”, “b”, and furthermore “c”"),
    (("a", "b", "c", "d"), "I think you mean “a”, “b”, “c”, and furthermore “d”"),
])
def test_format_reply(corrections, reply):
    assert fewerror.format_reply(corrections) == reply
