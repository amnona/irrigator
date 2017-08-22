#!/usr/bin/env python

import logging
from logging import getLogger

import icomputer
import timers
from counter_numato import CounterNumato

logger = getLogger(__name__)
logger.addHandler(logging.StreamHandler())
logger.setLevel(logging.DEBUG)

# cn = CounterNumato('0', '1')
# while True:
#     b = cn.get_current_value()
#     print(b)



logger.info('Starting irrigator')
icomp = icomputer.IComputer()
icomp.main_loop()
