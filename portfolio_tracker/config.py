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
    USER = 'SergioQV'
    CALC_CURRENCY = 'EUR'
    NON_CRYPTOS = ['EUR', 'USD', None]
    HISTORY_INIT = '2017-01-01'
    CURRENCIES = ['EUR', 'USD']
