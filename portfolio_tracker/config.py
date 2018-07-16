import os


class AppConfig:
    SECRET_KEY = os.environ.get('SECRET_KEY')
    SQLALCHEMY_DATABASE_URI = os.environ.get('SQLALCHEMY_DATABASE_URI')
    MAIL_SERVER = 'smtp.googlemail.com'
    MAIL_PORT = 587
    MAIL_USE_TLS = True
    MAIL_USERNAME = os.environ.get('EMAIL_USER')
    MAIL_PASSWORD = os.environ.get('EMAIL_PASS')


class Params:
    NON_CRYPTOS = ['EUR', 'USD', None]
    HISTORY_INIT = '2016-01-01'
    CURRENCIES = ['EUR', 'USD']
    # CURRENCY_SYMBOLS = {'EUR': '€',
    #                     'USD': '$',
    #                     'BTC': 'B'}
    DECIMAL_POS = {'EUR': 2,
                   'USD': 2,
                   'BTC': 8}
    OPERATION_TYPES = ['Airdrop', 'Deposit', 'Expense', 'Fork',
                       'Income', 'Trade', 'Withdrawal']
    IMPORT_HEADER = ("Date;Exchange;Type;Buy Amount;Buy Coin;Sell Amount;"
                     "Sell Coin;Fee Amount;Fee Coin;Comment")
    CURRENCY_SYMBOLS = {'EUR': '€',
                        'USD': '$',
                        'BTC': '฿'}
