#!/usr/bin/env python

import argparse
from flask import Flask
from .isite import Site_Main_Flask_Obj
from logging import getLogger
import sys

logger = getLogger('iserver')
# basicConfig(level='DEBUG')
logger.setLevel('INFO')

ISERVER_VERSION = 'V0.4'

app = Flask(__name__)
app.register_blueprint(Site_Main_Flask_Obj)

parser = argparse.ArgumentParser(description='Run the irrigator iserver')
parser.add_argument('--port', type=int, default=5000, help='Port to listen on')
args = parser.parse_args()

port = args.port
app.config['ISERVER_VERSION'] = ISERVER_VERSION
logger.debug('debug msg')
logger.info('starting iserver on port %d' % port)
print('starting iserver on port %d version %s' % (port, ISERVER_VERSION), file=sys.stderr)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=port)
