import logging

import serial

from faucet import Faucet

logger = logging.getLogger(__name__)
logger.addHandler(logging.StreamHandler())
logger.setLevel(logging.DEBUG)


class NumatoFaucet(Faucet):
#    def __init__(self, port_name = '/dev/tty.usbmodem1421', **kwargs):
    def __init__(self, port_name='/dev/ttyACM0', **kwargs):
        super().__init__(**kwargs)
        # if the relay is a number, convert to hex letter
        if isinstance(self.relay_idx, int):
            self.relay_idx = self.relay_idx_from_num(self.relay_idx)
        self.port_name = port_name

    def relay_idx_from_num(self, relay_num):
        '''Get the relay index string from the relay number
        So we get 0-9,A-E instead of 10-15'''
        if int(relay_num) < 10:
            relay_num = str(relayNum)
        else:
            relay_num = chr(55 + int(relay_num))
        return relay_num

    def read_relay(self):
        try:
            relay_idx = self.relay_idx
            ser_port = serial.Serial(self.port_name, 19200, timeout=1)
            ser_port.write(("relay read " + relay_idx + "\n\r").encode('utf-8'))
            response = ser_port.read(25)
            ser_port.close()
            return response
        except:
            logger.warning('read_relay for %s idx %s failed' % (self.name, relay_idx))
            return None

    def  write_relay(self, relay_idx, relay_cmd):
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
        return res

    def close(self):
        logger.debug('closing faucet %s' % self.name)
        res = self.write_relay(self.relay_idx, 'off')
        if res:
            self.isopen = False
        return res
