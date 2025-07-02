#!/usr/bin/env python

from flask import Flask
from .isite import Site_Main_Flask_Obj
from logging import getLogger
import sys

logger = getLogger('iserver')
# basicConfig(level='DEBUG')
logger.setLevel('DEBUG')

app = Flask(__name__)
app.register_blueprint(Site_Main_Flask_Obj)

port = 5000
logger.debug('debug msg')
logger.debug('starting iserver on port %d' % port)
print('starting iserver on port %d' % port, file=sys.stderr)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=port)
