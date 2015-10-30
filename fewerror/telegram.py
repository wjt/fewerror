#!/usr/bin/env python3
# vim: fileencoding=utf-8

import abc
import argh
import errno
import logging
import os
from retry import retry
import telegram

from . import find_corrections, format_reply

log = logging.getLogger(__name__)


class TelegramHandler(metaclass=abc.ABCMeta):
    def __init__(self, bot):
        self.bot = bot

    def handle_left_chat_participant(self, message):
        pass

    def handle_joined_chat_participant(self, message):
        pass

    def handle_command(self, message):
        pass

    def handle_text(self, message):
        pass

    def handle_message(self, message):
        log.debug("unhandled message flavour %s", message.to_dict())

    def _context(self, message):
        """Just for logging convenience"""
        sender = message.from_user.username

        if isinstance(message.chat, telegram.GroupChat):
            return '{} @ {}'.format(sender, message.chat.title)
        else:
            return sender


class TelegramStreamer(object):
    def __init__(self, bot, handler):
        self.bot = bot
        self.handler = handler
        self._last_offset_path = os.path.join(os.getcwd(), '.offset.{}.txt'.format(bot.username))

    def run(self):
        offset = self.read_last_offset()

        while True:
            updates = self._getUpdates(offset)

            for u in updates:
                # Yes, +1 is what the HTTP API requires, and python-telegram-bot does not hide this
                # cruelty from us
                offset = u.update_id + 1
                self.write_last_offset(offset)

                try:
                    self.despatch(u.message)
                except Exception:
                    log.warning("while handling %s", u, exc_info=True)

    def read_last_offset(self):
        try:
            with open(self._last_offset_path, 'r') as f:
                for line in f:
                    if line:
                        return int(line)
        except OSError as e:
            if e.errno != errno.ENOENT:
                raise

    def write_last_offset(self, offset):
        with open(self._last_offset_path, 'w') as f:
            f.write(str(offset))

    def despatch(self, message):
        if message.left_chat_participant:
            self.handle_left_chat_participant(message)
        elif message.new_chat_participant:
            self.handle_joined_chat_participant(message)
        elif message.text is not None:
            if message.text.startswith('/'):
                self.handler.handle_command(message)
            else:
                self.handler.handle_text(message)
        else:
            self.handler.handle_message(message)

    @retry(exceptions=telegram.error.TelegramError,
           delay=1,
           max_delay=30,
           backoff=2)
    def _getUpdates(self, offset):
        return self.bot.getUpdates(offset=offset, timeout=600)


class FewerrorHandler(TelegramHandler):

    def handle_left_chat_participant(self, message):
        if message.left_chat_participant.id == self.bot.id:
            log.info('Left %s', message.chat.title)

    def handle_joined_chat_participant(self, message):
        if message.joined_chat_participant.id == self.bot.id:
            log.info('Joined %s', message.chat.title)

    def handle_command(self, message):
        context = self._context(message)
        log.info('<%s> %s', context, message.text)

    def handle_text(self, message):
        context = self._context(message)

        qs = find_corrections(message.text)
        if qs:
            log.info('<%s> %s', context, message.text)

            reply = format_reply(qs)
            log.info('--> %s', reply)
            self.bot.sendMessage(
                chat_id=message.chat_id,
                reply_to_message_id=message.message_id,
                text=reply)


def main(debug: "enable debug output"=False):
    """
    Annoy some Telegram users.

    Set $TELEGRAM_BOT_TOKEN for success.
    """
    logging.basicConfig(level=('DEBUG' if debug else 'INFO'),
                        format='%(asctime)s %(levelname)8s [%(name)s] %(message)s')

    token = os.environ['TELEGRAM_BOT_TOKEN']
    bot = telegram.Bot(token=token)
    handler = FewerrorHandler(bot)
    TelegramStreamer(bot, handler).run()


if __name__ == '__main__':
    argh.dispatch_command(main)
