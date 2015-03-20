# vim: fileencoding=utf-8
import fewerror
import codecs
import string
import pytest

from textblob import TextBlob


true_positives = [
    u"I don't know whether I find the Believe.in thing more or less offensive than Tesco Clubcard sending HTML with `text/plain`",

    pytest.mark.xfail(reason='regressed at some point; maybe splitting subclauses would help')(
        u"Good: Sweet puppies sleeping. Less Good: Vet tells us they will be 50-60lbs instead of the 25-30 the Rescue group... pic.twitter.com/CBUpjZyxLu"

    ),
    u"Sitting next to Dan Winship here at the @WebKitGTK hackfest, turned out it was a missing TCP_NODELAY. Fixed! HTTPS now 33% less slow :)",
    u"My phone is more or less screwed.",
    u"One broken string, one shock from a microphone, and one admonition from the sound guy to rock less hard. Success! Thanks for coming.",
    u"Hispanic-American Adults Are Less Catholic and More ‘Unaffiliated’ Than Ever Before",
    u"Okay, it was an ad for an emergency-alarm watch. I feel less annoyed now.",
    u"We're not from a faraway country. We were just less lucky than you.",

    pytest.mark.xfail(reason='not sure')(
        u"@tellingfibulas Awww cheers mate. That's much appreciated :D I'm getting less wanky hopefully.",
    ),

    u"(And I know it's heresy to say it, but while Hissing Fauna is excellent I'm less keen on the direction it heralded)",

    # mass noun         vvvvvvvvvv
    u"Reckon you'd lose less blood having a major heart op!!"
]


@pytest.mark.parametrize("tweet", true_positives)
def test_true_positives(tweet):
    assert fewerror.make_reply(tweet) is not None


false_positives = [
    u"The fact that @merrittwhitley can Instagram me but not text me back.... haha I expect nothing less. #Cool #IllJustWait #MyBestFriendIsSlow",

    u"one less lonely girl is my song",
    u"There's going to be one less lonely girl",

    # Less JJ JJ+ nounish. "Fewer successful political unions" is not what the speaker meant, but it
    # is grammatical.
    u"@AdamRamsay @dhothersall For sake of balance; Less successful political unions include USSR and Yugoslavia."
    # Similar. https://twitter.com/kiehlmanniac/status/578486683353661441
    u"@resiak @fewerror @travisci Are there any less over-engineered satirical grammar bots?",

    u"oh yh due to there being less gender-neutral people, right? :D",
    u"Yes, Fred Phelps did horrible things, said horrible things. That doesn't mean you can do slightly less horrible things and be a good person.",
    u"There are people with life sentences for way less: Tim Allen arrested for over 650 grams (1.43 lb) of cocaine. 1978. http://twitter.com/History_Pics/status/442776869742854145/photo/1pic.twitter.com/EtUND0xYxm ",
]


@pytest.mark.parametrize("tweet", false_positives)
def test_false_positives(tweet):
    assert fewerror.make_reply(tweet) is None


def test_mass_nouns():
    assert fewerror.make_reply("I wish I had studied less mathematics") is not None
    assert fewerror.make_reply("I wish I had studied less mathematics students") is None


@pytest.mark.parametrize("desc,fmt", [
    ("RT", u"RT @test: {}"),
    ("MT", u"THIS. MT @test: {}"),
    ("dq", u'"{}" @myfriend'),
    ("uniquote", u'“{}” ýéş'),
])
def test_ignores_manual_rts(desc, fmt):
    tweet = fmt.format(true_positives[0])
    assert fewerror.make_reply(tweet) is None
