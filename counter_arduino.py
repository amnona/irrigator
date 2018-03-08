from logging import getLogger
import datetime

import serial

from counter import Counter

logger = getLogger(__name__)

MIN_FLOW_INTERVAL = 60


class CounterArduino(Counter):
    def __init__(self, name, computer_name, iopin, serial_name='/dev/ttyACM0'):
        super().__init__(name=name, computer_name=computer_name)
        self.iopin = iopin
        self.serial_name = serial_name
        self.last_water_read = -1
        self.last_water_time = datetime.datetime.now()
        self.flow = -1
        self.open_serial()
        self.clear_count()

    def open_serial(self):
        '''Get the USB(serial) port connection for the arduino and set it in self.serial

        if it already exists, return it. If not, try to connect

        Returns
        -------
            None if connection failed, otherwise the serial port
        '''
        if self.serial is not None:
            return self.serial
        try:
            self.serial = serial.Serial(self.serial_name, 9600, timeout=1)
        except serial.serialutil.SerialException:
            self.serial = None
            logger.warning('could not open serial port %s' % self.serial_name)
        return self.serial

    def get_count(self):
        '''Get the water count for the counter

        Returns:
        --------
            int - the water count
        '''
        command = 'r'+str(self.iopin)+'\n'
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
            print('count read conversion to int failed. count was: %s' % count)
        logger.debug('new count for %s pin %s: %d' % (self.serial_name, self.iopin, self.count))
        ctime = datetime.datetime.now()
        time_delta = (ctime - self.last_water_time).seconds
        if time_delta > MIN_FLOW_INTERVAL:
            self.flow = (self.count - self.last_water_read) * 60 / time_delta
            self.last_water_time = ctime
            self.last_water_read = self.count
        return self.count

    def clear_count(self):
        '''Set the count to 0'''
        command = 'c'+str(self.iopin)+'\n'
        if self.open_serial() is None:
            return
        self.serial.write(command.encode())
        new_count = self.get_count()
        if new_count != 0:
            logger.warning('clear counts failed for %s port %s. count is %d' % (self.serial_name, self.iopin, self.count))
            return
        logger.info('reset water counter %s port %s' % (self.serial_name, self.iopin))
