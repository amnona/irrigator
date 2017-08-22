from logging import getLogger

import serial

logger = getLogger(__name__)

from counter import Counter

class CounterArduino(Counter):
    def __init__(self, iopin, serial_name='/dev/ttyACM0'):
        super().__init__()
        self.iopin = iopin
        self.serial_name = serial_name
        self.clear_count()

    def get_count(self):
        try:
            ser = serial.Serial('/dev/ttyACM0', 9600, timeout=1)
        except:
            logger.warning('cannot connect to water counter %s' % self.serial_name)
            return self.count
        command = 'r'+str(self.iopin)+'\n'
        ser.write(command.encode())
        try:
            count = ser.readline()
        except:
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
        ser = serial.Serial('/dev/ttyACM0', 9600, timeout=1)
        command = 'c'+str(self.iopin)+'\n'
        ser.write(command.encode())
        new_count = self.get_count()
        if new_count != 0:
            logger.warning('clear counts failed for %s port %s. count is %d' % (self.serial_name, self.iopin, self.count))
            return
        logger.info('reset water counter %s port %s' % (self.serial_name, self.iopin))
