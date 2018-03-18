#!/usr/bin/env python

import logging
from logging import getLogger
from pkg_resources import resource_filename
from logging.config import fileConfig


import icomputer

logger = getLogger(__name__)
logger.setLevel(logging.DEBUG)

log = 'log.cfg'
# log = resource_filename(__package__, 'log.cfg')

# setting False allows other logger to print log.
fileConfig(log, disable_existing_loggers=False)


# logger.addHandler(logging.StreamHandler())
# logger.setLevel(logging.DEBUG)

# create file handler which logs even debug messages
## fh = logging.FileHandler('spam.log')
## fh.setLevel(logging.DEBUG)
# create console handler with a higher log level
##ch = logging.StreamHandler()
##ch.setLevel(logging.DEBUG)
# create formatter and add it to the handlers
##formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
##fh.setFormatter(formatter)
##ch.setFormatter(formatter)
# add the handlers to the logger
##logger.addHandler(fh)
##logger.addHandler(ch)

logger.info('Starting irrigator')
icomp = icomputer.IComputer()
icomp.main_loop()
