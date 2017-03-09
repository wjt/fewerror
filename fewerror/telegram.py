#!/usr/bin/env python3
# vim: fileencoding=utf-8

import argparse
import logging
import os
import telegram
from telegram.ext import (
    Updater, CommandHandler, MessageHandler, Filters,
)

from . import find_corrections, format_reply

log = logging.getLogger(__name__)


def _context(message):
    """Just for logging convenience"""
    sender = message.from_user.username

    if message.chat.type == telegram.Chat.GROUP:
        return '{} @ {}'.format(sender, message.chat.title)
    else:
        return sender


def on_start(bot, update):
    bot.sendMessage(chat_id=update.message.chat_id,
                    text="Hi. I'll let you know when you say ‘less’ but "
                         "should say ‘fewer’.")


def on_message(bot, update):
    message = update.message
    context = _context(message)
    qs = find_corrections(message.text)
    if qs:
        log.info('<%s> %s', context, update.message.text)

        reply = format_reply(qs)
        log.info('--> %s', reply)
        bot.sendMessage(
            chat_id=message.chat_id,
            reply_to_message_id=message.message_id,
            text=reply)


def main():
    p = argparse.ArgumentParser(
        description='Annoy some Telegram users. '
                    'Set $TELEGRAM_BOT_TOKEN for success.')
    p.add_argument('--debug', action='store_true', help='enable debug output')
    a = p.parse_args()

    logging.basicConfig(level=('DEBUG' if a.debug else 'INFO'),
                        format='%(asctime)s %(levelname)8s [%(name)s] %(message)s')

    token = os.environ['TELEGRAM_BOT_TOKEN']
    updater = Updater(token=token)
    dispatcher = updater.dispatcher
    dispatcher.add_handler(CommandHandler('start', on_start))
    dispatcher.add_handler(MessageHandler(Filters.text, on_message))
    updater.start_polling()
    updater.idle()


if __name__ == '__main__':
    main()
