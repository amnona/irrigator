#!/usr/bin/env python

from flask import Flask
from .isite import Site_Main_Flask_Obj
from logging import getLogger
import sys

logger = getLogger('iserver')
# basicConfig(level='DEBUG')
logger.setLevel('INFO')

ISERVER_VERSION = 'V0.4'
DEFAULT_PORT = 5000

app = Flask(__name__)
app.register_blueprint(Site_Main_Flask_Obj)
app.config['ISERVER_VERSION'] = ISERVER_VERSION

if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Run the irrigator iserver')
    parser.add_argument('--port', type=int, default=DEFAULT_PORT, help='Port to listen on')
    args = parser.parse_args()

    port = args.port
    logger.debug('debug msg')
    logger.info('starting iserver on port %d' % port)
    print('starting iserver on port %d version %s' % (port, ISERVER_VERSION), file=sys.stderr)
    app.run(host='0.0.0.0', port=port)
