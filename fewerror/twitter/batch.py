import glob
import json
import logging
import os
import re
import time

import tweepy

from . import FMK, classify_user, user_url

log = logging.getLogger(__name__)


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
    following id.'''

    mine = {
        int(re.match(r'user.(\d+).json', os.path.basename(f)).group(1))
        for f in glob.glob(os.path.join(args.directory, 'user.*.json'))
    }
    mutuals = set()

    g = tweepy.Cursor(api.followers_ids, user_id=args.id, count=5000).pages()
    for i, page in enumerate(g, 1):
        m = (mine & set(page))
        log.info('Page %d: %d mutuals', i, len(m))
        print('\n'.join(mutuals), flush=True)
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


def block(api, args):
    '''Unfollow, block, and optionally report as spam many user IDs.'''
    report = args.report

    to_block_ids = set(map(int, args.block_file))
    log.info('would like to unfollow block %d ids', len(to_block_ids))

    existing_block_ids = set(tweepy.Cursor(api.blocks_ids).items())
    log.info('%d existing blocks', len(existing_block_ids))
    # to_block_ids.difference_update(existing_block_ids)

    n = len(to_block_ids)
    for i, to_block_id in enumerate(to_block_ids, 1):
        try:
            if to_block_id in existing_block_ids:
                log.info('[%d/%d] #%d already blocked', i, n, to_block_id)
            elif report:
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

        if i < n and to_block_id not in existing_block_ids:
            # Experimentation suggests the limit is 50 spam reports per 30 minute window,
            # or 1 spam report per 36 seconds. Round up...
            time.sleep(45)
