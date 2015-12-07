# vim: fileencoding=utf-8
import json
import os

from unittest.mock import NonCallableMock
import pytest

from tweepy.models import User, Status
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
    friendships = {}

    def __init__(self):
        self._updates = []

    def me(self):
        return User.parse(self, fewerror_user)

    def lookup_friendships(self, screen_names):
        print("looking up {}".format(screen_names))
        return [
            # TODO: return something for unknown so that it is actually tested.
            self.friendships[screen_name]
            for screen_name in screen_names
            if screen_name in self.friendships
        ]

    def update_status(self, **kwargs):
        self._updates.append(kwargs)
        r = Status(api=self)
        setattr(r, 'id', len(self._updates))
        return r


@pytest.mark.parametrize('filename,expected', [
    ('tests/640748887330942977.json',
     "@krinndnz @eevee @mistydemeo I think you mean “fewer bad”."
    ),
    ('tests/671809680902127616.json',
     "@benjammingh @cafuego I think you mean “fewer grip”. It is cold outside."),
])
def test_end_to_end(filename, expected, tmpdir):
    api = MockAPI()

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

        assert len(api._updates) == 1
        u = api._updates[0]
        assert u['status'] == expected
