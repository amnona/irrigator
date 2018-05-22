from flask import Blueprint, request, Response, render_template
import os
import csv
from logging import getLogger
from functools import wraps
import configparser
from collections import defaultdict
import datetime
import time
import re
import matplotlib.pyplot as plt
import numpy as np
from io import BytesIO
import base64
import urllib
import mpld3

# import numpy as np

logger = getLogger(__name__)

Site_Main_Flask_Obj = Blueprint('Site_Main_Flask_Obj', __name__)


def get_last_lines(filename, num_lines, max_line_len=200):
	'''Get the last lines of a large file

	Parameters
	----------
	filename: str
	num_lines: int
		number of lines to get from end of file
	max_line_len: int, optional
		going back max_line_len*num_lines and scans forward

	Returns
	-------
	list of str (one per line)
	'''
	with open(filename, 'rb') as fl:
		fl.seek(-num_lines * max_line_len, os.SEEK_END)
		lines = fl.readlines()
		out_lines = []
		for x in range(min(num_lines, len(lines))):
			out_lines.append(lines[-(x + 1)].decode().strip())
	return out_lines


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
	return 'actions/%s_commands.txt' % computer_name


def get_status_file_name():
	computer_name = get_computer_name()
	return 'actions/%s_status.txt' % computer_name


def get_actions_file_name():
	computer_name = get_computer_name()
	return 'actions/%s_actions.txt' % computer_name


def get_counter_file_name(counter):
	computer_name = get_computer_name()
	return 'water/water-log-%s-%s.txt' % (computer_name, counter)


def get_timers_file_name():
	'''Get the file name for irrigation timers file

	Parameters
	----------

	Returns
	-------
	file_name : str
		the manual commands file name
	'''
	return 'data/timer-list.txt'


def get_faucets_file_name():
	'''Get the file name for faucets info file

	Parameters
	----------

	Returns
	-------
	file_name : str
		the manual commands file name
	'''
	return 'data/faucet-list.txt'


def get_timers(timers_file=None):
	if timers_file is None:
		timers_file = get_timers_file_name()

	timers = []
	with open(timers_file) as fl:
			ffile = csv.DictReader(fl, delimiter='\t')
			for row in ffile:
				timers.append(row)
	logger.debug('loaded %d timers' % len(timers))
	return timers


def get_current_water_file_name():
	return 'water/current_water_%s.txt' % get_computer_name()


def get_current_water():
	'''Get the current water status

	Returns
	-------
	dict {counter (str):  dict {'total': int, 'flow': int}}
	the current total water and water count for each counter on the computer
	'''
	water = {}
	try:
		with open(get_current_water_file_name()) as fl:
			wfile = csv.DictReader(fl, delimiter='\t')
			for row in wfile:
				water[row['counter']] = {}
				water[row['counter']]['total'] = row['total']
				water[row['counter']]['flow'] = row['flow']
	except Exception as err:
		logger.warning('error reading water file. %s' % err)
	return water


def get_status():
	'''Get the open/close status of the faucets

	Returns
	-------
	set of faucets that are open
	'''
	open_faucets = set()
	try:
		with open(get_status_file_name()) as fl:
			for cline in fl:
				open_faucets.add(cline.rstrip())
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
	with open(get_manual_file_name(), 'w') as cf:
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
	with open(get_manual_file_name(), 'w') as cf:
		cf.write('close\t%s\n' % faucet)
	return 'closing  faucet %s' % faucet


@Site_Main_Flask_Obj.route('/close_all', methods=['GET'])
@requires_auth
def close_all():
	'''Close all faucets now
	'''
	logger.debug('manual close all faucets')
	with open(get_manual_file_name(), 'w') as cf:
		cf.write('closeall\tcloseall\n')
	return 'closing all faucets!'


@Site_Main_Flask_Obj.route('/quit', methods=['GET'])
@requires_auth
def quit():
	'''Close all faucets now
	'''
	logger.debug('quit')
	with open(get_manual_file_name(), 'w') as cf:
		cf.write('quit\tquit\n')
	return 'quitting irrigation computer'


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
			faucet_list += fname + ';'
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
	output = []
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
	info = ''
	with open(get_faucets_file_name()) as fl:
		ffile = csv.DictReader(fl, delimiter='\t')
		for row in ffile:
			if row['name'] != faucet:
				continue
			for ck, cv in row.items():
				info += '%s:%s;' % (ck, cv)
	if info == '':
		info = '%s not found' % faucet
	return info


