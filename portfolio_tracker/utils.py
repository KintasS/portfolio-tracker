import logging
from portfolio_tracker.config import Params


def set_logger(file_name, logger_name):
    """Sets logging configuration.
    """
    # Set-up logger in both file
    logger = logging.getLogger(logger_name)
    logger.setLevel(logging.INFO)
    formatter = logging.Formatter('%(asctime)s:%(levelname)s:%(message)s')
    file_handler = logging.FileHandler(file_name)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    # Set-up looger in console
    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)
    # Return logger to allow it to be called from outside
    return logger


def error_notificator(logger_name, function, error):
    """Handles application erros to notify its creator.
    """
    logger_name.error("Not handled error in '{}': {}".format(function, error))
    pass


def num_2_str(number, currency, decs=None):
    """Formats 'number' so that it has 'decs' number of decimal places,
    and the symbol corresponding to 'currency'
    """
    try:
        symbol = Params.CURRENCY_SYMBOLS[currency]
    except Exception as e:
        symbol = '?'
    if decs is None:
        try:
            decs = Params.DECIMAL_POS[currency]
        except Exception as e:
            decs = 2
    try:
        return "{:20,.{}f} {}".format(number, decs, symbol)
    except ValueError as e:
        return number
    except TypeError as e:
        return number


def str_2_num(str_num):
    """
    """
    str_num = str_num[:-2]
    str_num = str_num.replace(" ", "")
    num = float(str_num.replace(",", ""))
    return num


def num_2_perc(number, decs):
    """Formats 'number' so that it is provided in percentage format
    with the amount of 'decs' indicated.'
    """
    try:
        return "{:.{}%}".format(number, decs)
    except ValueError as e:
        return number
    except TypeError as e:
        return number


def split_portf_by_exch(portfolio):
    """Splits a list of position of a portfolio in exchanges.
    """
    split_port = {}
    for pos in portfolio:
        try:
            split_port[pos.exchange].append(pos)
        except KeyError as e:
            split_port.update({pos.exchange: [pos]})
    return split_port


def divide(num, den):
    try:
        return num / den
    except ZeroDivisionError as e:
        return '-'


def get_type_choices():
    op_types = Params.OPERATION_TYPES
    choices = []
    for item in op_types:
        choices.append((item, item))
    return choices


def get_allowed_currencies():
    op_types = Params.CURRENCIES
    choices = []
    for item in op_types:
        choices.append((item, item))
    return choices


def is_number(s):
    try:
        float(s)
        return True
    except ValueError:
        return False


def is_positive_number(s):
    try:
        s = float(s)
        if s >= 0:
            return True
        return False
    except ValueError:
        return False
