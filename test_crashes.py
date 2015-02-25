#!/usr/bin/env python

import pytest
import fewerror

crashy_tweets = [
'''2x more likely to hire men than women, even when he's less capable http://t.co/XcovCXpsqC

"We shouldn't sacrifice quality to hire women!"''',
]

@pytest.mark.parametrize("tweet", crashy_tweets)
def test_not_crashing(tweet):
    for reply in fewerror.make_reply(tweet):
        # if we get anything out at all, it should be 'fewer capable'
        assert reply == 'fewer capable'
