import enum
import logging

from .util import user_url


log = logging.getLogger(__name__)


def lang_base(lang):
    base, *rest = lang.split('-')
    return base


class FMK(enum.Enum):
    '''Classification for new followers.'''
    FOLLOW_BACK = 1
    NEUTRAL = 2
    BLOCK = 3


def classify_user(api, whom, fetch_statuses=True):
    '''Crude attempt to identify spammy followers. It appears that this bot
    was used to boost follower counts since it always followed back.

    Returns an entry from FMK.'''
    label = '{} (#{})'.format(user_url(whom), whom.id)

    # Sorry if you speak these languages, but after getting several
    # thousand spam followers I needed a crude signal.
    forbidden_langs = {'ar', 'ja', 'tr', 'zh'}
    if lang_base(whom.lang) in forbidden_langs:
        log.info('%s has forbidden lang %s',
                 label, whom.lang)
        return FMK.BLOCK

    # Many spam users had user.lang == 'en' but tweet only in those languages.
    try:
        # "fully-hydrated" users have a status on them
        statuses = [whom.status]
    except AttributeError:
        # (if they're not protected...)
        if whom.protected:
            log.info('%s is protected; assume they are okay', label)
            return FMK.FOLLOW_BACK

        if whom.statuses_count == 0 and whom.followers_count > 1000:
            log.info('%s has never tweeted but has %d followers',
                     label, whom.followers_count)
            return FMK.BLOCK

        # but users in follow notifications do not; and nor do users who
        # haven't tweeted for a while (or ever)
        if fetch_statuses:
            # TODO: this fails for protected accounts who haven't accepted our request
            statuses = api.user_timeline(user_id=whom.id, count=20)
        else:
            log.info('%s: not enough information', label)
            return FMK.NEUTRAL

    langs = {lang_base(status.lang) for status in statuses}
    if langs & forbidden_langs:
        log.info('%s tweets in forbidden lang %s',
                 label, ', '.join(langs & forbidden_langs))
        return FMK.BLOCK

    if 'en' not in langs:
        log.info('%s tweets in %s, not en -- why are they following us?',
                 label, ', '.join(langs))
        return FMK.NEUTRAL

    return FMK.FOLLOW_BACK
