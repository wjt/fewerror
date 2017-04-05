import argparse
import logging
import os

from mastodon import Mastodon
from . import checkedshirt, find_corrections, format_reply


log = logging.getLogger(__name__)


def local_path(filename):
    parent = os.path.dirname(os.path.dirname(__file__))
    return os.path.join(parent, filename)


def do_register(args):
    if os.path.exists(args.client_creds):
        raise ValueError('%r already exists' % args.client_creds)

    Mastodon.create_app(
        'fewerror',
        api_base_url=args.api_base_url,
        to_file=args.client_creds)


def do_login(args):
    if not os.path.exists(args.client_creds):
        raise ValueError('%r does not exist (try "register")' % args.client_creds)

    if os.path.exists(args.user_creds):
        raise ValueError('%r already exists' % args.user_creds)

    mastodon = Mastodon(
        client_id=args.client_creds,
        api_base_url=args.api_base_url)
    mastodon.log_in(args.username, args.password, to_file=args.user_creds)


def do_run(args):
    if not os.path.exists(args.client_creds):
        raise ValueError('%r does not exist (try "register")' % args.client_creds)

    if not os.path.exists(args.user_creds):
        raise ValueError('%r does not exist (try "login")' % args.user_creds)

    mastodon = Mastodon(
        client_id=args.client_creds,
        access_token=args.user_creds,
        api_base_url=args.api_base_url)
    # wjt_id = mastodon.account_search('wjt@mastodon.social')[0]['id']
    # print(mastodon.account_follow(wjt_id))
    for toot in mastodon.timeline():
        import pprint
        log.debug(pprint.pformat(toot))
        html = toot['content']
        text = html  # TODO
        quantities = find_corrections(text)
        if quantities:
            correction = format_reply(quantities)
            log.info("want to correct %s: %s", toot['account']['acct'], correction)


def main():
    parser = argparse.ArgumentParser()

    def add_argument(p, *args, **kwargs):
        if 'default' in kwargs:
            kwargs.setdefault('help', '')
            kwargs['help'] += ' (default: {})'.format(kwargs['default'])
        p.add_argument(*args, **kwargs)

    checkedshirt.add_arguments(parser)

    g = parser.add_argument_group('Mastodon instance stuff')
    add_argument(g, '--client-creds', metavar='FILE', default=local_path('mastodon_client.txt'))
    add_argument(g, '--user-creds', metavar='FILE', default=local_path('mastodon_user.txt'))
    add_argument(g, '--api-base-url', metavar='URL', default='https://botsin.space')

    subparsers = parser.add_subparsers(dest='subcommand')
    subparsers.required = True

    register = subparsers.add_parser('register')
    register.set_defaults(func=do_register)

    login = subparsers.add_parser('login')
    login.set_defaults(func=do_login)
    login.add_argument('username')
    login.add_argument('password')

    run = subparsers.add_parser('run')
    run.set_defaults(func=do_run)

    args = parser.parse_args()
    checkedshirt.init(args)
    args.func(args)


if __name__ == '__main__':
    main()
