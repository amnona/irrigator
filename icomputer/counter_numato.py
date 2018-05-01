import serial

from .counter import Counter


class CounterNumato(Counter):
    '''
    A water counter class for contact (pulse) flow meter using the numato usb relay board
    '''
    def __init__(self, iopin, voltage_pin=None, port_name='/dev/tty.usbmodem1421', counts_per_liter=1.0):
        '''

        :param iopin: str
         the io pin to which the counter is connected (0-9)
        :param voltage_pin: str
         the pin to which the voltage is taken from (optional) (0-9)
        '''
        super().__init__()
        self.iopin = iopin
        self.port_name = port_name
        self.voltage_pin = str(voltage_pin)
        if voltage_pin is not None:
            ser_port = serial.Serial(self.port_name, 19200, timeout=1)
            cmd = "gpio set " + self.voltage_pin + "\n\r"
            ser_port.write(cmd.encode('utf-8'))
            ser_port.close()
        self.iopin = iopin
        self.last_val = self.get_current_value()
        self.count = 0

    def get_current_value(self):
        ser_port = serial.Serial(self.port_name, 19200, timeout=1)
        cmd = "gpio read " + self.voltage_pin + "\n\r"
        ser_port.write(cmd.encode('utf-8'))
        response = ser_port.readline()
        ser_port.close()
        if response[1] == 'n':
            return True
        return False

    def update(self):
        cval = self.get_current_value()
        if cval == self.last_val:
            return
        self.last_val = cval
        if cval:
            self.count += 1

    def reset(self):
        self.count = 0
        self.last_val = self.get_current_value()
