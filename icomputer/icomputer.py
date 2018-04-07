import configparser
import csv
import logging
import time
import datetime
import os
from collections import defaultdict
import traceback

import numpy as np

from .faucet import get_faucet_class
from .timers import Timer, WeeklyTimer, SingleTimer

logger = logging.getLogger(__name__)


def set_log_level(level):
	logger.setLevel(level)


class IComputer:
	# faucets associated with the computer (dict of faucet.Faucet). Keyed by name
	faucets = {}
	# timers list (list of timers.Timer)
	timers = []
	# water counters. Keyed by name
	counters = {}
	# number of faucets open concurrently for each water counter
	# key is water counter name
	num_open = {}
	# the name for the actions log file
	actions_log_file = None
	# the name for the immediate commands file
	commands_file = None
	# file containing the expected status of the faucets
	status_file = None
	# True if computer is disabled, False if not disabled (should irrigate)
	disabled = False

	def __init__(self, icomputer_conf_file='computer-config.txt'):
		logger.debug('init icomputer')
		self.computer_name = 'local'
		self.icomputer_config_file = icomputer_conf_file
		# load the irrigation computer config file
		if icomputer_conf_file is not None:
			self.read_config_file(icomputer_conf_file)
		logger.debug('initializing computer %s' % self.computer_name)
		if self.actions_log_file is None:
			self.actions_log_file = os.path.join('actions', self.computer_name + '_actions.txt')
		if self.status_file is None:
			self.status_file = os.path.join('actions', self.computer_name + '_status.txt')
		if self.commands_file is None:
			self.commands_file = os.path.join('actions', self.computer_name + '_commands.txt')
		# for the manual commands file, do not read it if already exists - just the updates
		try:
			self.commands_file_timestamp = os.stat(self.commands_file).st_mtime
		except:
			self.commands_file = None
			self.commands_file_timestamp = int(time.time())

		# load the faucets file
		self.read_faucets()
		# load the timers file
		self.read_timers()
		# load the water counters file
		self.read_counters()

	def __repr__(self):
		return "Computer: " + ', '.join("%s: %s" % item for item in vars(self).items())

	def read_counters(self, counters_file='data/counter-list.txt'):
		'''
		Load the water counters cofiguration file in to the computer class counter list
		:param counters_file: str (optional)
			name of the TSV file containing the water counter information. should contain the following columns:
				name (str) : name of the counter
				computer (str) : name of the computer the counter is connected to
				type (str) : type of counter. can be:
					'numato' : io pins of the numato relay board
					'pi' : gpio pins of the raspberry pi
					'arduino' : arduino connected counter (use image button_test)
				channel : int
					the channel the counter is connected to (0 is pin #0, etc.)
				voltage (optional) : int or 'none'
					the pin used to output voltage for counter, or 'none' to not output voltage
		:return:
		'''
		logger.info('read counters from file %s' % counters_file)
		self.counters = {}
		with open(counters_file) as fl:
			ffile = csv.DictReader(fl, delimiter='\t')
			for row in ffile:
				if 'voltage' not in row:
					voltage_pin = None
				else:
					voltage_pin = row['voltage']
				ttype = row['type']
				computer_name = row['computer']
				if computer_name != self.computer_name:
					continue
				name = row['name']
				if ttype == 'arduino':
					from .counter_arduino import CounterArduino
					ccounter = CounterArduino(name=name, computer_name=computer_name, iopin=row['channel'])
				elif ttype == 'numato':
					from .counter_numato import CounterNumato
					ccounter = CounterNumato(iopin=row['channel'], voltage_pin=voltage_pin)
				elif ttype == 'pi':
					from .counter_pi import CounterPi
					ccounter = CounterPi()
				else:
					logger.warning('counter type %s for counter %s unknown' % (ttype, row['name']))
					continue
				self.counters[name] = ccounter
		self.counters_file = counters_file
		self.counters_file_timestamp = os.stat(self.counters_file).st_mtime

	def read_faucets(self, faucets_file='data/faucet-list.txt'):
		'''Load faucets information from config file into the computer class faucet dict

		Parameters
		----------
		faucets_file : str (optional)
			name of TSV file containing faucet information. should contain the following columns:
				name (str) : name of faucet
				computer (str) : name of computer to which the faucet is connected
				type (str) : type of relay (connected to the computer) to which the faucet is connected. can be:
					'XXX'
					'YYY'
				relay (str) : name of the relay
				port (str): the port on the relay for the faucet
		'''
		logger.info('read faucets from file %s' % faucets_file)
		self.close_all()
		self.faucets = {}
		with open(faucets_file) as fl:
			ffile = csv.DictReader(fl, delimiter='\t')
			for row in ffile:
				faucet_type = row['faucet_type']
				fname = row['name']
				if fname in self.faucets:
					logger.warning('faucet %s already defined' % fname)
					continue
				faucet_class = get_faucet_class(faucet_type)
				cfaucet = faucet_class(local_computer_name=self.computer_name, **dict(row))
				logger.info('added faucet %s' % cfaucet)
				self.faucets[fname] = cfaucet
		self.faucets_file = faucets_file
		self.faucets_file_timestamp = os.stat(self.faucets_file).st_mtime

	def read_timers(self, timers_file='data/timer-list.txt'):
		'''Load timers information from config file into the computer class timers list

		Parameters
		----------
		timers_file : str (optional)
			name of TSV file containing timer information. should contain the following columns:
				faucet (str) : name of faucet
				type (str) : type of timers. can be:
					'weekly' : a day specific timer (auto renews every week)
					'single' : a timer that goes off once in the given date/time
				duration (int): the duration of the timer irrigation in minutes
		'''
		logger.info('read timers from file %s' % timers_file)
		self.close_all()
		self.timers = []
		with open(timers_file) as fl:
			ffile = csv.DictReader(fl, delimiter='\t')
			for row in ffile:
				cfaucetname = row['faucet']
				if cfaucetname not in self.faucets:
					logger.warning('faucet %s for timer not in computer faucet list' % cfaucetname)
					continue
				ttype = row['type']
				if ttype == 'weekly':
					start_time = datetime.time(hour=int(row['start_hour']), minute=int(row['start_minute']))
					ctimer = WeeklyTimer(duration=row['duration'], cfaucet=self.faucets[cfaucetname], start_day=row['start_day'], start_time=start_time)
				elif ttype == 'single':
					start_datetime = datetime.datetime(year=int(row['start_year']), month=int(row['start_month']), day=int(row['start_date']), hour=int(row['start_hour']), minute=int(row['start_minute']))
					ctimer = SingleTimer(duration=row['duration'], cfaucet=self.faucets[cfaucetname], start_datetime=start_datetime)
				else:
					ctimer = Timer(row['duration'], self.faucets[cfaucetname])
				logger.debug('added timer %s' % ctimer)
				self.timers.append(ctimer)
		self.timers_file = timers_file
		self.timers_file_timestamp = os.stat(self.timers_file).st_mtime

	def read_config_file(self, filename):
		'''Read the config file for the irrigation computer

		Parameters
		----------
		filename : str
			name of the config file

		the config file contains the following information:
			computer_name : str
				name of the irrigation computer (relays are associated with computer_name)
			file_check_interval : int
				interval for checking file change (seconds)
			disabled : bool
				True to disable irrigation from this computer, False to enable
		'''
		logger.debug('read config file %s' % filename)
		config = configparser.ConfigParser()
		config.read(filename)
		for k, v in config['IComputer'].items():
			setattr(self, k, v)
		if config.has_option('IComputer','disabled'):
			self.disabled = config.getboolean('IComputer','disabled')

	def write_config_file(self):
		'''Write the computer config from self

		Writes to the config file name stored in self.icomputer_config_file
		See read_config_file() doc for config file information
		'''
		filename = self.icomputer_config_file
		logger.debug('write config file %s' % filename)
		if filename is None:
			logger.warning('no computer config file set. cannot write')
			return
		config = configparser.ConfigParser()
		# first read all values (so we don't accidently something)
		config.read(filename)
		config['IComputer']['disabled'] = str(self.disabled)
		config['IComputer']['computer_name'] = self.computer_name
		with open(filename, 'w') as fl:
			config.write(fl)
		logger.debug('wrote config file %s' % filename)

	def read_manual_commands(self, commands_file=None):
		'''
		Read the manual commands file

		commands are tab separated between arguments, newline between commands.
		can include:
		open faucet_name(str)
			manually open the faucet for the default faucet duration
		close faucet_name(str)
			manually close faucet and delete single timer
		closeall JUNK(str)
			manually close all faucets
		disable computer_name(str)
			move computer to "disable" mode (close all faucets and don't turn any on until enable)
		enable computer_name(str)
			enable irrigation from computer
		set_percent percent(number+'%'')
			change all irrigation times by percent compared to the real program (100% - original, <100% less, 200% twice long irrigations...)

		:param commands_file:  str or None (optional)
			file name of the commands file. None to use the default (computer_name + '_commands.txt')
		:return:
		'''
		if commands_file is None:
			commands_file = self.commands_file
		with open(commands_file) as cf:
			for cline in cf:
				cline = cline.strip().split('\t')
				if len(cline)!=2:
					logger.warning('Manual command %s does not contain 2 columns' % cline)
					continue
				ccommand = cline[0].lower()
				param = cline[1]
				if ccommand == 'open':
					cfaucet = param
					if cfaucet not in self.faucets:
						logger.warning('cannot open faucet %s - not found' % cfaucet)
						logger.warning('current faucets: %s' % self.faucets)
						continue
					new_timer = SingleTimer(duration=self.faucets[cfaucet].default_duration, cfaucet=self.faucets[cfaucet], start_datetime=None, is_manual=True)
					self.timers.append(new_timer)
					if self.is_faucet_on_computer(self.faucets[cfaucet]):
						logger.info('created manual single timer for faucet: %s' % cfaucet)
					else:
						logger.info('cannot open. faucet %s not on this computer' % cfaucet)
				elif ccommand == 'close':
					cfaucet = param
					if cfaucet not in self.faucets:
						logger.warning('cannot close faucet %s - not found' % cfaucet)
						continue
					the_faucet = self.faucets[cfaucet]
					if the_faucet.counter != 'none':
						if the_faucet.counter in self.counters:
							total_water = self.counters[the_faucet.counter].get_count() - the_faucet.start_water
						else:
							logger.debug('counter %s for faucet %s not found' % (the_faucet.counter, cfaucet))
							total_water = -1
					else:
						total_water = -1
					self.write_action_log('manually closed faucet %s, water=%d' % (cfaucet, total_water))
					self.faucets[cfaucet].close()
					if self.is_faucet_on_computer(self.faucets[cfaucet]):
						logger.info('manually closed faucet %s' % cfaucet)
					else:
						logger.warning('cannot close. faucet %s not on this computer' % cfaucet)
					delete_list=[]
					for ctimer in self.timers:
						if ctimer.faucet!=self.faucets[cfaucet]:
							continue
						if not isinstance(ctimer, SingleTimer):
							continue
						if not ctimer.is_manual:
							continue
						delete_list.append(ctimer)
					self.delete_timers(delete_list)
				elif ccommand == 'closeall':
					self.close_all()
					delete_list=[]
					for ctimer in self.timers:
						if not isinstance(ctimer, SingleTimer):
							continue
						if not ctimer.is_manual:
							continue
						delete_list.append(ctimer)
					self.delete_timers(delete_list)
					logger.info('closed all faucets (manual)')
				elif ccommand == 'disable':
					computer_name = param
					logger.debug('manual disable computer %s' % computer_name)
					if computer_name == self.computer_name:
						self.disabled = True
						self.write_config_file()
						logger.info('computer %s disabled' % computer_name)
						# close all currently open faucets
						self.close_all()
						# and delete the manual timers
						delete_list=[]
						for ctimer in self.timers:
							if not isinstance(ctimer, SingleTimer):
								continue
							if not ctimer.is_manual:
								continue
							delete_list.append(ctimer)
						self.delete_timers(delete_list)
					else:
						logger.debug('cannot disable computer %s since not this computer (%s)' % (computer_name, self.computer_name))
				elif ccommand == 'enable':
					computer_name = param
					logger.debug('manual enable computer %s' % computer_name)
					if computer_name == self.computer_name:
						self.disabled = False
						self.write_config_file()
						logger.info('computer %s enabled' % computer_name)
					else:
						logger.debug('cannot enable computer %s since not this computer (%s)' % (computer_name, self.computer_name))
				else:
					logger.warning('Manual command %s not recognized' % cline)
					continue
		self.commands_file = commands_file
		self.commands_file_timestamp = os.stat(commands_file).st_mtime

	def write_action_log(self, msg):
		with open(self.actions_log_file, 'a') as fl:
			fl.write('%s ' % datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
			fl.write(msg)
			fl.write('\n')

	def write_status_file(self, should_be_open):
		with open(self.status_file, 'w') as fl:
			for cfaucet_name in should_be_open:
				fl.write(cfaucet_name+'\n')

	def delete_timers(self, delete_list):
		'''
		Delete timers from the timer list
		:param delete_list: list of timers
			timers to delete
		:return:
		'''
		if len(delete_list) == 0:
			return
		self.timers = [x for x in self.timers if x not in delete_list]
		logger.debug('deleted %d timers' % len(delete_list))

	def get_name(self):
		'''Get the computer name

		Returns
		-------
		str : computer name
			as defined in the config file
		'''
		return self.computer_name

	def is_faucet_on_computer(self, faucet):
		'''
		Check if the faucet is on this irrigation computer
		:param faucet:
		:return:
		True if faucet is on self irrigation computer
		False otherwise
		'''
		if self.computer_name == faucet.computer_name:
			return True
		return False

	def is_counter_on_computer(self, counter):
		'''
		Check if the counter is connected to this irrigation computer
		:param counter:
		:return:
		True if counter is on self irrigation computer
		False otherwise
		'''
		if self.computer_name == counter.computer_name:
			return True
		return False

	def close_all(self):
		'''Close all faucets on the computer
		'''
		logger.debug('closing all faucets')
		for cfaucet in self.faucets.values():
			cfaucet.close()

	def write_water_log_counter(self, counter, faucet_name=None, water_dir='water'):
		'''Write the faucet/counter water count to the log file.
		Note by default it writes the counter file, and if faucet is not None, it writes the faucet file.

		Parameters
		----------
		counter: Counter
			the Counter from where to get the water total/flow values
		faucet_name: str or None (optional)
			None to write to faucet file or str to to write the water info for the given faucet name
		water_dir: str (optional)
			the directory where to write the file
		'''
		# if we don't have the output directory, create it
		if not os.path.exists(water_dir):
			os.makedirs(water_dir)
		if faucet_name is None:
			file_name = os.path.join(water_dir, 'water-log-%s-%s.txt' % (self.computer_name, counter.name))
		else:
			file_name = os.path.join(water_dir, 'water-log-faucet-%s-%s.txt' % (faucet_name, self.computer_name))
		with open(file_name, 'a') as cfl:
			cfl.write('%s\t%d\t%f\n' % (time.asctime(), counter.get_count(), counter.flow))
			logger.debug('logged counter %s count %d flow %f' % (counter.name, counter.last_water_read, counter.flow))

	def main_loop(self):
		done = False
		ticks = 0
		old_should_be_open = set()
		while not done:
			# logger.debug('tick')

			# find out which faucets should be open (OR on all timers)
			should_be_open = set()
			num_open = defaultdict(list)
			delete_list = []
			for ctimer in self.timers:
				if ctimer.should_be_open():
					# add this faucet to the list of open faucets for this timer
					num_open[ctimer.faucet.counter].append(ctimer.faucet.name)
					# add faucet to the list of all faucets which should be open now (on all computers)
					should_be_open.add(ctimer.faucet.name)
				if ctimer.should_remove():
					delete_list.append(ctimer)

			# if the faucets that should be opened changed, write the status file (local faucets only?)
			if should_be_open != old_should_be_open:
				self.write_status_file(should_be_open)
				old_should_be_open = should_be_open

			# add the indication for faucets that are open but with another faucet on the same water counter
			# first all are alone
			for cfaucet in self.faucets.values():
				cfaucet.all_alone = True

			# now mark as not alone ones on a counter with more than one faucet open
			for ccounter, faucets in num_open.items():
				if len(faucets) > 1:
					for cfaucet in faucets:
						self.faucets[cfaucet].all_alone = False

			# go over all faucets and open/close as needed
			for cfaucet in self.faucets.values():
				if cfaucet.isopen:
					# if it is open and should close, close it
					if cfaucet.name not in should_be_open:
						# if faucet on local computer, actually close it, otherwise pretend to close it
						cfaucet.close()
						if self.is_faucet_on_computer(cfaucet):
							action_str = 'closed'
						else:
							action_str = 'closed remotely'
						logger.info('%s faucet %s' % (action_str, cfaucet.name))

						if cfaucet.counter != 'none':
							if cfaucet.counter in self.counters:
								total_water = self.counters[cfaucet.counter].get_count() - cfaucet.start_water
							else:
								logger.debug('counter %s for faucet %s not found' % (cfaucet.counter, cfaucet.name))
								total_water = -1
							if len(cfaucet.flow_counts)>0:
								median_flow = np.median(cfaucet.flow_counts)
							else:
								median_flow = 'was not alone'
						else:
							total_water = -1
							median_flow = 'no counter'
						logger.debug('total water %d' % total_water)
						if cfaucet.all_alone:
							logger.debug('was all alone')
							self.write_action_log('%s faucet %s water %d median flow %s' % (action_str, cfaucet.name, total_water, median_flow))
						else:
							logger.debug('was NOT all alone')
							self.write_action_log('%s faucet %s not alone water %d median flow %s' % (action_str, cfaucet.name, total_water, median_flow))
					else:
						if cfaucet.all_alone:
							if cfaucet.counter != 'none':
								cfaucet.flow_counts.append(self.counters[cfaucet.counter].flow)
				else:
					# if it is closed and should open, open it
					if cfaucet.name in should_be_open:
						if self.disabled:
							if self.is_faucet_on_computer(cfaucet):
								logger.debug('computer disabled. not opening faucet %s' % cfaucet.name)
								continue
						# if faucet on local computer, actually open it. otherwise, pretend to open it
						cfaucet.open()
						cfaucet.flow_counts = []
						if self.is_faucet_on_computer(cfaucet):
							action_str = 'opened'
						else:
							action_str = 'opened remotely'
						cfaucet.start_water = -1
						logger.info('%s faucet %s' % (action_str, cfaucet.name))
						if cfaucet.counter in self.counters:
							ccounter = self.counters[cfaucet.counter]
							logger.debug('found counter %s. start water for faucet %s: %s' % (ccounter.name, cfaucet.name, cfaucet.start_water))
							cfaucet.start_water = ccounter.get_count()
						self.write_action_log('%s faucet %s start water=%d' % (action_str, cfaucet.name, cfaucet.start_water))

			# delete timers in the delete list
			self.delete_timers(delete_list)

			# go over water counters and write the per counter water log file
			if ticks % 60 == 0:
				for ccounter in self.counters.values():
					if ccounter.computer_name != self.computer_name:
						continue
					# write water log
					self.write_water_log_counter(ccounter)

			# write the current per-counter water details to the current water status file (for website)
			if ticks % 60 == 0:
				with open('water/current_water_%s.txt' % self.computer_name,'w') as fl:
					fl.write('counter\ttotal\tflow\n')
					for ccounter in self.counters.values():
						if ccounter.computer_name != self.computer_name:
							continue
						# write counter info
						fl.write('%s\t%s\t%s\n' % (ccounter.name, ccounter.last_water_read, ccounter.flow))

			# per line water usage (if open alone on a counter)
			if ticks % 60 == 0:
				for ccounter in self.counters.values():
					# only on counters on this computer
					if ccounter.computer_name != self.computer_name:
						continue
					# are any faucets on this counter open?
					if ccounter.name not in num_open:
						logger.debug('no open faucets for counter %s (not in num_open)' % ccounter.name)
						continue
					# is more than one faucet on this counter open?
					if len(num_open[ccounter.name]) > 1:
						logger.debug('more than one open for counter %s: %s' % (ccounter.name, num_open[ccounter.name]))
						continue
					# write water log
					cur_faucet_name = num_open[ccounter.name][0]
					self.write_water_log_counter(ccounter, faucet_name=cur_faucet_name)

			# check for changed files
			# check manual open/close file
			# if not self.commands_file_timestamp == os.stat(self.commands_file).st_mtime:
			# 	logger.debug('Loading manual commands file')
			# 	self.read_manual_commands(self.commands_file)
			try:
				if not self.commands_file_timestamp == os.stat(self.commands_file).st_mtime:
					logger.debug('Loading manual commands file')
					self.read_manual_commands(self.commands_file)
			except Exception as err:
				logger.warning('manual commands file %s load failed. error: %s' % (self.commands_file, err))
				logger.warning(traceback.format_exc())
				self.commands_file_timestamp = int(time.time())
			# if not self.faucets_file_timestamp == os.stat(self.faucets_file).st_mtime:
			# 	pass
			# check faucet list file
			if not self.faucets_file_timestamp == os.stat(self.faucets_file).st_mtime:
				logger.debug('faucets file changed')
				self.read_faucets(self.faucets_file)
				self.read_timers(self.timers_file)
			# check timers file
			if not self.timers_file_timestamp == os.stat(self.timers_file).st_mtime:
				logger.debug('timers file changed')
				self.read_timers(self.timers_file)

			# update keepalive file
			if ticks % 60 == 0:
				# logger.debug('keepalive')
				pass

			# sleep
			time.sleep(1)
			ticks += 1
