from portfolio_tracker.utils import num_2_str


class FileLineError:

    def __init__(self, line_num, line_error, line_content):
        self.line_num = line_num
        self.line_error = line_error
        self.line_content = line_content

    def __repr__(self):
        return "FileLineError(LÍNEA '{}': {} [{}])".format(self.line_num,
                                                           self.line_error,
                                                           self.line_content)


class PortfolioWarning:

    def __init__(self, legend, operation):
        self.legend = legend
        self.operation = operation

    def __repr__(self):
        return "PortfolioWarning(Warning: '{}' [{}])".format(self.legend,
                                                             self.operation)


class Balance:

    def __init__(self, date, coin, amount, value, value_btc, perc, realized_PL,
                 unrealized_PL, unrealized_perc, total_PL):
        self.date = date
        self.coin = coin
        self.amount = amount
        self.value = value
        self.value_btc = value_btc
        self.perc = perc
        self.realized_PL = realized_PL
        self.unrealized_PL = unrealized_PL
        self.unrealized_perc = unrealized_perc
        self.total_PL = total_PL

    def __repr__(self):
        date = self.date.strftime("%Y%m%d")
        return ("Balance({}-{}-{}: {})"
                .format(date, self.coin, self.amount, self.value))

    def amount_str(self):
        return "{:20,.8f}".format(self.amount)

    def value_str(self, currency):
        return num_2_str(self.value, currency, 0)

    def perc_str(self):
        if self.perc:
            return "{:.2%}".format(self.perc)
        else:
            return "-"

    def unrealized_PL_str(self, currency):
        return num_2_str(self.unrealized_PL, currency, 0)

    def unrealized_perc_str(self):
        if self.unrealized_perc:
            return "{:.2%}".format(self.unrealized_perc)
        else:
            return "-"

    def realized_PL_str(self, currency):
        return num_2_str(self.realized_PL, currency, 0)

    def total_PL_str(self, currency):
        return num_2_str(self.total_PL, currency, 0)
