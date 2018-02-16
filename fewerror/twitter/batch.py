import argparse
import glob
import json
import logging
import os
import re
import time

import tweepy

from . import FMK, classify_user, user_url

log = logging.getLogger(__name__)


DEFAULT_BLOCK_TIMEOUT = 120


def add_user_args(parser):
    g = parser.add_mutually_exclusive_group(required=True)
    g.add_argument('--user-id', type=int)
    g.add_argument('--screen-name', type=str)


def get_user_kwargs(args):
    if args.user_id is not None:
        return {'user_id': args.user_id}
    elif args.screen_name is not None:
        return {'screen_name': args.screen_name}
    else:
        raise ValueError(args)


def save_user(user, directory):
    path = os.path.join(directory, 'user.{}.json'.format(user.id_str))
    with open(path, 'w') as f:
        json.dump(obj=user._json, fp=f)


def fetch_followers(api, args):
    '''Fetches all followers' JSON and saves them to the given directory.

    Files will have names of the form 'user.<numeric id>.json'.'''
    os.makedirs(args.directory, exist_ok=True)

    n = api.me().followers_count
    g = tweepy.Cursor(api.followers, count=200).items()

    for i, follower in enumerate(g, 1):
        log.info('[%d/%d] %s', i, n, follower.screen_name)
        save_user(follower, args.directory)


def fetch_mutuals(api, args):
    '''Intersects a directory of user.*.json (as populated with fetch-followers) with users
    following USER_ID/SCREEN_NAME.'''

    mine = {
        int(re.match(r'user.(\d+).json', os.path.basename(f)).group(1))
        for f in glob.glob(os.path.join(args.directory, 'user.*.json'))
    }
    mutuals = set()

    kwargs = get_user_kwargs(args)
    kwargs['count'] = 5000

    g = tweepy.Cursor(api.followers_ids, **kwargs).pages()
    for i, page in enumerate(g, 1):
        m = (mine & set(page))
        log.info('Page %d: %d mutuals', i, len(m))
        print('\n'.join(map(str, m)), flush=True)
        mutuals |= m
        time.sleep(60)

    log.info('Done; %d mutuals total', len(mutuals))


def classify(api, args):
    classes = {e: set() for e in FMK}
    for dirpath, _, filenames in os.walk(args.directory):
        for filename in filenames:
            if not re.match(r'user.\d+.json', filename):
                continue

            with open(os.path.join(dirpath, filename), 'rb') as f:
                j = json.load(f)

            user = tweepy.models.User.parse(api, j)
            c = classify_user(api, user, fetch_statuses=False)
            classes[c].add(user)

    for user in classes[FMK.BLOCK]:
        args.block_file.write('{}\n'.format(user.id))

    already_following = {u for u in classes[FMK.FOLLOW_BACK] if u.following}
    classes[FMK.FOLLOW_BACK] -= already_following

    results = {'already following': len(already_following)}
    for e, us in classes.items():
        results[e.name.lower().replace('_', ' ')] = len(us)

    w = max(map(len, results))
    v = max(len(str(n)) for n in results.values())
    for label, n in results.items():
        print('{:>{w}}: {:{v}} users'.format(label, n, w=w, v=v))


def report_spam(api, *args, **kwargs):
    sleep_time = 15 * 60

    for i in reversed(range(5)):
        try:
            return api.report_spam(*args, **kwargs)
        except tweepy.TweepError as e:
            if e.api_code == 205 and i > 0:
                # “You are over the limit for spam reports.  The account limit
                # for reporting spam has been reached. Try again later.”
                #
                # Annoyingly, this is a different error code to the normal
                # “rate-limited“ error code so tweepy's built-in rate limiting
                # doesn't apply.
                log.info("Over the spam-report limit; sleeping for %ds",
                         sleep_time, exc_info=True)
                time.sleep(sleep_time)
                sleep_time *= 1.5
            else:
                raise


def _block_many(api, to_block_ids, timeout, report):
    n = len(to_block_ids)
    for i, to_block_id in enumerate(to_block_ids, 1):
        try:
            if report:
                log.info('[%d/%d] reporting #%d', i, n, to_block_id)
                u = report_spam(api, user_id=to_block_id, perform_block=True)
                log.info('reported and blocked %s (#%d)', user_url(u), to_block_id)
            else:
                log.info('[%d/%d] blocking #%d', i, n, to_block_id)
                u = api.create_block(user_id=to_block_id,
                                     include_entities=False,
                                     skip_status=True)
                log.info('blocked %s (#%d)', user_url(u), to_block_id)

            api.destroy_friendship(user_id=to_block_id)
            log.info('Unfollowed #%d', to_block_id)
        except tweepy.TweepError as e:
            if e.api_code in (
                34,  # reported by report_spam
                50,  # reported by create_block
            ):
                log.info('#%d no longer exists', to_block_id)
            else:
                raise

        if i < n:
            time.sleep(timeout)


