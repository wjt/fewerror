# vim: fileencoding=utf-8
import json
import os

from unittest.mock import NonCallableMock
import pytest

from tweepy.models import Status

from fewerror.twitter import get_sanitized_text

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
