class CounterPi(Counter):
    '''
    A water counter class for contact (pulse) flow meter using the gpio pins
    '''
    def __init__(self, channel, voltage_channel=None):
        '''

        :param channel:
         the raspberry pi channel where the counter is connected
        '''
        super().__init()
        try:
            import RPi.GPIO as GPIO
        except RuntimeError:
            print(
                "Error importing RPi.GPIO!  This is probably because you need superuser privileges.  You can achieve this by using 'sudo' to run your script")
        GPIO.setmode(GPIO.BOARD)
        GPIO.setup(channel, GPIO.IN)
        if voltage_channel is not None:
            GPIO.setup(voltage_channel, GPIO.OUT, initial=GPIO.HIGH)
        self.channel = channel
        self.last_val = self.get_current_value()
        self.count = 0

    def get_current_value(self):
        return GPIO.input(self.channel)

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
