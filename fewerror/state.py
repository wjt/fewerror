import datetime
import dateutil.parser
import errno
import json
import logging
import os
import tempfile

log = logging.getLogger(__name__)


class State(object):
    def __init__(self,
                 filename,
                 olde=None,
                 now=datetime.datetime.utcnow,
                 timeout_seconds=120,
                 per_word_timeout_seconds=60*60):
        self._state_filename = filename
        self._replied_to = {
            int(k): v for k, v in olde.get('replied_to', {}).items()
        }
        self._last_time_for_word = {
            k: dateutil.parser.parse(v)
            for k, v in olde.get('last_time_for_word', {}).items()
        }

        self._timeout = datetime.timedelta(seconds=timeout_seconds)
        self._per_word_timeout = datetime.timedelta(
            seconds=per_word_timeout_seconds)

        self._now = now
        self._last = now() - self._timeout

    def __str__(self):
        return '<State: {} replied_to, {} last_time_for_word>'.format(
            len(self._replied_to), len(self._last_time_for_word))

    def __eq__(self, value):
        return (
            self._state_filename == value._state_filename and
            self._replied_to == value._replied_to and
            self._last_time_for_word == value._last_time_for_word
        )

    @classmethod
    def load(cls, screen_name, directory='.', **kwargs):
        filename = os.path.join(directory, 'state.{}.json'.format(screen_name))

        try:
            with open(filename, 'r') as f:
                olde = json.load(f)

        except IOError as e:
            if e.errno != errno.ENOENT:
                raise

            olde = {}

        state = cls(filename, olde, **kwargs)
        log.info('loaded %s: %s', filename, state)
        return state

    def save(self):
        with tempfile.NamedTemporaryFile(prefix=self._state_filename, suffix='.tmp', dir='.',
                                         mode='w',
                                         delete=False) as f:
            json.dump(fp=f, obj={
                'replied_to': self._replied_to,
                'last_time_for_word': {
                    k: v.isoformat()
                    for k, v in self._last_time_for_word.items()
                },
            })

        os.rename(f.name, self._state_filename)

    def can_reply(self, status_id, quantities):
        for quantity in quantities:
            quantity = quantity.lower()
            now = self._now()

            r_id = self._replied_to.get(status_id, None)
            if r_id is not None:
                log.info(u"…already replied: %d", r_id)
                return False

            last_for_this = self._last_time_for_word.get(quantity, None)
            if last_for_this and now - last_for_this < self._per_word_timeout:
                log.info(u"…corrected '%s' at %s, waiting till %s", quantity, last_for_this,
                         last_for_this + self._per_word_timeout)
                return False

            if now - self._last < self._timeout:
                log.info(u"rate-limiting until %s…", self._last + self._timeout)
                return False

        return True

    def record_reply(self, status_id, quantities, r_id):
        now = self._now()

        self._last = now
        self._replied_to[status_id] = r_id
        for quantity in quantities:
            self._last_time_for_word[quantity.lower()] = now

        self.save()
