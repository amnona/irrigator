#!/usr/bin/env python

import logging
from logging import getLogger

import icomputer
import timers
from counter_numato import CounterNumato

logger = getLogger(__name__)
# logger.addHandler(logging.StreamHandler())
# logger.setLevel(logging.DEBUG)

# create file handler which logs even debug messages
fh = logging.FileHandler('spam.log')
fh.setLevel(logging.DEBUG)
# create console handler with a higher log level
ch = logging.StreamHandler()
ch.setLevel(logging.WARNING)
# create formatter and add it to the handlers
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
fh.setFormatter(formatter)
ch.setFormatter(formatter)
# add the handlers to the logger
logger.addHandler(fh)
logger.addHandler(ch)


# cn = CounterNumato('0', '1')
# while True:
#     b = cn.get_current_value()
#     print(b)



logger.info('Starting irrigator')
icomp = icomputer.IComputer()
icomp.main_loop()
