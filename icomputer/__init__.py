from logging.config import fileConfig
from pkg_resources import resource_filename

from .icomputer import IComputer

__version__ = "1.0-dev"

__all__ = ['IComputer']


log = resource_filename(__package__, 'log.cfg')

# setting False allows other logger to print log.
fileConfig(log, disable_existing_loggers=False)
