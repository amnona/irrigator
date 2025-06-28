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

from icomputer import IComputer


# import numpy as np

logger = getLogger('iserver')

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
	try:
		with open(filename, 'rb') as fl:
			fl.seek(-num_lines * max_line_len, os.SEEK_END)
			lines = fl.readlines()
			out_lines = []
			for x in range(min(num_lines, len(lines))):
				out_lines.append(lines[-(x + 1)].decode().strip())
		return out_lines
	except:
		return ['Error reading file %s' % filename]

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
	'''Get the timers list from the timers data file

	Parameters
	----------
	timers_file: str, optional
		name of the timers file to parse, or None to get the default file from the computer

	Returns
	-------
	list of dict:
		entry for each line in the timers file. keys are the headers of the tsv file
		(should include "faucet_num", "faucet", "type", "duration", etc.
	'''
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
	icomputer = IComputer(read_only=True)
	# get the next irrigation times
	next_time = {}
	for ctimer in icomputer.timers:
		ctimer_name = ctimer.faucet.name
		cnext_irrigation = ctimer.get_next_irrigation()
		if ctimer_name in next_time:
			if next_time[ctimer_name] < cnext_irrigation:
				continue
		next_time[ctimer_name] = cnext_irrigation

	# get the last irrigation times
	print(get_actions_file_name())
	last_times = {}
	last_actions = get_last_lines(get_actions_file_name(), 200)
	for caction in last_actions[::-1]:
		print(caction)
		a = caction.split('opened faucet ')
		print(a)
		if len(a) != 2:
			continue
		action_faucet = a[1]
		action_time_str = a[0].split(' remotely ')[0].strip()
		# same format as the write_action_log() command in icomputer
		try:
			last_times[action_faucet] = datetime.datetime.strptime(action_time_str, '%Y-%m-%d %H:%M:%S')
		except:
			last_times[action_faucet] = datetime.datetime.now()
		print(caction)
		print(action_faucet)
		print(action_time_str)

	skip_remote = False
	wpage = render_template('main.html')
	if icomputer.mode == 'manual':
		wpage += '<h2 style="background-color:red;">Manual mode</h2><br>'
	wpage += '<table>'
	wpage += '<thead><tr><th>Name</th><th>Duration</th><th>Status</th><th>Last</th><th>Next</th></tr></thead>'
	wpage += '<tbody>'
	open_faucets = get_status()
	for cfaucet in icomputer.faucets.values():
		if skip_remote:
			if not cfaucet.is_local():
				continue
		cname = cfaucet.name
		cduration = cfaucet.default_duration
		if cname in open_faucets:
			cstatus = 'Open'
		else:
			cstatus = 'Closed'
		wpage += '<tr>'
		cline = '<td>%s</td>' % cname
		if not skip_remote:
			if not cfaucet.is_local():
				# cline = '<td style="background-color:#0077FF">%s</td>' % cname
				cline = '<td><s>%s</s></td>' % cname
		wpage += cline
		wpage += '<td>%s</td>' % cduration
		if cstatus == 'Open':
			wpage += '<td style="background-color:#00FF00">Open</td>'
		elif cstatus == 'Closed':
			wpage += '<td style="background-color:#0000FF">Closed</td>'
		else:
			wpage += '<td style="background-color:#FF0000">%s</td>' % cstatus
		wpage += '<td>%s</td>' % get_last_irrigation_str(last_times.get(cname, None))
		wpage += '<td>%s</td>' % get_next_irrigation_time_str(next_time.get(cname, None))
		# wpage += '<td>%s</td>' % cstatus
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


def get_next_irrigation_time_str(next_time):
	'''Get a string describing the next irrigation time

	Parameters
	----------
	next_time: datetime.datetime
		the time of the next irrigation

	Returns
	-------
	str: (i.e. 'today night' or 'tomorrow evening' etc)
	'''
	if next_time is None:
		return 'NA'

	ctime = datetime.datetime.now()
	# we set the current time to 5am, so anything until 5am is <1day away
	ctime = ctime.replace(hour=4, minute=59, second=0)

	tstart_hour = next_time.time().hour

	day_diff = (next_time - ctime).days

	if tstart_hour < 5:
		timestr = 'night'
	elif tstart_hour < 8:
		timestr = 'morning'
	elif tstart_hour < 17:
		timestr = 'day'
	elif tstart_hour < 20:
		timestr = 'evening'
	else:
		timestr = 'night'

	if day_diff <= 0:
		daystr = 'today'
	elif day_diff == 1:
		daystr = 'tomorrow'
	else:
		daystr = 'in %d days' % day_diff

	ntime = daystr + ' ' + timestr
	if ntime == 'today night':
		ntime = 'tonight'
	return ntime


