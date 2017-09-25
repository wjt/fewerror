#!/usr/bin/env python3
import logging

from . import main

log = logging.getLogger(__name__)

if __name__ == '__main__':
    try:
        main()
    except SystemExit:
        raise
    except:
        log.info('oh no', exc_info=True)
        raise
