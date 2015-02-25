#!/usr/bin/env python

import fewerror
import os

def test_stateholder(tmpdir):
    with tmpdir.as_cwd():
        sh = fewerror.StateHolder('test')
        state = sh.load()
        assert state.replied_to == {}
        assert state.replied_to_user_and_word == {}
        assert state.last_time_for_word == {}
        state.replied_to[12345] = 67890
        sh.save(state)
        state_2 = sh.load()
        assert state_2.replied_to == state.replied_to
        assert state_2.replied_to_user_and_word == {}
        assert state_2.last_time_for_word == {}