def get_last_irrigation_str(last_time):
	'''Get a string representation of the last irrigation time (in hours or days)
	Parameters
	----------
		last_time: datetime.datetime

	Returns
	-------
		str (for example '2 hours' or '5 days')
	'''
	if last_time is None:
		return 'NA'
	ctime = datetime.datetime.now()
	ti = ctime - last_time
	if ti.days < 0:
		return 'future'
	hours = ti.days * 24 + ti.seconds / 3600
	print('------')
	if hours < 48:
		print(hours)
		print(ti)
		print(last_time)
		print(ctime)
		print('%d Hours' % int(hours))
		return '%d Hours' % int(hours)
	print(ti)
	print(last_time)
	print(ctime)
	print('%d Days' % ti.days)
	return '%d Days' % ti.days


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
		for i in range(round((cduration + 30) / 60)):
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
	logger.debug('get_stats_from_log')
	if actions_log_file is None:
		actions_log_file = get_actions_file_name()
	if end_time is None:
		end_time = datetime.datetime.now()
	start_time = end_time - datetime.timedelta(days=period)
	logger.debug('using log file %s, period %s, end_time %s' % (actions_log_file, period, end_time))
	actions = defaultdict(list)
	num_lines = 0
	num_out_of_range = 0
	num_bad_format = 0
	num_water_problem = 0
	parsing_problems = 0
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
				# parse the date/time part
				# we don't use strptime since has problems with raspberry pi locale en-IL
				tt = res.groups()[0].split(' ')
				dpart = tt[0].split('-')
				tpart = tt[1].split(':')
				event_time = datetime.datetime(year=int(dpart[0]), month=int(dpart[1]), day=int(dpart[2]), hour=int(tpart[0]), minute=int(tpart[1]))
				# event_time = datetime.datetime.strptime(res.groups()[0], "%Y-%m-%d %H:%M:%S")
			except Exception as err:
				if parsing_problems == 0:
					logger.debug('failed to read date time from actions log file. line is: %s' % cline)
					logger.debug(err)
					logger.debug(res.groups()[0])
				parsing_problems += 1
				continue
			num_lines += 1
			if event_time <= start_time or event_time > end_time:
				num_out_of_range += 1
				continue
			try:
				cfaucet = res.groups()[2]
				cwater = float(res.groups()[3])
				cflow = float(res.groups()[4])
			except:
				num_bad_format += 1
				continue
			if cflow < 0:
				num_water_problem += 1
				continue
			if cwater < 0:
				num_water_problem += 1
				continue
			caction = {'date': event_time, 'flow': cflow, 'water': cwater}
			actions[cfaucet].append(caction)
	logger.debug('read %d ok lines from log file' % num_lines)
	logger.debug('got %d out of date range' % num_out_of_range)
	logger.debug('got %d bad format' % num_bad_format)
	logger.debug('got %d water problems' % num_water_problem)
	logger.debug('got %d parsing problems' % parsing_problems)
	return actions


