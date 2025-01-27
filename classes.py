class SimCard:
    number = None

    def __init__(self, icc):
        self.icc = icc

    def get_number(self):
        return self.number