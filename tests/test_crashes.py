#!/usr/bin/env python

import pytest
import fewerror

crashy_tweet = '''2x more likely to hire men than women, even when he's less capable http://t.co/XcovCXpsqC

"We shouldn't sacrifice quality to hire women!"'''


def test_not_crashing():
    reply = fewerror.make_reply(crashy_tweet)
    if reply is not None:
        # if we get anything out at all, it should be 'fewer capable'
        assert reply == 'fewer capable'