def get_water_log(counter, end_time=None, period=14, actions_log_file=None):
	'''Get the water counter reads log for the counter

	Parameters
	----------
	counter: str
		the water counter name
	end_time: datetime or None, optional
		the end time for the analysis period. None for the current datetime
	period: int, optional
		the period in days to get the reads for (back from the end_time)
	actions_log_file: str, optional
		the file to get the reads from.
		If None, use the file for counter

	Returns
	-------
	(err: str or None if ok, times: list of int, water_reads: list of float)
	'''
	if actions_log_file is None:
		actions_log_file = get_counter_file_name(counter)
	if end_time is None:
		end_time = datetime.datetime.now()
	start_time = end_time - datetime.timedelta(days=period)
	times = []
	water_reads = []
	try:
		with open(actions_log_file) as fl:
			for cline in fl:
				try:
					cres = cline.split('\t')
					# event_time = datetime.datetime.strptime(cres[0], "%Y-%m-%d %H:%M:%S")
					event_time = datetime.datetime.strptime(cres[0], "%a %b %d %H:%M:%S %Y")
					if event_time <= start_time or event_time > end_time:
						continue
					cwater = float(cres[1])
					# cflow = float(cres[2])
					times.append(event_time.timestamp())
					water_reads.append(cwater)
				except Exception as err:
					print(err)
					continue
		return (None,times, water_reads)
	except:
		logger.warning('could not read water log file %s' % actions_log_file)
		return ('counter %s does not have the water log file %s' % (counter, actions_log_file),[], [])


def draw_counter_water_plot(xdat, ydat, title=None):
	try:
		# plt.hold(False)
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
		return None, res
	except Exception as err:
		logger.warning('error when running draw_counter_water_plot:%s' % err)
		return 'error when running draw_counter_water_plot:%s' % err, None


def draw_barchart(ydat, labels, xlabel=None):
	try:
		# plt.hold(False)
		logger.debug('draw bar chart')
		fig = plt.figure()
		xdat = np.arange(len(ydat))
		plt.barh(xdat, ydat, tick_label=labels)
		if xlabel:
			logger.debug('adding xlabel %s' % xlabel)
			plt.xlabel(xlabel)

		res = mpld3.fig_to_html(fig, no_extras=False)
		plt.close(fig)
		return res
	except Exception as err:
		logger.warning('error when running draw_barchart:%s' % err)
		return None


@Site_Main_Flask_Obj.route('/stats', methods=['GET'])
@requires_auth
def stats():
	period = 7
	actions = get_stats_from_log(period=period)
	median_flows = []
	median_water = []
	lines = []
	logger.debug('got %d actions' % len(actions))
	for cline, cactions in actions.items():
		if len(cactions) == 0:
			logger.debug('caction len is 0 for line %s' % cline)
			continue
		logger.debug('prcoessing line %s' % cline)
		lines.append(cline)
		cflows = [x['flow'] for x in cactions]
		median_flows.append(np.median(cflows) * 60)
		cwater = [x['water'] for x in cactions]
		median_water.append(np.sum(cwater))

	flow_bars = draw_barchart(median_flows, lines, 'median flow (Liter/Hour)')
	water_bars = draw_barchart(median_water, lines, 'total water for last %d days (Liter)' % period)

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
	err, times, water_reads = get_water_log(counter)
	if err is not None:
		logger.warning(err)
		return err
	err, water_lines = draw_counter_water_plot(times, water_reads, 'counter %s' % counter)
	if err is not None:
		logger.warning('error when drawing water plot: %s' % err)
		return err

	# return water_bars
	wpart = 'Flow for counter: %s<br>' % counter
	wpart += water_lines
	# wpart += render_template('plot_counter_water.html', water_plot=water_bars)

	return wpart


@Site_Main_Flask_Obj.route('/faucetlog/<line>', methods=['GET'])
@requires_auth
def faucetlog(line):
	logger.debug('getting faucetlog for line %s' % line)
	actions = get_stats_from_log(period=1000)
	if line not in actions:
		return('line %s not in actions file' % line)
	line_actions = actions[line]
	logger.info('found %d actions for line' % len(line_actions))
	flows = []
	times = []
	water = []
	for caction in line_actions:
		flows.append(caction['flow'] * 60)
		water.append(caction['water'])
		times.append(caction['date'].strftime("%d/%m"))
	logger.debug('generating graphs')
	flow_bars = draw_barchart(flows, times, 'flow (Liter/Hour)')
	water_bars = draw_barchart(water, times, 'total water (Liter)')
	logger.debug('finished')
	wpart = ''
	wpart += 'Actions summary for line %s<br><br>' % line
	wpart += 'Flow<br>'
	wpart += flow_bars
	wpart += '<br>Total water<br>'
	wpart += water_bars

	return wpart
