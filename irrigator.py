import logging
from logging import getLogger

import icomputer
import timers

logger = getLogger(__name__)
logger.addHandler(logging.StreamHandler())
logger.setLevel(logging.DEBUG)

logger.info('Starting irrigator')
icomp = icomputer.IComputer()
icomp.main_loop()
