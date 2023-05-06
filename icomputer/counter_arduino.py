import logging
import datetime

import serial
import os

from .counter import Counter

logger = logging.getLogger(__name__)


MIN_FLOW_INTERVAL = 45


class CounterArduino(Counter):
    def __init__(self, name, computer_name, iopin, serial_name=None, counts_per_liter=1):
        super().__init__(name=name, computer_name=computer_name)
        self.iopin = iopin
        if serial_name is None:
            serial_name = self.get_serial_port()
        self.serial_name = serial_name
        self.counts_per_liter = float(counts_per_liter)
        self.last_water_read = -1
        self.last_water_time = datetime.datetime.now()
        self.flow = -1
        self.serial = None
        self.clear_count()

    def get_serial_port(self):
        try:
            # find and set the correct port name
            dev_list_dir = '/dev/serial/by-id/'
            port_names = [os.path.join(dev_list_dir, x) for x in os.listdir(dev_list_dir)]
            port_names = [x for x in port_names if 'usb-Arduino' in x]
            if len(port_names) == 0:
                logger.warning('no Arduino connected. cannot contact counter %s' % self.name)
                return None
            if len(port_names) > 1:
                logger.warning('found more than one Arduino (%d) connected to counter %s' % (len(port_names), self.name))
            found_port = port_names[0]
            logger.debug('Found serial port %s for counter %s' % (found_port, self.name))
            return found_port
        except Exception as err:
            logger.debug('Did not find serial port. error %s' % err)
            return None

    def open_serial(self):
        '''Get the USB(serial) port connection for the arduino and set it in self.serial

        if it already exists, return it. If not, try to connect

        Returns
        -------
            None if connection failed, otherwise the serial port
        '''
        if self.serial is not None:
            return self.serial
        self.serial_name = self.get_serial_port()
        try:
            self.serial = serial.Serial(self.serial_name, 9600, timeout=1)
        except serial.serialutil.SerialException:
            self.serial = None
            logger.warning('could not open serial port %s' % self.serial_name)
        return self.serial

    def get_count(self):
        '''Get the water count for the counter.
        Also updates the self.flow if time from last read > MIN_FLOW_INTERVAL

        Returns:
        --------
            int - the water count
        '''
        command = 'r' + str(self.iopin) + '\n'
        if self.open_serial() is None:
            return self.count
        self.serial.write(command.encode())
        try:
            count = self.serial.readline()
        except serial.SerialTimeoutException:
            logger.warning('did not get response from serial %s' % self.serial_name)
            # reset the serial port - maybe next time we need to reconnect?
            # self.serial = None
            return self.count
        try:
            self.count = int(count)
        except:
            logger.debug('count read conversion to int failed. count was: %s (counter %s, serial %s)' % (count, self.name, self.serial_name))
            return self.count

        # correct for the number of counts per liter, so we are in liter units
        self.count = self.count / self.counts_per_liter

        logger.debug('new count for %s pin %s: %d' % (self.serial_name, self.iopin, self.count))
        ctime = datetime.datetime.now()
        time_delta = (ctime - self.last_water_time).seconds
        if time_delta > MIN_FLOW_INTERVAL:
            # if we had a problem reading (or first read), flow will be 0
            if self.last_water_read == -1:
                self.last_water_read = self.count
            self.flow = (self.count - self.last_water_read) * 60 / time_delta
            logger.debug('flow for %s: %f (current %f, last %f, time %f)' % (self.name, self.flow, self.count, self.last_water_read, time_delta))
            self.last_water_time = ctime
            self.last_water_read = self.count
        return self.count

    def clear_count(self):
        '''Set the count to 0'''
        try:
            command = 'c' + str(self.iopin) + '\n'
            if self.open_serial() is None:
                return
            self.serial.write(command.encode())
            new_count = self.get_count()
            if new_count != 0:
                logger.warning('clear counts failed for %s port %s. count is %d' % (self.serial_name, self.iopin, self.count))
                return
            logger.info('reset water counter %s port %s' % (self.serial_name, self.iopin))
        except Exception as err:
            logger.warning('clear counts failed for %s port %s. error %s' % (self.name, self.iopin, err))
            return