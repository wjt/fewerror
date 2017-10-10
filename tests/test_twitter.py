# vim: fileencoding=utf-8
import json
import os
import datetime as dt

from unittest.mock import NonCallableMock
import pytest

from tweepy.models import User, Status, Relationship
from tweepy.parsers import ModelParser

from fewerror.twitter import get_sanitized_text, LessListener

@pytest.mark.parametrize('filename,expected', [
    ('647349406191218688.json',
     "Four Penguin novels of 128pp or less* that turn me on. Unlike that one published yesterday. \n\n* yes, I do mean less",
    ),

    ('582960339714744320.json',
     "If media had shown more news curiosity in recent years, this would seem less surprising.",
    ),
    # No media
    ('649911069322948608.json',
     """OH:\n“It's all vaguely Sisyphean.”\n“Oh! THAT's the word I was looking for yesterday!”""",
    ),
    # extended_tweet with trailing quoted tweet link
    ('793203535626309632.json',
     """Imagine thinking giving the nuclear codes to someone who treats classified material carelessly wouldn't be a problem.""",
    ),
    # extended_tweet with leading @replies
    ('793561534861574144.json',
     """Evolution is on the curriculum, so this is irrelevant. Unless you're proposing we apply "pressure" by continuing exactly as we are?""",
    ),
])
def test_sanitize(filename, expected):
    api = NonCallableMock()

    with open(os.path.join('tests', filename), 'r') as f:
        status = Status.parse(api, json.load(f))

    text = get_sanitized_text(status)
    assert '&amp;' not in text
    assert 'http' not in text
    assert text == expected


'''
@pytest.mark.parametrize("fmt", [
    (u"RT @test: {}"),
    (u"THIS. MT @test: {}"),
    (u'"{}" @myfriend'),
    (u'“{}” ýéş'),
])
def test_ignores_manual_rts(fmt):
    tweet = fmt.format(true_positives[0])
    assert fewerror.make_reply(tweet) is None
'''

fewerror_user = {
    "screen_name": "fewerror",
    "id": 1932168457,
    "id_str": "1932168457",
    "name": "Fewer Errors",
}


class MockAPI:
    parser = ModelParser()

    def __init__(self, connections):
        self._updates = []
        self._connections = {k: set(v) for k, v in connections.items()}

    def me(self):
        return User.parse(self, fewerror_user)

    def lookup_friendships(self, screen_names):
        return [
            Relationship.parse(self, {
                "name": "{x}y Mc{x}face".format(x=screen_name),
                "screen_name": screen_name,
                "id": i,
                "id_str": str(i),
                "connections": self._connections.get(screen_name, [
                    # "following",
                    # "followed_by",
                ]),
            })
            for i, screen_name in enumerate(screen_names, 2 ** 32)
        ]

    def destroy_friendship(self, screen_name):
        self._connections[screen_name] -= {"following"}

    def update_status(self, **kwargs):
        self._updates.append(kwargs)
        r = Status(api=self)
        setattr(r, 'id', len(self._updates))
        setattr(r, 'author', self.me())
        # Status.user is "DEPRECIATED" so we omit it
        return r


@pytest.mark.parametrize('filename,connections,expected', [
    ('tests/640748887330942977.json',
     {
         "krinndnz": ["following", "followed_by"],
         "eevee": ["following", "followed_by"],
         "mistydemeo": ["following"],
     },
     "@krinndnz @eevee I think you mean “fewer bad”."
    ),
    ('tests/671809680902127616.json',
     {
         "benjammingh": ["following", "followed_by"],
     },
     "@benjammingh I think you mean “fewer grip”. It is cold outside."),
    ('tests/671809680902127616.json',
     {},
     None),
    ('tests/738052925646340096.json',
     {
         'ArosOrcidae': ['following', 'followed_by'],
     },
     "@Renferos @ArosOrcidae I think you mean “fewer skilled”.",
    ),
    # Tweet from @davidgerard, who we were following but had stopped following
    # us. We correctly unfollowed him, and
    ('tests/801120047829753856.json',
     {
        'mjg59': ['following', 'followed_by'],
        'davidgerard': ['following'],
     },
     None,
    ),
    # Modified version of 793561534861574144.json where the string 'less' only appears in the
    # full_text, not in the truncated text. Regression test for a bug where we dropped any such
    # tweet.
    ('tests/less-only-in-extended-text.json',
     {
         'RobTH26': ['following', 'followed_by'],
     },
     '@RobTH26 I think you mean “fewer cake”.',
    ),

])
def test_end_to_end(filename, connections, expected, tmpdir):
    api = MockAPI(connections=connections)

    with open(filename, 'r') as f:
        status = Status.parse(api, json.load(fp=f))

    l = LessListener(api=api, post_replies=True, gather='tweets', state_dir=str(tmpdir))

    # 100% festivity for all of December
    l.december_greetings = ('It is cold outside.',)
    l.festive_probability = 1.
    assert l.get_festive_probability(dt.date(2016, 12, 5)) == 1.

    l.on_status(status)

    # Never reply to the same toot twice
    l.on_status(status)

    # Rate-limit replies for same word
    setattr(status, 'id', status.id + 1)
    l.on_status(status)

    if expected is None:
        assert api._updates == []
    else:
        assert len(api._updates) == 1
        u = api._updates[0]
        assert u['status'] == expected

    for k, before in connections.items():
        after = api._connections[k]
        assert ('following' in after) == ('followed_by' in before), \
            (k, before, after)

@pytest.mark.parametrize('date,p', [
    (dt.date(2016, 11, 30), 0),
    (dt.date(2016, 12, 1), 0.25),
    (dt.date(2016, 12, 9), 0.5),
    (dt.date(2016, 12, 17), 0.75),
    (dt.date(2016, 12, 25), 1),
    (dt.date(2016, 12, 26), 0),
])
def test_festivity(date, p, tmpdir):
    api = MockAPI(connections={})

    l = LessListener(api=api, post_replies=True, gather=None, state_dir=str(tmpdir))

    assert l.get_festive_probability(date) == p


@pytest.mark.parametrize('id_,expected_filename', [
    ('649911069322948608', '64/649911069322948608.json'),
    ('1649911069322948608', '164/1649911069322948608.json'),
])
def test_save_tweet(tmpdir, id_, expected_filename):
    api = MockAPI(connections={})
    foo = tmpdir.join('foo')

    l = LessListener(api=api, gather=str(foo), state_dir=str(tmpdir))
    s = Status.parse(api=api, json={
        'id': int(id_),
        'id_str': id_,
    })
    l.save_tweet(s)

    j = tmpdir.join('foo', expected_filename)
    assert j.check()
