import os
import yaml
import pytest

from unittest.mock import MagicMock, call
from fewerror.thatsnotmybot import ThatsNotMyBot


def test_validate():
    ThatsNotMyBot()


def test_generate():
    ThatsNotMyBot().generate()


def test_argparse():
    ThatsNotMyBot().main([])


@pytest.mark.parametrize('initial_state,is_my', [
    (None, False),
    ({}, False),
    ({'object': 'teapot', 'n': 1, 'last_id': 42}, False),
    ({'object': 'cake', 'n': 7, 'last_id': 42}, True),
])
def test_first_tweet(tmpdir, initial_state, is_my):
    state_yaml = str(tmpdir.join('x.yaml'))

    if initial_state is not None:
        with open(state_yaml, 'w') as f:
            yaml.dump(initial_state, f)

    status = MagicMock()
    status.author.screen_name = 'abcde'
    status.id = 12345

    api = MagicMock()
    api.update_status.return_value = status

    tnmb = ThatsNotMyBot()
    tnmb.get_twitter_api = lambda: api
    tnmb.main(['tweet', '--state', state_yaml])

    with open(state_yaml, 'r') as f:
        state = yaml.load(f)

    if is_my:
        assert state == {}
    else:
        assert state['n'] == (initial_state or {}).get('n', 0) + 1
        assert 'object' in state
        if initial_state and 'object' in initial_state:
            assert initial_state['object'] == state['object']
        assert state['last_id'] == 12345

    assert len(api.update_status.mock_calls) == 1
    args, kwargs = api.update_status.call_args
    tweet = args[0]

    if initial_state:
        assert initial_state['object'] in tweet
        assert kwargs['in_reply_to_status_id'] == initial_state['last_id']
    else:
        assert kwargs['in_reply_to_status_id'] is None

    if is_my:
        assert tweet.startswith("THAT'S my")
    else:
        assert tweet.startswith("That's not")
