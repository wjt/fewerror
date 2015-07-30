#!/usr/bin/env python3
# vim: fileencoding=utf-8

# XXX: https://github.com/leandrotoledo/python-telegram-bot/pull/22
import logging
logging.basicConfig(level='DEBUG',
                    format='%(asctime)s %(levelname)8s [%(name)s] %(message)s')

import argh
import os
import telegram

from . import make_reply

log = logging.getLogger(__name__)


class Telegrammar(object):
    def __init__(self, bot):
        self.bot = bot

    def run(self):
        offset = None

        while True:
            updates = self.bot.getUpdates(offset=offset, timeout=600)

            for u in updates:
                self.despatch(u)

            if updates:
                offset = updates[-1].update_id

    def despatch(self, message):
        if message.left_chat_participant:
            self.handle_left_chat_participant(message)
        elif message.new_chat_participant:
            self.handle_joined_chat_participant(message)
        elif message.text is not None:
            # TODO: handle commands
            self.handle_text(message)
        else:
            log.debug("unhandled message %s", message.to_dict())

    def handle_left_chat_participant(self, message):
        if message.left_chat_participant.id == self.bot.id:
            log.info('Left %s', message.chat.title)

    def handle_joined_chat_participant(self, message):
        if message.joined_chat_participant.id == self.bot.id:
            log.info('Joined %s', message.chat.title)

    def handle_text(self, message):
        sender = message.from_user.username

        if isinstance(message.chat, telegram.GroupChat):
            context = '{} @ {}'.format(sender, message.chat.title)
        else:
            context = sender

        quantity = make_reply(message.text)
        if quantity is not None:
            log.info('<%s> %s', context, message.text)

            reply = u'I think you mean “{}”.'.format(quantity)
            log.info('--> %s', reply)
            self.bot.sendMessage(
                chat_id=message.chat_id,
                reply_to_message_id=message.message_id,
                text=reply)


def main(debug: "enable debug output"=False):
    """
    Annoy some Telegram users.

    Requires the TELEGRAM_BOT_TOKEN environment variable to be set.
    """
    token = os.environ['TELEGRAM_BOT_TOKEN']
    bot = telegram.Bot(token=token, debug=debug)

    Telegrammar(bot).run()

if __name__ == '__main__':
    argh.dispatch_command(main)
