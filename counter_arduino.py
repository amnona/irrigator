from logging import getLogger
import datetime

import serial

logger = getLogger(__name__)

from counter import Counter

MIN_FLOW_INTERVAL = 60

class CounterArduino(Counter):
    def __init__(self, name, computer_name, iopin, serial_name='/dev/ttyACM0'):
        super().__init__(name=name, computer_name=computer_name)
        self.iopin = iopin
        self.serial_name = serial_name
        self.serial = serial.Serial(self.serial_name, 9600, timeout=1)
        self.clear_count()
        self.last_water_read = None
        self.last_water_time = datetime.datetime.now()
        self.flow = None

    def get_count(self):
        command = 'r'+str(self.iopin)+'\n'
        self.serial.write(command.encode())
        try:
            count = self.serial.readline()
        except serial.SerialTimeoutException:
            logger.warning('did not get response from serial %s' % self.serial_name)
            return self.count
        try:
            self.count = int(count)
        except:
            print('count read failed %s' % count)
        logger.debug('new count for %s pin %s: %d' % (self.serial_name, self.iopin, self.count))
        ctime = datetime.datetime.now()
        time_delta = ctime - self.last_water_time
        if time_delta.seconds > MIN_FLOW_INTERVAL:
            self.flow = (self.count - self.last_water_read)/time_delta
            self.last_water_time = ctime
            self.last_water_read = self.count
        return self.count

    def clear_count(self):
        '''Set the count to 0'''
        command = 'c'+str(self.iopin)+'\n'
        self.serial.write(command.encode())
        new_count = self.get_count()
        if new_count != 0:
            logger.warning('clear counts failed for %s port %s. count is %d' % (self.serial_name, self.iopin, self.count))
            return
        logger.info('reset water counter %s port %s' % (self.serial_name, self.iopin))
