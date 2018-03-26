class Counter():
    def __init__(self,name, computer_name):
        self.count = 0
        self.last_val = False
        self.name = name
        self.computer_name = computer_name
        # count how long (consecutive reads) there is a leak - i.e. no faucet is supposed to be open
        # but water is running
        self.leak_duration = 0
        # last water value read on this counter (to look for flow/leak)
        self.last_water_read = 0

    def update(self):
        pass

    def get_count(self):
        return self.count
