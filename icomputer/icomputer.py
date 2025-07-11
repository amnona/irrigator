import configparser
import csv
import logging
import time
import datetime
import os
from collections import defaultdict
import traceback
import sys

from .faucet import get_faucet_class
from .timers import Timer, WeeklyTimer, SingleTimer
from .utils import send_email

logger = logging.getLogger(None)


def set_log_level(level):
	logger.setLevel(level)


class IComputer:
	# faucets associated with the computer (dict of faucet.Faucet). Keyed by name
	faucets = {}
	# timers list (list of timers.Timer)
	timers = []
	# water counters. Keyed by name
	counters = {}
	# fertilization pumps. Keyed by name
	pumps = {}

	# number of faucets open concurrently for each water counter
	# key is water counter name
	num_open = {}
	# the name for the actions log file
	actions_log_file = None
	# the name for the immediate commands file
	commands_file = None
	# file containing the expected status of the faucets
	status_file = None

	def __init__(self, icomputer_conf_file='computer-config.txt', read_only=False):
		'''Initialize the irrigation computer
		loads the faucet, timer, counters and pumps

		Parameters
		----------
		read_only: bool, optional
			False (default) to be a fully working irrigation computer
			True to not write anything to the relays
		'''
		logger.debug('init icomputer')
		self.init_state_params()
		self.computer_name = 'local'
		self.read_only = read_only

		# monitoe leaks mode. if True, do not report faucets not opening - just leaks (and assume no faucets should open)
		# can be set via "monitor_leaks True" in actions config file
		self.monitor_leaks = False

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
			logger.warning('commands file %s not found' % self.commands_file)
			self.commands_file = None
			self.commands_file_timestamp = int(time.time())

		# load the faucets file
		self.read_faucets(read_only=read_only)
		# load the timers file
		self.read_timers()
		# load the water counters file
		self.read_counters()
		# load the fertilization pumps file
		self.read_pumps()
		# set the irrigation mode (can be 'auto' or 'manual')
		self.mode = 'auto'
		# load the state commands file (disabled computers etc.)
		self.read_state_commands()

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
					'fake' : a fake software counter for testing. has the field fake_flow (per second)
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
				counts_per_liter = row.get('counts_per_liter', 1.0)
				if ttype == 'arduino':
					from .counter_arduino import CounterArduino
					ccounter = CounterArduino(name=name, computer_name=computer_name, iopin=row['channel'], counts_per_liter=counts_per_liter)
				elif ttype == 'numato':
					from .counter_numato import CounterNumato
					ccounter = CounterNumato(iopin=row['channel'], voltage_pin=voltage_pin, counts_per_liter=counts_per_liter)
				elif ttype == 'pi':
					from .counter_pi import CounterPi
					ccounter = CounterPi()
				elif ttype == 'fake':
					from .counter_fake import CounterFake
					ccounter = CounterFake(name=name, computer_name=computer_name, iopin=row['channel'], counts_per_liter=counts_per_liter, fake_flow=row.get('fake_flow', 0))
				else:
					logger.warning('counter type %s for counter %s unknown' % (ttype, row['name']))
					continue
				self.counters[name] = ccounter
		self.counters_file = counters_file
		self.counters_file_timestamp = os.stat(self.counters_file).st_mtime
		logger.info('read %d counters from file %s' % (len(self.counters), counters_file))


	def read_faucets(self, faucets_file='data/faucet-list.txt', read_only=False):
		'''Load faucets information from config file into the computer class faucet dict

		Parameters
		----------
		faucets_file : str (optional)
			name of TSV file containing faucet information. should contain the following columns:
				name (str) : name of faucet
				idx (int): the index of the faucet (for quick reference)
				computer_name (str) : name of computer to which the faucet is connected
				type (str) : type of relay (connected to the computer) to which the faucet is connected. can be:
					'NumatoFaucet'
					'FakeFaucet'
				counter (str): name of the water counter (from counters.txt) measuting this line or 'na' if no counter connected
				normal_flow (float): the expected flow for the faucet. if water is significantly higher/lower than the normal_flow, we get an email warning
				relay (str) : name of the relay
				port (str): the port on the relay for the faucet
				default_duration (float): default irrigation time for the faucet (used for manual open and adding new timer)
				fertilization_pump (str): name of the fertilization pump associated with this line (from pump-list.txt) or 'na' if no pump on this line
				fertilize (str): 'yes' to apply fertilization or 'no' to not fertilize
		read_only: bool, optional
			True to not write anything to the faucets (for monitoring)
		'''
		logger.info('read faucets from file %s' % faucets_file)
		if not read_only:
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
				cfaucet = faucet_class(local_computer=self, read_only=read_only, **dict(row))
				logger.info('added faucet %s' % cfaucet)
				self.faucets[fname] = cfaucet
		self.faucets_file = faucets_file
		self.faucets_file_timestamp = os.stat(self.faucets_file).st_mtime

	def read_pumps(self, pumps_file='data/pump-list.txt'):
		'''Load fertilization pump information from config file into the computer class faucet dict

		Parameters
		----------
		pump_file : str (optional)
			name of TSV file containing pump information. should contain the following columns:
				name (str) : name of pump (used in faucet-list.txt)
				computer_name (str) : name of computer to which the pump relay is connected
				type (str) : type of relay (connected to the computer) to which the faucet is connected. can be:
					'NumatoFaucet'
					'FakeFaucet'
				relay (str) : name of the relay
				port (str): the port on the relay for the faucet
				pre_close_time (float): time before closing the faucet to close the pump (min)
		'''
		logger.info('read pumps config from file %s' % pumps_file)
		self.close_all()
		self.pumps = {}
		with open(pumps_file) as fl:
			ffile = csv.DictReader(fl, delimiter='\t')
			for row in ffile:
				faucet_type = row['faucet_type']
				fname = row['name']
				if fname in self.pumps:
					logger.warning('pump %s already defined' % fname)
					continue
				faucet_class = get_faucet_class(faucet_type)
				cpump = faucet_class(local_computer=self, **dict(row))
				logger.info('added pump %s' % cpump)
				self.pumps[fname] = cpump
		self.pumps_file = pumps_file
		self.pumps_file_timestamp = os.stat(self.pumps_file).st_mtime

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
		if config.has_option('IComputer', 'disabled'):
			self.disabled = config.getboolean('IComputer', 'disabled')

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

		:param commands_file:  str or None (optional)
			file name of the commands file. None to use the default (computer_name + '_commands.txt')
		:return:
		'''
		if commands_file is None:
			commands_file = self.commands_file
		logger.debug('read manual commands from file %s' % commands_file)
		with open(commands_file) as cf:
			for cline in cf:
				cline = cline.strip().split('\t')
				if len(cline) != 2:
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
					if self.faucets[cfaucet].is_local():
						logger.info('created manual single timer for faucet: %s' % cfaucet)
					else:
						logger.info('cannot open. faucet %s not on this computer' % cfaucet)

				elif ccommand == 'close':
					cfaucet = param
					if cfaucet not in self.faucets:
						logger.warning('cannot close faucet %s - not found' % cfaucet)
						continue
					self.faucets[cfaucet].close()
					# the_faucet = self.faucets[cfaucet]
					# self.write_action_log('manually closed faucet %s, water=%d, flow=%s' % (cfaucet, the_faucet.get_total_water(), the_faucet.get_median_flow()))
					# self.faucets[cfaucet].close()

					# if self.faucets[cfaucet].is_local():
					# 	logger.info('manually closed faucet %s' % cfaucet)
					# else:
					# 	logger.warning('cannot close. faucet %s not on this computer' % cfaucet)
					delete_list = []
					for ctimer in self.timers:
						if ctimer.faucet != self.faucets[cfaucet]:
							continue
						if not isinstance(ctimer, SingleTimer):
							continue
						if not ctimer.is_manual:
							continue
						delete_list.append(ctimer)
					self.delete_timers(delete_list)

				elif ccommand == 'closeall':
					self.close_all()
					delete_list = []
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
						delete_list = []
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

				elif ccommand == 'mode':
					mode = param
					logger.info('changing mode to %s' % param)
					self.mode = mode

				elif ccommand == 'quit':
					logger.warning('quitting')
					self.close_all()
					sys.exit()

				else:
					logger.warning('Manual command %s not recognized' % cline)
					continue
		self.commands_file = commands_file
		self.commands_file_timestamp = os.stat(commands_file).st_mtime

	def init_state_params(self):
		logger.debug('Initialized state_params')
		'''Initialize all the state commands related parameters to default values
		'''
		# True if computer is disabled, False if not disabled (should irrigate)
		self.disabled = False
		# set of disabled fertilization pump names
		self.disable_fertilization = set()
		# Fraction to modify all irrigation timers (1 to not change)
		self.duration_correction = 1
		# a set of disabled faucets (names - str)
		self.disabled_faucets = set()

	def read_state_commands(self, state_commands_file='actions/irrigation-state-commands.txt'):
		'''Read the state commands file
		TODO: write this

		This file contains commands that are always applied (not deleted).
		This includes disabling/enabling computer / lines, changing irrigation durations by percentage, disbaling/enabling fertilization, etc.

		commands are tab separated between arguments, newline between commands.
		can include:
		'#' - comment line
		disable_computer computer_name(str)
			move computer to "disable" mode (close all faucets and don't turn any on until enable)
		set_percent percent(number+'%'')
			change all irrigation times by percent compared to the real program (100% - original, <100% less, 200% twice long irrigations...)
		disable_line line_name(str)
			skip all irrigations for this line
		disable_fertilization fertilization_pump(str)
			disable all fertilization by this pump
		force_fertilization fertilization_pump(str)
			force fertilization for all lines using this pump
		mode manual/auto
			'manual' - Ignore all automatic (timer) open commands, open only using manual commands (and automatically close)
			'auto' - Use the timers

		:param state_commands_file:  str or None (optional)
			file name of the commands file. None to use the default ('actions/irrigation-state-commands.txt')

		:return:
		'''
		try:
			logger.debug('read state commands from file %s' % state_commands_file)
			# first reset all state parameters (since we're reloading the state file)
			self.init_state_params()
			# if state commands file doesn't exist, create it
			# (should be copied from irrigation-state-commands.default.txt)
			if not os.path.exists(state_commands_file):
				with open(state_commands_file, 'w'):
					logger.warning('irrigation state commands file %s does not exist, create' % state_commands_file)
			with open(state_commands_file) as cf:
				for cline in cf:
					cline = cline.strip()
					if len(cline) == 0:
						continue
					cline = cline.split('\t')
					if len(cline) == 0:
						continue
					ccommand = cline[0].lower()
					if len(cline) > 1:
						param = cline[1].lower()

					# if comment - next line
					if ccommand[0] == '#':
						continue

					if ccommand == 'disable_computer':
						computer_name = param
						logger.debug('manual disable computer %s' % computer_name)
						if computer_name == self.computer_name:
							self.disabled = True
							logger.info('computer %s disabled from state_commands_file' % computer_name)
							# close all currently open faucets
							self.close_all()
							# and delete the manual timers
							delete_list = []
							for ctimer in self.timers:
								if not isinstance(ctimer, SingleTimer):
									continue
								if not ctimer.is_manual:
									continue
								delete_list.append(ctimer)
							self.delete_timers(delete_list)
						else:
							logger.debug('cannot disable computer %s since not this computer (%s)' % (computer_name, self.computer_name))
					elif ccommand == 'monitor_leaks':
						logger.info('Change to monitor state %s' % param)
						if param == 'True':
							self.monitor_leaks = True
						else:
							self.monitor_leaks = False
					elif ccommand == 'disable_line':
						logger.info('disable line %s' % param)
						self.disabled_faucets.add(param)
					elif ccommand == 'disable_fertilization':
						self.disable_fertilization.add(param)
					elif ccommand == 'set_percent':
						if param[-1] != '%':
							logger.warning('set_percent in state-commands file needs to end with "%"')
							continue
						try:
							percent = float(param[:-1])
						except Exception as err:
							logger.warning('failed to convert to float set_percent in state-commands file: error %s' % err)
							continue
						if percent < 0 or percent > 1000:
							logger.warning('set_percent in state-commands supplied percent (%f) too small or too big' % percent)
							continue
						self.duration_correction = percent / 100
						logger.info('percent irrigation updated to %f' % percent)
					elif ccommand == 'mode':
						mode = param
						logger.info('changing mode to %s' % param)
						self.mode = mode
					else:
						logger.warning('Manual command %s not recognized' % cline)
						continue
		except Exception as err:
			logger.warning('Error reading state command file %s.\n%s' % (state_commands_file, err))
		self.state_commands_file = state_commands_file
		self.state_commands_file_timestamp = os.stat(state_commands_file).st_mtime

	def write_action_log(self, msg):
		logger.debug('write action log: %s' % msg)
		with open(self.actions_log_file, 'a') as fl:
			fl.write('%s ' % datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
			fl.write(msg)
			fl.write('\n')

	def write_status_file(self, should_be_open):
		logger.debug('write status file %s' % self.status_file)
		with open(self.status_file, 'w') as fl:
			for cfaucet_name in should_be_open:
				fl.write(cfaucet_name + '\n')

	def delete_timers(self, delete_list):
		'''
		Delete timers from the timer list
		:param delete_list: list of timers
			timers to delete
		:return:
		'''
		logger.debug('delete %d timers' % len(delete_list))
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

	def close_all(self):
		'''Close all faucets and fertilization pumps on the computer
		'''
		logger.debug('closing all faucets and pumps')
		for cfaucet in self.faucets.values():
			cfaucet.close(force=True)
		for cpump in self.pumps.values():
			cpump.close(force=True)

	def write_keep_alive_file(self):
		'''write the current time to the keep alive file.
		So we can see the computer is running.
		'''
		logger.debug('write keep alive file')
		file_name = os.path.join('actions', '%s_keep_alive.txt' % self.computer_name)
		with open(file_name, 'w') as fl:
			fl.write('%s' % time.asctime())

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
		logger.debug('write water log for counter %s' % counter.name)
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

	def write_short_water_log_counter(self, counter, n=30, faucet_name=None, water_dir='water'):
		'''Write the faucet/counter water count to the log file containing only the last n reads.
		Note by default it writes the counter file, and if faucet is not None, it writes the faucet file.

		Parameters
		----------
		counter: Counter
			the Counter from where to get the water total/flow values
		n: int (optional)
			the number of last reads to write to the file
		faucet_name: str or None (optional)
			None to write to faucet file or str to to write the water info for the given faucet name
		water_dir: str (optional)
			the directory where to write the file
		'''
		logger.debug('write short water log for counter %s' % counter.name)
		# if we don't have the output directory, create it
		if not os.path.exists(water_dir):
			os.makedirs(water_dir)
		if faucet_name is None:
			file_name = os.path.join(water_dir, 'water-short-log-%s-%s.txt' % (self.computer_name, counter.name))
		else:
			file_name = os.path.join(water_dir, 'water-short-log-faucet-%s-%s.txt' % (faucet_name, self.computer_name))
		# read the file and keep only the last n lines
		last_reads = []
		if os.path.exists(file_name):
			with open(file_name, 'r') as cfl:
				for line in cfl:
					last_reads.append(line.strip())
		# keep only the last n-1 reads
		if len(last_reads) >= n:
			last_reads = last_reads[-n:]
		# add the current read
		last_reads.append('%s\t%d\t%f' % (time.asctime(), counter.get_count(), counter.flow))
		# write the last n reads to the file
		with open(file_name, 'w') as cfl:
			for line in last_reads:
				cfl.write(line + '\n')
		logger.debug('logged short (%d) counter %s count %d flow %f' % (n, counter.name, counter.last_water_read, counter.flow))


	def main_loop(self):
		done = False

		# time counter (seconds)
		ticks = 0
		# the faucets that should be open before the closing of needed faucets
		old_should_be_open = set()

		# a list of water reads per counter. used to detect water leaks
		leak_check_counter_water = defaultdict(list)
		# how many non zero counts we need to decide a leak is happening
		leak_check_nunber_tests = 4
		# interval for leak checks (seconds)
		leak_check_interval = 5 * 60
		# for the daily total water report
		last_daily_water_count = defaultdict(float)
		irrigation_report_timers = '--------------------\n'
		last_daily_water_day = datetime.datetime.now().day

		logger.info('sending irrigator started email')
		send_email('amnonim@gmail.com', 'irrigator started', 'computer name is %s' % self.computer_name)
		logger.info('starting main loop for computer %s' % self.computer_name)

		while not done:
			# logger.debug('tick')

			# find out which faucets should be open (OR on all timers)
			should_be_open = set()
			num_open = defaultdict(list)
			delete_list = []
			for ctimer in self.timers:
				# if we are in manual mode, ignore the weekly timers open command
				if self.mode == 'manual':
					if isinstance(ctimer, WeeklyTimer):
						continue
				if ctimer.should_be_open(self.duration_correction):
					# add this faucet to the list of open faucets for this timer
					num_open[ctimer.faucet.counter].append(ctimer.faucet.name)
					# add faucet to the list of all faucets which should be open now (on all computers)
					should_be_open.add(ctimer.faucet.name)
				if ctimer.should_remove():
					delete_list.append(ctimer)

			# check which fertilization pumps should be open
			fertilizer_should_be_open = set()
			fertilizer_should_be_closed = set()
			for ctimer in self.timers:
				# the faucet needs to be open
				if not ctimer.should_be_open(self.duration_correction):
					continue
				cfaucet = ctimer.faucet
				logger.debug('fertilize - faucet %s open' % cfaucet.name)
				# need to have the fertilization pump
				cpump = cfaucet.fertilization_pump
				if cpump not in self.pumps:
					logger.debug('fertilize - pump %s does not exist from faucet %s' % (cpump, cfaucet.name))
					continue
				# if this is an open faucet which is connected to the pump and should not be fertilized, should not open the pump
				if cfaucet.fertilize != 'yes':
					logger.debug('fertilize - pump %s should be always closed from faucet %s' % (cpump, cfaucet.name))
					fertilizer_should_be_closed.add(cpump)
					continue
				# if we have < 10 minutes to closing time, pump should be closed
				if ctimer.time_to_close(self.duration_correction) < 10 * 60:
					fertilizer_should_be_closed.add(cpump)
					logger.debug('fertilize - pump %s should be closed since %f time left is not enough from faucet %s' % (cpump, ctimer.time_to_close(self.duration_correction), cfaucet.name))
					continue
				# so faucet with the pump is open, should fertilize and has enough time before closing, lets open the pump
				logger.debug('fertilize - pump %s should be open from faucet %s' % (cpump, cfaucet.name))
				fertilizer_should_be_open.add(cpump)
			# now lets remove all the pumps that should be closed
			fertilizer_should_be_open = fertilizer_should_be_open.difference(fertilizer_should_be_closed)

			# and let's open all the pumps that need to be open and close the other ones
			for cpump in self.pumps:
				if cpump in fertilizer_should_be_open:
					if cpump in self.disable_fertilization:
						logger.debug('Fertilization pump %s disabled. Not opening.' % cpump)
						irrigation_report_timers += 'did not open fertilization pump %s since it is disabled\n' % cpump
						continue
					if not self.pumps[cpump].isopen:
						logger.info('fertilizer - opening pump %s' % cpump)
					self.pumps[cpump].open()
				else:
					if self.pumps[cpump].isopen:
						logger.info('fertilizer - closing pump %s' % cpump)
						irrigation_report_timers += 'fertilized with pump %s for %f minuntes\n' % (cpump, self.pumps[cpump].get_time_since_open())
					self.pumps[cpump].close()

			# if the faucets that should be opened changed, write the status file (local faucets only?)
			if should_be_open != old_should_be_open:
				self.write_status_file(should_be_open)
				old_should_be_open = should_be_open

			# add the indication for faucets that are open but with another faucet on the same water counter
			# first all are alone.
			# all_alone is for the current read, all_alone_all_time is for the whole open-close period
			for cfaucet in self.faucets.values():
				cfaucet.all_alone = True

			# now mark as not alone ones on a counter with more than one faucet open
			for ccounter, faucets in num_open.items():
				if len(faucets) > 1:
					logger.debug('more than one faucet: %s' % faucets)
					for cfaucet in faucets:
						self.faucets[cfaucet].all_alone = False
						self.faucets[cfaucet].all_alone_all_time = False

			# go over all faucets and open/close as needed
			for cfaucet in self.faucets.values():
				if cfaucet.isopen:
					# if it is open and should close, close it
					if cfaucet.name not in should_be_open:
						# if faucet on local computer, actually close it, otherwise pretend to close it
						logger.info('closing faucet %s' % cfaucet.name)
						irrigation_report_timers += 'closed faucet %s duration %d min, total water %f L, median flow %f L/hour\n' % (cfaucet.name, 0, cfaucet.get_total_water(), cfaucet.get_median_flow())
						cfaucet.close(force=True)
					else:
						# if open and should be open, if it is alone, add the water count
						cfaucet.add_flow_count()
				else:
					# if it is closed and should open, open it
					if cfaucet.name in should_be_open:
						if self.disabled:
							if cfaucet.is_local():
								logger.info('computer disabled. not opening faucet %s' % cfaucet.name)
								irrigation_report_timers += 'did not open faucet %s since computer %s is disabled\n' % (cfaucet.name, self.computer_name)
								continue
						if cfaucet.name in self.disabled_faucets:
							if cfaucet.is_local():
								logger.info('faucet %s disabled. not opening' % cfaucet.name)
								irrigation_report_timers += 'did not open faucet %s since computer line is disabled\n' % cfaucet.name
								continue
						# if faucet on local computer, actually open it. otherwise, pretend to open it
						logger.info('opening faucet %s' % cfaucet.name)
						cfaucet.open(force=True)

			# delete timers in the delete list
			self.delete_timers(delete_list)

			# go over water counters and write the per counter water log file
			if ticks % 60 == 0:
				for ccounter in self.counters.values():
					if ccounter.computer_name != self.computer_name:
						continue
					# write water log
					self.write_water_log_counter(ccounter)

			# write the short water log file (last 30 reads) (for website)
			if ticks % 60 == 0:
				for ccounter in self.counters.values():
					if ccounter.computer_name != self.computer_name:
						continue
					# write short water log
					self.write_short_water_log_counter(ccounter)

			# write the current per-counter water details to the current water status file (for website)
			if ticks % 60 == 0:
				with open('water/current_water_%s.txt' % self.computer_name, 'w') as fl:
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

			# leak check
			if ticks % leak_check_interval == 0:
				logger.debug('leak check')
				for ccounter in self.counters.values():
					# only on counters on this computer
					if ccounter.computer_name != self.computer_name:
						continue
					# are any faucets on this counter open?
					# do this check only if not in monitor_leaks mode (monitor leaks mode assumes no faucets should be open)
					if not self.monitor_leaks:
						if ccounter.name in num_open:
							logger.debug('faucets open on counter %s. test skipped' % ccounter.name)
							continue
						logger.debug('leak check - no faucets open for %s' % ccounter.name)

					# add current water read to list of flows for the current counter
					cleak = leak_check_counter_water[ccounter.name]
					# get the per minute flow
					cleak.append(ccounter.get_count())
					if len(cleak) > leak_check_nunber_tests:
						cleak.pop(0)

					# test if we have a leak
					num_leak = 0
					leak_flows = []
					for idx in range(len(cleak) - 1):
						if cleak[idx + 1] - cleak[idx] <= 0:
							break
						leak_flows.append((cleak[idx + 1] - cleak[idx]) * 60 / leak_check_interval)
						num_leak += 1
					if num_leak >= leak_check_nunber_tests - 1:
						logger.warning('leak detected for faucet %s')
						msg = 'computer name: %s\n' % self.computer_name
						msg += 'counter name: %s\n' % ccounter.name
						msg += 'reads (read interval is %s):\n%s\n' % (leak_check_interval, cleak)
						msg += 'flows (read interval is %s):\n%s\n' % (leak_check_interval, leak_flows)
						send_email('amnonim@gmail.com', 'leak detected', msg)

			# do the daily water report
			ctime = datetime.datetime.now()
			if ctime.day != last_daily_water_day:
				irrigation_report = ''
				if ctime.hour >= 8:
					last_daily_water_day = ctime.day
					for ccounter in self.counters.values():
						if ccounter.computer_name != self.computer_name:
							continue
						irrigation_report += 'counter %s total daily water: %f\n' % (ccounter.name, ccounter.last_water_read - last_daily_water_count[ccounter.name])
						last_daily_water_count[ccounter.name] = ccounter.last_water_read
					irrigation_report += irrigation_report_timers
					send_email('amnonim@gmail.com', 'daily irrigation report', irrigation_report)
					irrigation_report_timers = '--------------------\n'
					last_daily_water_day = ctime.day

			# check for changed files
			# check manual open/close file
			try:
				if not self.commands_file_timestamp == os.stat(self.commands_file).st_mtime:
					logger.debug('Loading manual commands file')
					self.read_manual_commands(self.commands_file)
			except Exception as err:
				logger.warning('manual commands file %s load failed. error: %s' % (self.commands_file, err))
				logger.warning(traceback.format_exc())
				self.commands_file_timestamp = int(time.time())
			# check for state commands change (disable computer etc.)
			if not self.state_commands_file_timestamp == os.stat(self.state_commands_file).st_mtime:
				logger.info('State commands file changed. reloading')
				self.read_state_commands()
			# check faucet list file
			if not self.faucets_file_timestamp == os.stat(self.faucets_file).st_mtime:
				logger.info('faucets file changed')
				self.read_faucets(self.faucets_file)
				self.read_timers(self.timers_file)
			# check timers file
			if not self.timers_file_timestamp == os.stat(self.timers_file).st_mtime:
				logger.info('timers file changed')
				self.read_timers(self.timers_file)
			# check fertilization pumps list file
			if not self.pumps_file_timestamp == os.stat(self.pumps_file).st_mtime:
				logger.info('pumps file changed')
				self.read_pumps(self.pumps_file)
				self.read_faucets(self.faucets_file)
				self.read_timers(self.timers_file)

			# update keepalive file
			if ticks % 60 == 0:
				self.write_keep_alive_file()
				pass

			# sleep
			time.sleep(1)
			ticks += 1
