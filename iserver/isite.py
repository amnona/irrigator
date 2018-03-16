from flask import Blueprint, request, Response, render_template
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
	return Response('Could not verify your access level for that URL.\nYou have to login with proper credentials', 401, {'WWW-Authenticate': 'Basic realm="Login Required"'})


def requires_auth(f):
	@wraps(f)
	def decorated(*args, **kwargs):
		auth = request.authorization
		if not auth or not check_auth(auth.username, auth.password):
			return authenticate()
		return f(*args, **kwargs)
	return decorated


def get_computer_name(config_file_name='computer-config.txt'):
	'''Get the name of the current irrigation computer based on the config file'''
	logger.debug('reading config file %s' % config_file_name)
	config = configparser.ConfigParser()
	config.read(config_file_name)
	if 'computer_name' not in config['IComputer']:
		logger.warning('computer_name not found in config file %s' % config_file_name)
		return 'local'
	computer_name = config['IComputer']['computer_name']
	logger.debug('computer name is %s' % computer_name)
	return computer_name


def get_manual_file_name():
	'''Get the file name for the manual commands file

	Parameters
	----------

	Returns
	-------
	file_name : str
		the manual commands file name
	'''
	computer_name = get_computer_name()
	return '%s_commands.txt' % computer_name


def get_status_file_name():
	computer_name = get_computer_name()
	return '%s_status.txt' % computer_name


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


def get_status():
	'''Get the open/close status of the faucets

	Returns
	-------
	set of faucets that are open
	'''
	open_faucets = set()
	try:
		with open(get_status_file_name) as fl:
			for cline in fl:
				open_faucets.add(cline)
		logger.debug('found %d open faucets' % len(open_faucets))
		return open_faucets
	except:
		logger.warning('could not find the status file')
		return open_faucets


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
			fname = row['name']
			faucet_list += fname+';'
	return faucet_list


def _faucets_info():
	'''Get the row about all faucet

	Parameters
	----------

	Returns
	-------
	list of dict of type:data
	'''
	logger.debug('_getting faucets info')
	output=[]
	with open(get_faucets_file_name()) as fl:
		ffile = csv.DictReader(fl, delimiter='\t')
		for row in ffile:
			output.append(row)
	return output


@Site_Main_Flask_Obj.route('/faucet_info/<faucet>', methods=['GET'])
@requires_auth
def faucet_info(faucet):
	'''Get all the details about a given faucet

	Parameters:
	-----------
	faucet: str
		the name of the faucet to get the info for

	Returns
	-------
	str: made of key:val;
	'''
	logger.debug('getting faucet info for faucet %s' % faucet)
	info=''
	with open(get_faucets_file_name()) as fl:
		ffile = csv.DictReader(fl, delimiter='\t')
		for row in ffile:
			if row['name'] != faucet:
				continue
			for ck,cv in row.items():
				info += '%s:%s;' % (ck,cv)
	if info=='':
		info='%s not found' % faucet
	return info


@Site_Main_Flask_Obj.route('/', methods=['GET'])
@requires_auth
def main_site():
	wpage = render_template('main.html')
	wpage += '<table>'
	wpage += '<thead><tr><th>Name</th><th>Relay</th><th>Duration</th><th>Status</th></tr></thead>'
	wpage += '<tbody>'
	faucets = _faucets_info()
	open_faucets = get_status()
	for cfaucet in faucets:
		cname = cfaucet.get('name','NA')
		crelay = cfaucet.get('relay','NA')
		cduration = cfaucet.get('default_duration','NA')
		if cname in open_faucets:
			cstatus = 'Open'
		else:
			cstatus = 'Closed'
		wpage += '<tr>'
		wpage += '<td>%s</td>' % cname
		wpage += '<td>%s</td>' % crelay
		wpage += '<td>%s</td>' % cduration
		wpage += '<td>%s</td>' % cstatus
		wpage += '<td><button id=".button-test" type="button" onclick="open_faucet(\'%s\')">open</button></td>' % cname
		wpage += '<td><button id=".button-test" type="button" onclick="close_faucet(\'%s\')">close</button></td>' % cname
		wpage += '</tr>'
	wpage += '</tbody></table>'
	wpage += '</body>'
	wpage += '</html>'
	return wpage
