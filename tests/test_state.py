#!/usr/bin/env python

import fewerror

def test_roundtrip(tmpdir):
    with tmpdir.as_cwd():
        state = fewerror.State.load('test')
        assert state.replied_to == {}
        assert state.replied_to_user_and_word == {}
        assert state.last_time_for_word == {}
        state.replied_to[12345] = 67890
        state.save()
        state_2 = fewerror.State.load('test')
        assert state_2.replied_to == state.replied_to
        assert state_2.replied_to_user_and_word == {}
        assert state_2.last_time_for_word == {}
