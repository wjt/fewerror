# vim: fileencoding=utf-8
import json
import os

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
    connections = {}

    def __init__(self):
        self._updates = []

    def me(self):
        return User.parse(self, fewerror_user)

    def lookup_friendships(self, screen_names):
        return [
            Relationship.parse(self, {
                "name": "{x}y Mc{x}face".format(x=screen_name),
                "screen_name": screen_name,
                "id": i,
                "id_str": str(i),
                "connections": self.connections.get(screen_name, [
                    # "following",
                    # "followed_by",
                ]),
            })
            for i, screen_name in enumerate(screen_names, 2 ** 32)
        ]

    def destroy_friendship(self, user_id):
        try:
            self.connections[user_id].remove("following")
        except (KeyError, ValueError):
            pass

    def update_status(self, **kwargs):
        self._updates.append(kwargs)
        r = Status(api=self)
        setattr(r, 'id', len(self._updates))
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
])
def test_end_to_end(filename, connections, expected, tmpdir):
    api = MockAPI()
    api.connections = dict(connections)

    with open(filename, 'r') as f:
        status = Status.parse(api, json.load(fp=f))

    with tmpdir.as_cwd():
        l = LessListener(api=api, post_replies=True)
        l.december_greetings = ('It is cold outside.',)

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