@Site_Main_Flask_Obj.route('/', methods=['GET'])
@requires_auth
def main_site():
	wpage = render_template('main.html')
	wpage += '<table>'
	wpage += '<thead><tr><th>Name</th><th>Computer</th><th>Relay</th><th>Duration</th><th>Status</th></tr></thead>'
	wpage += '<tbody>'
	faucets = _faucets_info()
	open_faucets = get_status()
	for cfaucet in faucets:
		cname = cfaucet.get('name', 'NA')
		ccomputer = cfaucet.get('computer_name', 'NA')
		crelay = cfaucet.get('relay', 'NA')
		cduration = cfaucet.get('default_duration', 'NA')
		if cname in open_faucets:
			cstatus = 'Open'
		else:
			cstatus = 'Closed'
		wpage += '<tr>'
		wpage += '<td>%s</td>' % cname
		wpage += '<td>%s</td>' % ccomputer
		wpage += '<td>%s</td>' % crelay
		wpage += '<td>%s</td>' % cduration
		wpage += '<td>%s</td>' % cstatus
		wpage += '<td><button id=".button-test" type="button" onclick="open_faucet(\'%s\')">open</button></td>' % cname
		wpage += '<td><button id=".button-test" type="button" onclick="close_faucet(\'%s\')">close</button></td>' % cname
		wpage += '</tr>'
	wpage += '</tbody></table>'
	wpage += 'Water:<br>'
	counter_water = get_current_water()
	for ccounter, cvals in counter_water.items():
		wpage += 'Counter: %s, Water: %s, Flow: %s' % (ccounter, cvals['total'], cvals['flow'])
	wpage += '</body>'
	wpage += '</html>'
	return wpage


@Site_Main_Flask_Obj.route('/schedule', methods=['GET'])
@requires_auth
def schedule():
	days = ['Time', 'Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat']
	timers = get_timers()
	schedule = {}
	for cday in days:
		schedule[cday] = defaultdict(list)
	for ctimer in timers:
		cday = int(ctimer.get('start_day', 0))
		if cday == 0:
			continue
		if 'start_hour' not in ctimer:
			continue
		cstart_hour = int(ctimer['start_hour'])
		if 'start_minute' not in ctimer:
			continue
		cstart_minute = int(ctimer['start_minute'])
		cduration = int(ctimer['duration'])
		# for i in range(np.ceil(cduration / 60)):
		for i in range(round((cduration+30) / 60)):
			schedule[days[cday]][cstart_hour + i].append(ctimer)
	wpage = render_template('main.html')
	wpage += '<div>'
	wpage += '<table border="3px solid purple">'
	wpage += '<thead><tr>'
	for cday in days:
		wpage += '<th>%s</th>' % cday
	wpage += '</tr></thead>'
	wpage += '<tbody>'
	hours = []
	for chour in range(24):
		hours.append(chour)
	for chour in hours:
		wpage += '<tr>'
		wpage += '<td>%s</td>' % chour
		for cday in days:
			if cday == days[0]:
				continue
			else:
				if chour in schedule[cday]:
					relay_nums = []
					for crelay in schedule[cday][chour]:
						relay_nums.append(crelay.get('faucet_num', 'NA'))
					relay_nums = ','.join(relay_nums)
					wpage += '<td onClick="document.location.href=\'http://127.0.01:5000\';">%s</td>' % relay_nums
				else:
					wpage += '<td onClick="document.location.href=\'http://127.0.01:5000\';"></td>'
		wpage += '</tr>'
	wpage += '</tbody></table>'
	wpage += '</div>'
	wpage += '<div>'
	wpage += 'Water:<br>'
	counter_water = get_current_water()
	for ccounter, cvals in counter_water.items():
		wpage += 'Counter: <a href="waterlog/%s">%s</a>, Water: %s, Flow2: %s' % (ccounter, ccounter, cvals['total'], cvals['flow'])
	wpage += '<br>last actions:<br>'
	wpage += '<select size="10">'
	last_actions = get_last_lines(get_actions_file_name(), 20)
	for caction in last_actions:
		wpage += "<option>%s</option>" % caction
	wpage += "</select>"
	wpage += '</div>'
	wpage += '</div>'
	wpage += '</body>'
	wpage += '</html>'
	return wpage


def get_stats_from_log(end_time=None, period=7, actions_log_file=None):
	'''Get the per faucet statistics based on the actions log file

	Parameters
	----------
	end_time: datetime or None, optional
		the end time for the analysis period. None for the current datetime
	period: int, optional
		the period (back from the end_time) to get the stats (in days).
	actions_log_file: str or None, optional
		name of the actions log file to analyze. None to use the current computer log file

	Returns
	-------
	dict of {line_name (str): list of dict {'date':datetime, 'flow':list of float, 'water': list of float}}
	'''
	if actions_log_file is None:
		actions_log_file = get_actions_file_name()
	if end_time is None:
		end_time = datetime.datetime.now()
	start_time = end_time - datetime.timedelta(days=period)
	actions = defaultdict(list)
	with open(actions_log_file) as fl:
		for cline in fl:
			# get the log file parameters.
			# [0]: datetime of event
			# [1]: remotely or empty
			# [2]: faucet name
			# [3]: water
			# [4]: flow
			res = re.search('(\d+-\d+-\d+ \d+:\d+:\d+) (.*)closed faucet (.*) water (.*) median flow (.*)', cline)
			if res is None:
				continue
			try:
				event_time = datetime.datetime.strptime(res.groups()[0], "%Y-%m-%d %H:%M:%S")
			except Exception as err:
				logger.debug('failed to read date time from actions log file. line is: %s' % cline)
				continue
			if event_time <= start_time or event_time > end_time:
				continue
			try:
				cfaucet = res.groups()[2]
				cwater = float(res.groups()[3])
				cflow = float(res.groups()[4])
			except:
				continue
			if cflow < 0:
				continue
			if cwater < 0:
				continue
			caction = {'date': event_time, 'flow': cflow, 'water': cwater}
			actions[cfaucet].append(caction)
	return actions


