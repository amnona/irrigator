import logging

import serial

from faucet import Faucet

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


class NumatoFaucet(Faucet):
#    def __init__(self, port_name = '/dev/tty.usbmodem1421', **kwargs):
    def __init__(self, port_name='/dev/ttyACM0', **kwargs):
        super().__init__(**kwargs)
        # if the relay is a number, convert to hex letter
        try:
            self.relay_idx = self.relay_idx_from_num(self.relay_idx)
        except:
            self.relay_idx = str(self.relay_idx)
        self.port_name = self.get_serial_port()

    def relay_idx_from_num(self, relay_num):
        '''Get the relay index string from the relay number
        So we get 0-9,A-E instead of 10-15'''
        if int(relay_num) < 10:
            relay_num = str(relay_num)
        else:
            relay_num = chr(55 + int(relay_num))
        return relay_num

    def get_serial_port(self):
        # find and set the correct port name
        port_names = ['/dev/ttyACM0', '/dev/tty.usbmodem1421']
        found_port = None
        for cport in port_names:
            try:
                logger.debug('trying port %s' % cport)
                ser_port = serial.Serial(cport, 19200, timeout=1)
                logger.debug('opened')
                ser_port.write(("ver\n\r").encode('utf-8'))
                logger.debug('wrote ver')
                response = ser_port.read(8)
                logger.debug('got response %s' % response)
                ser_port.close()
                found_port = cport
                logger.info('USB/serial port %s responded, version=%s' % (cport, response))
                break
            except Exception as e:
                logger.debug('port %s not found. error %s' % (cport, e))
        if found_port is None:
            logger.warning('USB/Serial port not found. Unable to connect to USB')
        return found_port

    def read_relay(self):
        try:
            relay_idx = self.relay_idx
            ser_port = serial.Serial(self.port_name, 19200, timeout=1)

            # empty the read buffer (don't need old output)
            ser_port.reset_input_buffer()

            ser_port.write(("relay read " + relay_idx + "\n\r").encode('utf-8'))
            response = ser_port.read(25)
            ser_port.close()
            return response
        except:
            logger.warning('read_relay for %s idx %s failed' % (self.name, relay_idx))
            return None

    def write_relay(self, relay_idx, relay_cmd):
        '''
        :param relay_idx:
            "1"-"9","A"-"F"
        :param relay_cmd:
            can be "on" or "off"
        :return:
        '''
        try:
            ser_port = serial.Serial(self.port_name, 19200, timeout=1)
            cmd = "relay " + str(relay_cmd) + " " + str(relay_idx) + "\n\r"
            ser_port.write(cmd.encode('utf-8'))
            ser_port.close()
            return True
        except Exception as e:
            logger.warning('failed to write "%s" to relay %s for faucet %s' % (relay_cmd, relay_idx, self.name))
            logger.debug(e)
            return False

    def open(self):
        logger.debug('opening faucet %s' % self.name)
        res = self.write_relay(self.relay_idx, 'on')
        if res:
            self.isopen = True
        status = self.read_relay()
        logger.debug('open. got response %s' % status)
        return res

    def close(self):
        logger.debug('closing faucet %s' % self.name)
        res = self.write_relay(self.relay_idx, 'off')
        if res:
            self.isopen = False
        status = self.read_relay()
        logger.debug('close. got response %s' % status)
        return res
