# vim: fileencoding=utf-8
import json
import os

from unittest.mock import NonCallableMock
import pytest

from tweepy.models import Status

from fewerror import get_sanitized_text, State
import fewerror.twitter

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


def test_state(tmpdir):
    d = str(tmpdir)

    s1 = State.load("test", d)
    assert s1.replied_to_user_and_word == {}
    s1.replied_to_user_and_word[('foo', 'bar')] = 1
    s1.save()

    s2 = State.load("test", d)
    assert s1.replied_to_user_and_word == s2.replied_to_user_and_word