def block(api, args):
    '''Unfollow, block, and optionally report as spam many user IDs.'''
    to_block_ids = {int(line) for line in args.block_file if line.strip()}
    log.info('would like to unfollow block %d ids', len(to_block_ids))

    existing_block_ids = set(tweepy.Cursor(api.blocks_ids).items())
    log.info('%d existing blocks', len(existing_block_ids))
    to_block_ids.difference_update(existing_block_ids)

    _block_many(api, to_block_ids, timeout=args.timeout, report=args.report)


def block_one(api, args):
    '''Block and unfollow a user, and (optionally) our friends who follow them.'''

    kwargs = get_user_kwargs(args)

    if args.mutuals:
        log.info('Fetching our friends')
        my_friends = set(tweepy.Cursor(api.friends_ids).items())
        log.info('Fetched %d friends', len(my_friends))
        time.sleep(args.TIMEOUT)

        mutuals = set()
        log.info('Intersecting friends with users following %s', kwargs)
        g = tweepy.Cursor(api.followers_ids, **kwargs).pages()
        for i, page in enumerate(g, 1):
            m = my_friends & set(page)
            log.info('Page %d: %d mutuals', i, len(m))
            mutuals |= m
            time.sleep(args.TIMEOUT)

        _block_many(api, mutuals, timeout=args.timeout, report=False)

    u = api.create_block(include_entities=False,
                         skip_status=True,
                         **kwargs)
    log.info('Blocked %s', user_url(u))

    api.destroy_friendship(**kwargs)
    log.info('Unfollowed %s', user_url(u))


def ℕ(value):
    '''Vim really deals badly with this function name.'''
    try:
        i = int(value)
        if i < 0:
            raise ValueError
        return i
    except ValueError:
        raise argparse.ArgumentTypeError('{!r} ∉ ℕ'.format(value))


def add_subcommands(subparsers, var):
    # fetch-followers
    fetch_p = subparsers.add_parser('fetch-followers', help='fetch some tweeps',
                                    description=fetch_followers.__doc__)
    fetch_p.set_defaults(func=fetch_followers)
    default_fetch_directory = os.path.join(var, 'followers')
    fetch_p.add_argument('directory', default=default_fetch_directory,
                         help='(default: {})'.format(default_fetch_directory))

    # fetch-mutuals
    fetch_m = subparsers.add_parser('fetch-mutuals', help='intersect some tweeps',
                                    description=fetch_mutuals.__doc__)
    fetch_m.set_defaults(func=fetch_mutuals)
    fetch_m.add_argument('directory')
    add_user_args(fetch_m)

    # classify
    classify_p = subparsers.add_parser('classify', help='group some tweeps')
    classify_p.set_defaults(func=classify)
    classify_p.add_argument('directory', default=default_fetch_directory,
                            help='(default: {})'.format(default_fetch_directory))
    classify_p.add_argument('block_file', type=argparse.FileType('w'),
                            help='file to store one numeric user id per line, '
                                 'as used by "block" command')

    block_one_p = subparsers.add_parser('block-one', help='block one tweep',
                                        description=block_one.__doc__)
    block_one_p.set_defaults(func=block_one)
    add_user_args(block_one_p)
    block_one_p.add_argument('--mutuals', action='store_true',
                             help='Also block friends who follow them')
    block_one_p.add_argument('--timeout', type=ℕ, default=DEFAULT_BLOCK_TIMEOUT,
                             help='delay in seconds between each API call')

    # block
    block_p = subparsers.add_parser('block', help='block some tweeps',
                                    description=block.__doc__)
    block_p.set_defaults(func=block)
    block_p.add_argument('block_file', type=argparse.FileType('r'),
                         help='file with one numeric user id per line')
    block_p.add_argument('--report', action='store_true',
                         help='with --block, also report for spam')
    block_p.add_argument('--timeout', type=ℕ, default=DEFAULT_BLOCK_TIMEOUT,
                         help='delay in seconds between each API call')


__all__ = ['add_subcommands']
