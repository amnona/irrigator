import configparser
import csv
import logging
import time
import datetime
import os
from collections import defaultdict

from faucet import get_faucet_class
from timers import Timer, WeeklyTimer, SingleTimer

logger = logging.getLogger(__name__)
logger.addHandler(logging.StreamHandler())
logger.setLevel(logging.DEBUG)


class IComputer:
	# faucets associated with the computer (dict of faucet.Faucet). Keyed by name
	faucets = {}
	# timers list (list of timers.Timer)
	timers = []
	# water counters. Keyed by name
	wcounters = {}
	# number of faucets open concurrently for each water counter
	# key is water counter name
	num_open = {}
	# the name for the actions log file
	actions_log_file = None
	# the name for the immediate commands file
	commands_file = None

	def __init__(self, icomputer_conf_file='computer-config.txt'):
		logger.debug('init icomputer')
		self.computer_name = 'local'
		# load the irrigation computer config file
		if icomputer_conf_file is not None:
			self.read_config_file(icomputer_conf_file)
		print(self.computer_name)
		if self.actions_log_file is None:
			self.actions_log_file = self.computer_name + '_actions.txt'
		if self.commands_file is None:
			self.commands_file = self.computer_name + '_commands.txt'
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

	def read_counters(self, counters_file='counter-list.txt'):
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
		logger.debug('read counters from file %s' % counters_file)
		self.counters = []
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
					from counter_arduino import CounterArduino
					ccounter = CounterArduino(name=name, computer_name=computer_name, iopin=row['channel'])
				elif ttype == 'numato':
					from counter_numato import CounterNumato
					ccounter = CounterNumato(iopin=row['channel'], voltage_pin=voltage_pin)
				elif ttype == 'pi':
					from counter_pi import CounterPi
					ccounter = CounterPi()
				else:
					logger.warning('counter type %s for counter %s unknown' % (ttype, row['name']))
					continue
				self.counters.append(ccounter)
		self.counters_file = counters_file
		self.counters_file_timestamp = os.stat(self.counters_file).st_mtime

	def read_faucets(self, faucets_file='faucet-list.txt'):
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
		logger.debug('read faucets from file %s' % faucets_file)
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
				cfaucet = faucet_class(**dict(row))
				logger.debug('added faucet %s' % cfaucet)
				self.faucets[fname] = cfaucet
		self.faucets_file = faucets_file
		self.faucets_file_timestamp = os.stat(self.faucets_file).st_mtime

	def read_timers(self, timers_file='timer-list.txt'):
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
		logger.debug('read timers from file %s' % timers_file)
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
					ctimer = SingleTimer(duration=row['duration'], cfaucet=self.faucets[cfaucetname],
										 start_datetime=start_datetime)
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
		'''
		logger.debug('read config file %s' % filename)
		config = configparser.ConfigParser()
		config.read(filename)
		for k, v in config['IComputer'].items():
			setattr(self, k, v)

	def read_manual_commands(self, commands_file=None):
		'''
		Read the manual commands file
		:param commands_file:  str or None (optional)
			file name of the commands file. None to use the default (computer_name + '_commands.txt')
		:return:
		'''
		if commands_file is None:
			commands_file = self.commands_file
		with open(commands_file) as cf:
			for cline in cf:
				ccommand = cline.strip().split('\t')
				if len(ccommand)!=2:
					logger.warning('Manual command %s does not contain 2 columns' % cline)
					continue
				cfaucet = ccommand[1]
				if ccommand[0].lower()=='open':
					if cfaucet not in self.faucets:
						logger.warning('cannot open faucet %s - not found' % cfaucet)
						logger.warning('current faucets: %s' % self.faucets)
						continue
					if self.is_faucet_on_computer(self.faucets[cfaucet]):
						new_timer = SingleTimer(duration=self.faucets[cfaucet].default_duration, cfaucet=self.faucets[cfaucet], start_datetime=None, is_manual=True)
						self.timers.append(new_timer)
						logger.info('created single timer for faucet %s' % cfaucet)
					else:
						logger.warning('cannot open. faucet %s not on this computer' % cfaucet)
				elif ccommand[0].lower() == 'close':
					if cfaucet not in self.faucets:
						logger.warning('cannot close faucet %s - not found' % cfaucet)
						continue
					if self.is_faucet_on_computer(self.faucets[cfaucet]):
						self.faucets[cfaucet].close()
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
				elif ccommand[0].lower() == 'closeall':
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
				else:
					logger.warning('Manual command %s not recognized' % cline)
					continue
		self.commands_file = commands_file
		self.commands_file_timestamp = os.stat(commands_file).st_mtime

	def write_action_log(self, msg):
		with open(self.actions_log_file, 'a') as fl:
			fl.write(msg)
			fl.write('\n')

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

	def main_loop(self):
		done = False
		ticks = 0
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
					# if on this computer, add to the list of timers that should be opened locally
					if self.is_faucet_on_computer(ctimer.faucet):
						should_be_open.add(ctimer.faucet.name)
				if ctimer.should_remove():
					delete_list.append(ctimer)

			# add the indication for faucets that are open but with another faucet on the same water counter
			# first all are alone
			for cfaucet in self.faucets.values():
				cfaucet.all_alone = True
			# now mark as not alone ones on a counter with more than one faucet open
			for ccounter, faucets in num_open.items():
				if len(faucets) > 0:
					for cfaucet in faucets:
						self.faucets[cfaucet].all_alone = False

			# go over all faucets and open/close as needed
			for cfaucet in self.faucets.values():
				# if on another computer, ignore this timer
				if not self.is_faucet_on_computer(cfaucet):
					continue
				if cfaucet.isopen:
					# if it is open and should close, close it
					if cfaucet.name not in should_be_open:
						cfaucet.close()
						if cfaucet.counter != 'none':
							if cfaucet.counter in self.counters:
								total_water = self.counters[cfaucet.counter].get_count() - cfaucet.start_water
							else:
								logger.debug('counter %s for faucet %s not found' % (cfaucet.counter, cfaucet.name))
								total_water = -1
						else:
							total_water = -1
						if cfaucet.all_alone:
							self.write_action_log('closed faucet %s water %d' % (cfaucet.name, total_water))
						else:
							self.write_action_log('closed faucet %s not alone water %d' % (cfaucet.name, total_water))
				else:
					# if it is closed and should open, open it
					if cfaucet.name in should_be_open:
						cfaucet.open()
						cfaucet.start_water = -1
						for ccounter in self.counters:
							if ccounter.name == cfaucet.counter:
								cfaucet.start_water = ccounter.get_count()
						self.write_action_log('opened faucet %s start water=%d' % (cfaucet.name, cfaucet.start_water))

			# delete timers in the delete list
			self.delete_timers(delete_list)

			# go over water counters
			if ticks % 60 == 0:
				for ccounter in self.counters:
					if ccounter.computer_name != self.computer_name:
						continue
					# write water log
					with open('water-log-%s-%s.txt' % (self.computer_name, ccounter.name),'a') as cfl:
						cfl.write('%s\t%d\t%f\n' % (time.asctime(), ccounter.get_count(), ccounter.flow))
						print('Counter %s count %d flow %f' % (ccounter.name, ccounter.last_water_read, ccounter.flow))

			# per line water usage (if open alone on a counter)
			if ticks % 60 == 0:
				for ccounter in self.counters:
					if ccounter.computer_name != self.computer_name:
						continue
					# are any faucets on this counter open?
					if ccounter.name not in num_open:
						print('no open faucets for this counter (not in num_open)')
						continue
					# is more than one faucet on this counter open?
					if len(num_open[ccounter.name]) > 1:
						print('more than one open for counter %s: %s' % (ccounter.name, num_open[ccounter.name]))
						continue
					# write water log
					cur_faucet_name = num_open[ccounter.name][0]
					with open('water-log-faucet-%s-%s.txt' % (cur_faucet_name, self.computer_name), 'a') as cfl:
						cfl.write('%s\t%d\t%f\n' % (time.asctime(), ccounter.get_count(), ccounter.flow))
						print('open faucet %s count %d flow %f' % (cur_faucet_name, ccounter.get_count(), ccounter.flow))

			# check for changed files
			# check manual open/close file
			# if not self.commands_file_timestamp == os.stat(self.commands_file).st_mtime:
			# 	logger.debug('Loading manual commands file')
			# 	self.read_manual_commands(self.commands_file)
			try:
				if not self.commands_file_timestamp == os.stat(self.commands_file).st_mtime:
					logger.debug('Loading manual commands file')
					self.read_manual_commands(self.commands_file)
			except:
				logger.warning('manual commands file %s load failed' % self.commands_file)
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

			if ticks % 2 == 0:
				# logger.debug('tick2')
				pass
			# sleep
			time.sleep(1)
			ticks += 1
