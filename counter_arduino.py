from logging import getLogger

import serial

logger = getLogger(__name__)

from counter import Counter

class CounterArduino(Counter):
    def __init__(self, iopin, serial_name='/dev/ttyACM0'):
        super().__init__()
        self.iopin = iopin
        self.serial_name = serial_name
        self.serial = serial.Serial(self.serial_name, 9600, timeout=1)
        self.clear_count()

    def get_count(self):
        command = 'r'+str(self.iopin)+'\n'
        self.serial.write(command.encode())
        try:
            count = ser.readline()
        except serial.SerialTimeoutException:
            logger.warning('did not get response from serial %s' % self.serial_name)
            return self.count
        try:
            self.count = int(count)
        except:
            print('count read failed %s' % count)
        logger.debug('new count for %s pin %s: %d' % (self.serial_name, self.iopin, self.count))
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
