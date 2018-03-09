from flask import Blueprint, request, Response
import os
import csv
from logging import getLogger
from functools import wraps
import configparser

logger = getLogger(__name__)

Site_Main_Flask_Obj = Blueprint('Site_Main_Flask_Obj', __name__)


def check_auth(username, password):
	"""This function is called to check if a username /
	password combination is valid.
	"""
	if username != 'irrigator':
		logger.warning('wrong user supplied: %s' % username)
		return False
	if 'IRRIGATOR_PASSWORD' in os.environ:
		pwd = os.environ['IRRIGATOR_PASSWORD']
		if password != pwd:
			logger.warning('Wrong password supplied: %s' % pwd)
			return False
		return username == 'irrigator' and password == pwd
	else:
		logger.warning('IRRIGATOR_PASSWORD not in environment variables. please set.')
		return False


def authenticate():
	"""Sends a 401 response that enables basic auth"""
	return Response('Could not verify your access level for that URL.\n'
					'You have to login with proper credentials', 401,
					{'WWW-Authenticate': 'Basic realm="Login Required"'})


def requires_auth(f):
	@wraps(f)
	def decorated(*args, **kwargs):
		auth = request.authorization
		if not auth or not check_auth(auth.username, auth.password):
			return authenticate()
		return f(*args, **kwargs)
	return decorated


def get_manual_file_name(config_file_name='computer-config.txt'):
	'''Get the file name for the manual commands file

	Parameters
	----------

	Returns
	-------
	file_name : str
		the manual commands file name
	'''
	logger.debug('reading config file %s' % config_file_name)
	config = configparser.ConfigParser()
	config.read(config_file_name)
	if 'computer_name' not in config['IComputer']:
		logger.warning('computer_name not found in %s - cannot find manual commands file' % config_file_name)
		return 'commands.txt'
	computer_name = config['IComputer']['computer_name']
	logger.debug('computer name is %s' % computer_name)
	return '%s_commands.txt' % computer_name


def get_faucets_file_name():
	'''Get the file name for the manual commands file

	Parameters
	----------

	Returns
	-------
	file_name : str
		the manual commands file name
	'''
	return 'faucet-list.txt'


@Site_Main_Flask_Obj.route('/manual_open/<faucet>', methods=['GET'])
@requires_auth
def manual_open(faucet):
	'''Manually open a faucet

	Parameters
	----------
	faucet: str
		NAME of the faucet to open (i.e. cypress)
	'''
	logger.debug('manual open faucet %s' % faucet)
	with open(get_manual_file_name(),'w') as cf:
		cf.write('open\t%s\n' % faucet)
	return 'opening faucet %s' % faucet


@Site_Main_Flask_Obj.route('/manual_close/<faucet>', methods=['GET'])
@requires_auth
def manual_close(faucet):
	'''Manually close a faucet

	Parameters
	----------
	faucet: str
		NAME of the faucet to open (i.e. cypress)
	'''
	logger.debug('manual close faucet %s' % faucet)
	with open(get_manual_file_name(),'w') as cf:
		cf.write('close\t%s\n' % faucet)
	return 'closing  faucet %s' % faucet


@Site_Main_Flask_Obj.route('/close_all', methods=['GET'])
@requires_auth
def close_all():
	'''Close all faucets now
	'''
	logger.debug('manual close all faucets')
	with open(get_manual_file_name(),'w') as cf:
		cf.write('closeall\tcloseall\n')
	return 'closing all faucets!'


@Site_Main_Flask_Obj.route('/get_faucets', methods=['GET'])
@requires_auth
def get_faucets():
	'''Get a list of all faucets
	'''
	logger.debug('get faucets')
	faucet_list = ''
	with open(get_faucets_file_name()) as fl:
		ffile = csv.DictReader(fl, delimiter='\t')
		for row in ffile:
			faucet_type = row['faucet_type']
			fname = row['name']
			faucet_list += fname+';'
	return faucet_list
