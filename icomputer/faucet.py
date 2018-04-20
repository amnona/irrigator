from logging import getLogger
import importlib
import datetime
import os

import numpy as np

logger = getLogger(__name__)


def get_faucet_class(faucet_type):
	faucet_module = importlib.import_module('.' + faucet_type.lower(), 'icomputer')
	faucet_class = getattr(faucet_module, faucet_type)
	return faucet_class


class Faucet:
	# status of the faucet - True if faucet is currently open, False if closed
	isopen = False
	# timers associated with the faucet
	timers = []

	def __init__(self, name, local_computer, computer_name=None, faucet_type='generic', relay='0', counter='none', default_duration=30, **kwargs):
		'''Init the faucet

		Parameters
		----------
		name : str
			name of the faucet (i.e. 'roses drips')
		local_computer : IComputer
			the current computer.
			Note: could be different from computer_name if this faucet is connected to a different computer, since
			we are loading all faucets to all computers, but don't actually open/close it
		computer_name : str or None
			name of the computer the faucet is connected to or None to get the name from local_computer
		faucet_type : str (optional)
			the relay type - can be 'numato'
		relay_idx : str or int
			the relay in the faucet controller (i.e. 0-F for numato 16 relay board
		default_duration: int (optional)
			the default duration of the faucet when opened manually/new timer added
		'''
		self.name = name
		self.local_computer = local_computer
		if computer_name is None:
			computer_name = local_computer.computer_name
		self.computer_name = computer_name
		self.faucet_type = faucet_type
		self.relay_idx = relay
		self.counter = counter
		self.default_duration = default_duration
		self.flow_counts = []
		self.open_time = datetime.datetime.now()
		self.isopen = False
		self.all_alone_all_time = True
		self.all_alone = True
		self.start_water = -1

		# all_alone is set to True when opened, and turns False if more than one open on the same water counter
		self.all_alone = False
		logger.debug('Init faucet %s on computer %s' % (name, computer_name))

	def __repr__(self):
		return 'Faucet: %s\nfaucet_type: %s, counter: %s, default_duration: %s, computer_name: %s, relay: %s' % (self.name, self.faucet_type, self.counter, self.default_duration, self.computer_name, self.relay_idx)

	def is_local(self):
		'''Is this faucet physically connected to this computer
		'''
		if self.computer_name == self.local_computer.computer_name:
			return True
		return False

	def get_faucet_counter(self):
		'''Get the counter class of the counter where this faucet sits, or None if doesn't exist
		'''
		if self.counter == 'none':
			return None
		if self.counter not in self.local_computer.counters:
			logger.debug('counter %s not found for faucet %s' % (self.counter, self.name))
			return None
		return self.local_computer.counters[self.counter]

	def get_current_water(self):
		'''Get the current water count of the counter to where this faucet is connected
		Returns
		-------
		float, -1 if not connected to counter (or counter is not on this computer)
		'''
		ccounter = self.get_faucet_counter()
		if ccounter is None:
			logger.debug('could not get counter for faucet %s' % self.name)
			return -1
		return ccounter.get_count()

	def open(self):
		'''Open the faucet (water on)

		Returns
		-------
		True if the faucet was opened, False if an error was enountered
		'''
		logger.debug('opening faucet %s' % self.name)
		self.isopen = True
		self.all_alone = True
		self.all_alone_all_time = True
		# all the flow reads when this faucet was alone on the counter.
		# used to get the median flow of this faucet
		self.flow_counts = []
		# time when the faucet was opened
		self.open_time = datetime.datetime.now()
		# water counter read when the faucet was opened
		# used to get the total water if it was all_alone_all_time
		self.start_water = self.get_current_water()

		# write to the action log file:
		if self.is_local():
			action_str = 'opened'
		else:
			action_str = 'remotely opened'
		self.local_computer.write_action_log('%s faucet %s' % (action_str, self.name))

		# we didn't really open anything so return false
		return False

	def close(self, write_summary=True):
		'''Close the faucet (water off)

		Parameters
		----------
		write_summary: bool, optional
			True to save the open-close summary to the faucet water summary file

		Returns
		-------
		True if faucet was closed, False if a problem encountered
		'''
		self.isopen = False
		# write the water summary for this open/close session
		if write_summary:
			# write the water log only on the computer where the counter is connected
			if self.get_faucet_counter():
				self.write_water_summary()

		# write the action log file entry
		if self.is_local():
			action_str = 'closed'
		else:
			action_str = 'remotely closed'
		self.local_computer.write_action_log('%s faucet %s water %d median flow %s' % (action_str, self.name, self.get_total_water(), self.get_median_flow()))

		# we didn't really close anything here
		return False

	def get_current_flow(self):
		'''Get the current flow value from the counter

		Returns
		-------
		flow or None:
			None if cannot get the flow (no counter, or not alone)
			flow - the counts/min for the current flow
		'''
		ccounter = self.get_faucet_counter()
		if ccounter is None:
			return None
		return ccounter.flow

	def add_flow_count(self):
		'''Add the current flow to the flow count

		Only add if it is the only faucet open, and has a counter on the computer
		'''
		if not self.all_alone:
			return False
		cflow = self.get_current_flow
		if cflow is None:
			return False
		self.flow_counts.append(cflow)
		return True

	def get_median_flow(self):
		'''Get the median water flow for the faucet

		Returns
		-------
		float - the mean flow rate or -1 if cannot calculate
		'''
		if self.counter == 'none':
			logger.debug('no counter for %s' % self.name)
			return -1
		if len(self.flow_counts) < 1:
			logger.debug('not enough flow reads for %s' % self.name)
			return -1
		return '%.2f' % np.median(self.flow_counts)

	def get_total_water(self):
		'''Get the total water amount (real or estimated) for the faucet

		Returns
		-------
		-1 if cannot estimate (no flow available since was never alone or no water counter)
		'''
		if self.counter == 'none':
			logger.debug('cannot get total water - no water counter for faucet %s' % self.name)
			return -1

		# if all alone all the time - can just look at the total water count
		if self.all_alone_all_time:
			total_water = self.get_current_water() - self.start_water
			logger.debug('measured total water %f' % total_water)
			return total_water

		# was not alone all the time - need to estimate the total water
		cflow = self.get_median_flow()
		if cflow == -1:
			logger.debug('cannot get total water - no flow reads for faucet %s' % self.name)
			return -1
		predicted_water = cflow * (datetime.datetime.now() - self.open_time).total_minutes()
		logger.debug('predicted total water %f for %s' % (predicted_water, self.name))
		return predicted_water

	def write_water_summary(self):
		'''Write the faucet summary to the faucet water summary file

		writes to water/summary_faucet_XXX.txt where XXX is the faucet name
		format is:
		faucet open time, duration, alone, mean flow, total water
		'''
		summary_file_name = os.path.join('water', 'summary_faucet_' + self.name + '.txt')
		logger.debug('writing water summary into %s' % summary_file_name)
		with open(summary_file_name, 'a') as fl:
			# time the faucet was opened
			fl.write('%s\t' % self.open_time.strftime("%Y-%m-%d %H:%M:%S"))
			# total open time (minutes)
			fl.write('%f\t' % (datetime.datetime.now - self.open_time).total_minutes())
			# alone
			fl.write('%s\t' % self.all_alone)
			# mean flow
			fl.write('%f\t' % self.get_median_flow())
			# total water
			fl.write('%f\n' % self.get_total_water())
