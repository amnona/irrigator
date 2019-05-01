#!/usr/bin/env python

from logging import getLogger
import argparse

import icomputer

logger = getLogger(__name__)

parser = argparse.ArgumentParser()
parser.add_argument('--debug-level', '-l', help='debug level (DEBUG/INFO/WARNING)', default='INFO')

ns = parser.parse_args()

logger.setLevel(ns.debug_level)
icomputer.set_log_level(ns.debug_level)


logger.info('Starting irrigator')
icomp = icomputer.IComputer()
icomp.main_loop()
