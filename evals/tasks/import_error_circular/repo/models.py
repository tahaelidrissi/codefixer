from services import get_discount


class Order:
    def __init__(self, total):
        self.total = total

    def final_total(self):
        return self.total - get_discount(self.total)
