#!/usr/bin/env python
from contextlib import contextmanager
import fewerror
from datetime import datetime, timedelta

class Now:
    def __init__(self):
        self.now = datetime.now()

    def advance(self, td):
        self.now += td

    def __call__(self):
        return self.now


@contextmanager
def roundtripped_state(tmpdir, timeout_seconds=-1, per_word_timeout_seconds=-1):
    d = str(tmpdir)
    now = Now()

    def load():
        return fewerror.State.load(
            "test", d,
            timeout_seconds=timeout_seconds,
            per_word_timeout_seconds=per_word_timeout_seconds,
            now=now)

    s = load()
    yield s, now

    s2 = load()
    assert s == s2


def test_str(tmpdir):
    with roundtripped_state(tmpdir) as (s, now):
        assert ' 0 ' in str(s)


def test_reply_once(tmpdir):
    with roundtripped_state(tmpdir) as (s, now):
        assert s.can_reply(123, 'blood')
        assert s.can_reply(123, 'blood')

        s.record_reply(123, 'blood', 124)
        assert not s.can_reply(123, 'blood')
        # It shouldn't matter what the word is, we don't reply to the same tweet twice.
        assert not s.can_reply(123, 'annoying')

        # But rate-limiting is disabled, so reply immediately to the same word in any other toot
        assert s.can_reply(456, 'blood')
        assert s.can_reply(456, 'annoying')


def test_rate_limit(tmpdir):
    with roundtripped_state(tmpdir, timeout_seconds=30, per_word_timeout_seconds=-1) as (s, now):
        assert s.can_reply(123, 'blood')

        s.record_reply(123, 'blood', 124)
        assert not s.can_reply(123, 'blood')

        # Reply to nothing else for 30 seconds
        assert not s.can_reply(456, 'blood')
        assert not s.can_reply(456, 'annoying')

        now.advance(timedelta(seconds=31))

        assert s.can_reply(456, 'blood')
        assert s.can_reply(456, 'annoying')


def test_word_rate_limit(tmpdir):
    with roundtripped_state(tmpdir, timeout_seconds=-1, per_word_timeout_seconds=30) as (s, now):
        assert s.can_reply(123, 'blood')

        s.record_reply(123, 'blood', 124)
        assert not s.can_reply(123, 'blood')

        # Reply to new tweets, but not about blood
        assert not s.can_reply(456, 'blood')
        assert s.can_reply(789, 'annoying')

        now.advance(timedelta(seconds=31))

        assert s.can_reply(456, 'blood')
        assert s.can_reply(789, 'annoying')
