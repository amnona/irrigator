#!/usr/bin/env python

import logging
from logging import getLogger
import time

import icomputer
import timers
from counter_arduino import CounterArduino

logger = getLogger(__name__)
# logger.addHandler(logging.StreamHandler())
# logger.setLevel(logging.DEBUG)

# create file handler which logs even debug messages
fh = logging.FileHandler('spam.log')
fh.setLevel(logging.DEBUG)
# create console handler with a higher log level
ch = logging.StreamHandler()
ch.setLevel(logging.DEBUG)
# create formatter and add it to the handlers
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
fh.setFormatter(formatter)
ch.setFormatter(formatter)
# add the handlers to the logger
logger.addHandler(fh)
logger.addHandler(ch)

import datetime
zz=timers.next_weekday(datetime.datetime.now(), 4)
print(zz.date())

# ca = CounterArduino(iopin='2')
# while True:
#     b = ca.get_count()
#     print(b)
#     time.sleep(1)



logger.info('Starting irrigator')
icomp = icomputer.IComputer()
icomp.main_loop()
