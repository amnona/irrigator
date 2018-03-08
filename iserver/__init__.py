from logging.config import fileConfig
from pkg_resources import resource_filename

log = resource_filename(__package__, 'log.cfg')

# setting False allows other logger to print log.
fileConfig(log, disable_existing_loggers=False)
