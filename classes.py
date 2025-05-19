class SimCard:
    """Класс, представляющий СИМ-карту."""

    def __init__(self, icc):
        self.icc = icc

    def __eq__(self, other):
        if isinstance(other, self.__class__):
            return self.icc == other.icc
        return False

    def __hash__(self):
        return hash(self.icc)

    def __str__(self):
        return str(self.icc)


class Number:
    """Класс представляющий Номер."""

    def __init__(self, number, balance=None, sim_card=None):
        self.number = number
        self.sim_card = sim_card
        self.block = None
        self.block_date = None
        self.balance = balance
        self.api_response = None

    def __eq__(self, other):
        if isinstance(other, self.__class__):
            return (self.number == other.number
                    and self.sim_card == other.sim_card)
        return False

    def __hash__(self):
        return hash((self.number, self.sim_card))

    def __str__(self):
        return str(self.number)


class ApiMtsResponse:
    """Класс, описывающий ответ API запроса."""

    def __init__(self, success, text):
        self.success = success
        self.text = text
