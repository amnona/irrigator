class Counter():
    def __init__(self,name, computer_name):
        self.count = 0
        self.last_val = False
        self.name = name
        self.computer_name = computer_name

    def update(self):
        pass

    def get_count(self):
        return self.count
