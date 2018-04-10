#!/usr/bin/env python

import icomputer
from logging import getLogger

logger = getLogger(__name__)
logger.setLevel('DEBUG')
icomputer.set_log_level('DEBUG')

logger.debug('running closeall')

for idx in range(16):
	cfaucet = icomputer.numatofaucet.NumatoFaucet(relay=idx, name='lala', computer_name='pita', local_computer_name='pata')
	print('closing faucet %s' % idx)
	cfaucet.close()
	print('closed faucet %s' % idx)