def get_water_log(counter, end_time=None, period=14, actions_log_file=None):
	'''Get the water counter reads log for the counter

	Parameters
	----------
	counter: str
		the water counter name
	period: int, optional
		the period in days to get the reads for (back from the end_time)
	actions_log_file: str, optional
		the file to get the reads from.
		If None, use the file for counter

	Returns
	-------
	(times: list of int, water_reads: list of float)
	'''
	if actions_log_file is None:
		actions_log_file = get_counter_file_name(counter)
	if end_time is None:
		end_time = datetime.datetime.now()
	start_time = end_time - datetime.timedelta(days=period)
	times = []
	water_reads = []
	with open(actions_log_file) as fl:
		for cline in fl:
			try:
				cres = cline.split('\t')
				# event_time = datetime.datetime.strptime(cres[0], "%Y-%m-%d %H:%M:%S")
				event_time = datetime.datetime.strptime(cres[0],"%a %b %d %H:%M:%S %Y")
				if event_time <= start_time or event_time > end_time:
					continue
				cwater = float(cres[1])
				# cflow = float(cres[2])
				times.append(event_time.timestamp())
				water_reads.append(cwater)
			except Exception as err:
				print(err)
				continue
	return (times, water_reads)


def draw_counter_water_plot(xdat, ydat, title=None):
	try:
		plt.hold(False)
		logger.debug('draw counter_water_plot')
		fig = plt.figure()
		points = plt.plot(xdat, ydat, 'o-')
		plt.ylabel('total water (l)')
		xticks = []
		currentday = 'na'
		xtickpos = []
		xticklabels = []
		for ctime in xdat:
			xticks.append(time.strftime('%d/%m/%Y %H:%M', time.gmtime(ctime)))
			newday = time.strftime('%d', time.gmtime(ctime))
			if newday != currentday:
				currentday = newday
				xtickpos.append(ctime)
				xticklabels.append(newday)
				print(newday)
		# print(xticks)
		plt.xticks(xtickpos, xticklabels)
		mpld3.plugins.connect(fig, mpld3.plugins.PointLabelTooltip(points[0], labels=xticks))
		plt.xlabel('time (secs)')
		if title:
			plt.title(title)

		res = mpld3.fig_to_html(fig, no_extras=False)
		plt.close(fig)
		return res
	except Exception as err:
		logger.warning('error when running draw_counter_water_plot:%s' % err)
		return None


def draw_barchart(ydat, labels, xlabel=None):
	try:
		# plt.hold(False)
		logger.debug('draw bar chart')
		fig = plt.figure()
		xdat = np.arange(len(ydat))
		plt.barh(xdat, ydat, tick_label=labels)
		if xlabel:
			plt.ylabel(xlabel)

		res = mpld3.fig_to_html(fig, no_extras=False)
		plt.close(fig)
		return res
	except Exception as err:
		logger.warning('error when running draw_barchart:%s' % err)
		return None


@Site_Main_Flask_Obj.route('/stats', methods=['GET'])
@requires_auth
def stats():
	actions = get_stats_from_log(period=1000)
	median_flows = []
	median_water = []
	lines = []
	for cline, cactions in actions.items():
		if len(cactions) == 0:
			continue
		lines.append(cline)
		cflows = [x['flow'] for x in cactions]
		median_flows.append(np.median(cflows))
		cwater = [x['water'] for x in cactions]
		median_water.append(np.sum(cwater))

	flow_bars = draw_barchart(median_flows, lines, 'median flow')
	water_bars = draw_barchart(median_water, lines, 'total water')

	wpart = ''
	wpart += 'Flow<br>'
	wpart += flow_bars
	wpart += '<br>Total water<br>'
	wpart += water_bars
	# wpart += render_template('plot.html', flow_plot=flow_bars, water_plot=water_bars)

	return wpart


@Site_Main_Flask_Obj.route('/waterlog/<counter>', methods=['GET'])
@requires_auth
def waterlog(counter):
	times, water_reads = get_water_log(counter)
	water_lines = draw_counter_water_plot(times, water_reads, 'counter %s' % counter)
	# return water_bars

	wpart = 'Flow for counter: %s<br>' % counter
	wpart += water_lines
	# wpart += render_template('plot_counter_water.html', water_plot=water_bars)

	return wpart
