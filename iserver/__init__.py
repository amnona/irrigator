from logging.config import fileConfig

try:
	from importlib import resources as _importlib_resources
except Exception:
	_importlib_resources = None

try:
	from pkg_resources import resource_filename as _pkg_resource_filename
except Exception:
	_pkg_resource_filename = None


def resource_filename(package, resource_name):
	"""Return a filesystem path for a packaged resource across Python versions."""
	if _importlib_resources is not None:
		try:
			if hasattr(_importlib_resources, 'files'):
				return str(_importlib_resources.files(package).joinpath(resource_name))
			with _importlib_resources.path(package, resource_name) as path_obj:
				return str(path_obj)
		except Exception:
			pass

	if _pkg_resource_filename is not None:
		return _pkg_resource_filename(package, resource_name)

	raise ModuleNotFoundError('No resource loader available: importlib.resources or pkg_resources is required')

log = resource_filename(__package__, 'log.cfg')

# setting False allows other logger to print log.
fileConfig(log, disable_existing_loggers=False)
