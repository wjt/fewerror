import os
import telegram
import logging

from . import make_reply

log = logging.getLogger(__name__)


def main(token):
    bot = telegram.Bot(token=token)
    # me = bot.getMe()
    offset = None

    while True:
        log.info('Polling for updates')
        updates = bot.getUpdates(offset=offset, timeout=600)

        for u in updates:
            if u.message.text is None:
                print(u.message.to_dict())
            else:
                print(u.message.text)
                quantity = make_reply(u.message.text)
                if quantity is not None:
                    reply = u'I think you mean “{}”.'.format(quantity)
                    bot.sendMessage(chat_id=u.message.chat_id, text=reply)

            offset = u.update_id + 1


if __name__ == '__main__':
    logging.basicConfig(level='DEBUG',
                        format='%(asctime)s %(levelname)8s [%(name)s] %(message)s')

    token = os.environ['TELEGRAM_BOT_TOKEN']
    main(token)
