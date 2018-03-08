from flask import Flask
from .isite import Site_Main_Flask_Obj
from logging import getLogger
import sys

logger = getLogger(__name__)

print('hello', file=sys.stderr)

app = Flask(__name__)
app.register_blueprint(Site_Main_Flask_Obj)


port=5000
print('hello2', file=sys.stderr)
logger.debug('starting iserver on port %d' % port)
print('starting iserver on port %d' % port, file=sys.stderr)
app.run(host='0.0.0.0', port=port)
