from datetime import datetime
from itsdangerous import TimedJSONWebSignatureSerializer as Serializer
from portfolio_tracker import db, login_manager, app
from flask_login import UserMixin
from portfolio_tracker.utils import num_2_str


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(20), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    currency = db.Column(db.String(3), nullable=False)
    image_file = db.Column(db.String(20), nullable=False,
                           default='default.jpg')
    password = db.Column(db.String(60), nullable=False)
    operations = db.relationship('Operation', backref='user', lazy=True)
    trade_PLs = db.relationship('TradePL', backref='user', lazy=True)
    positions = db.relationship('Portfolio', backref='user', lazy=True)
    tasks = db.relationship('Task', backref='user', lazy=True)

    def get_reset_token(self, expires_sec=1800):
        s = Serializer(app.config['SECRET_KEY'], expires_sec)
        return s.dumps({'user_id': self.id}).decode('utf-8')

    @staticmethod
    def verify_reset_token(token):
        s = Serializer(app.config['SECRET_KEY'])
        try:
            user_id = s.loads(token)['user_id']
        except Exception as e:
            return None
        return User.query.get(user_id)

    def __repr__(self):
        return f"User('{self.id}', '{self.username}', '{self.email}', '{self.currency}')"


class Operation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.DateTime, nullable=False)
    exchange = db.Column(db.String(20), nullable=False)
    type = db.Column(db.String(10), nullable=False)
    buy_amount = db.Column(db.Float)
    buy_coin = db.Column(db.String(10))
    sell_amount = db.Column(db.Float)
    sell_coin = db.Column(db.String(10))
    fee_amount = db.Column(db.Float)
    fee_coin = db.Column(db.String(10))
    comment = db.Column(db.String(200))
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

    def __repr__(self):
        date = self.date.strftime("%Y%m%d")
        return ("Operation('{}-{}-{}', Buy:{}|{}, Sell:{}|{}, Fee:{}|{})"
                .format(date, self.exchange, self.type,
                        self.buy_amount, self.buy_coin, self.sell_amount,
                        self.sell_coin, self.fee_amount, self.fee_coin))

    def print(self):
        date = self.date.strftime("%Y%m%d")
        return ("{}|{}|{}:  Buy={}|{}  Sell={}|{}  Fee={}|{})"
                .format(date, self.exchange, self.type,
                        self.buy_amount, self.buy_coin, self.sell_amount,
                        self.sell_coin, self.fee_amount, self.fee_coin))

    def buy_amount_str(self):
        if self.buy_amount or self.buy_amount == 0:
            return '{:20,.8f}'.format(self.buy_amount)
        return "-"

    def buy_coin_str(self):
        if self.buy_coin:
            return self.buy_coin
        return "-"

    def sell_amount_str(self):
        if self.sell_amount or self.sell_amount == 0:
            return '{:20,.8f}'.format(self.sell_amount)
        return "-"

    def sell_coin_str(self):
        if self.sell_coin:
            return self.sell_coin
        return "-"

    def fee_amount_str(self):
        if self.fee_amount or self.fee_amount == 0:
            return '{:20,.8f}'.format(self.fee_amount)
        return "-"

    def fee_coin_str(self):
        if self.fee_coin:
            return self.fee_coin
        return "-"

    def comment_str(self):
        if self.comment:
            return self.comment
        return "-"


class Price(db.Model):
    coin = db.Column(db.String(10), primary_key=True, nullable=False)
    currency = db.Column(db.String(10), primary_key=True, nullable=False)
    date = db.Column(db.DateTime, primary_key=True, nullable=False)
    price = db.Column(db.Float, nullable=False)

    def __repr__(self):
        date = self.date.strftime("%Y-%m-%d")
        return ("Price({}/{} ({}): {})"
                .format(self.coin, self.currency, date, self.price))


class PriceDelta(db.Model):
    coin = db.Column(db.String(10), primary_key=True, nullable=False)
    currency = db.Column(db.String(10), primary_key=True, nullable=False)
    delta_1d = db.Column(db.Float)
    delta_7d = db.Column(db.Float)
    delta_1m = db.Column(db.Float)
    delta_3m = db.Column(db.Float)
    delta_6m = db.Column(db.Float)
    delta_1y = db.Column(db.Float)
    delta_2y = db.Column(db.Float)

    def __repr__(self):
        return ("PriceDelta({}/{}: 1d={}, 7d={}, 1m={}, 3m={}, 6m={}, "
                "1y={}, 2y={})"
                .format(self.coin, self.currency, self.delta_1d, self.delta_7d,
                        self.delta_1m, self.delta_3m, self.delta_6m,
                        self.delta_1y, self.delta_2y))


class TradePL(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.DateTime, nullable=False)
    coin = db.Column(db.String(10), nullable=False)
    type = db.Column(db.String(10), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    buy_cost = db.Column(db.Float, nullable=False)
    sell_income = db.Column(db.Float)
    rem_FIFO = db.Column(db.Float)
    realized_PL = db.Column(db.Float)
    perc = db.Column(db.Float)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

    def __repr__(self):
        date = self.date.strftime("%Y%m%d")
        return ("TradePL({}-{}-{}: amount={}, buy_cost={}; , sell_income={};"
                " , rem_FIFO={}; , realized_PL={}; , user_id={})"
                .format(date, self.coin, self.type, self.amount, self.buy_cost,
                        self.sell_income, self.rem_FIFO, self.realized_PL,
                        self.user_id))

    def amount_str(self):
        return "{:20,.8f}".format(self.amount)

    def buy_cost_str(self, currency):
        return num_2_str(self.buy_cost, currency)

    def sell_income_str(self, currency):
        if not self.sell_income:
            return '-'
        else:
            return num_2_str(self.sell_income, currency)

    def realized_PL_str(self, currency):
        if not self.realized_PL:
            return '-'
        else:
            return num_2_str(self.realized_PL, currency)

    def perc_str(self):
        if self.perc:
            return "{:.2%}".format(self.perc)
        else:
            return "-"


class Portfolio(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.DateTime, nullable=False)
    exchange = db.Column(db.String(20), nullable=False)
    coin = db.Column(db.String(10), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    value = db.Column(db.Float, nullable=False)
    value_btc = db.Column(db.Float, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

    def __repr__(self):
        date = self.date.strftime("%Y%m%d")
        return ("Portfolio({}-{}-{}: {} ({}) )"
                .format(date, self.exchange, self.coin,
                        self.amount, self.value))

    def amount_str(self):
        return "{:20,.8f}".format(self.amount)

    def value_str(self, currency, decs=None):
        return num_2_str(self.value, currency, decs)

    def value_btc_str(self, currency, decs=None):
        return num_2_str(self.value_btc, 'BTC', decs)


class Task(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    request_time = db.Column(db.DateTime, nullable=False)
    name = db.Column(db.String(30), nullable=False)
    status = db.Column(db.String(10), nullable=False)
    not_before_time = db.Column(db.DateTime)
    start_time = db.Column(db.DateTime)
    finish_time = db.Column(db.DateTime)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    return_info = db.Column(db.String(100))

    def __repr__(self):
        start_time = None
        if self.not_before_time:
            start_time = self.not_before_time.strftime("%Y%m%d")
        if self.user_id and start_time:
            return ("Task({}[user:{}]: Status:{}, Start Time:{})"
                    .format(self.name, self.user_id, self.status, start_time))
        elif (self.user_id is None) and (start_time is None):
            return ("Task({}: Status:{})"
                    .format(self.name, self.status))
        elif self.user_id is None:
            return ("Task({}: Status:{}, Start Time:{})"
                    .format(self.name, self.status, start_time))
        elif start_time is None:
            return ("Task({}[user:{}]: Status:{})"
                    .format(self.name, self.user_id, self.status))


class Crypto(db.Model):
    symbol = db.Column(db.String(10), primary_key=True, nullable=False)
    long_name = db.Column(db.String(30))
    algorithm = db.Column(db.String(30))
    consensus_type = db.Column(db.String(30))
    supply = db.Column(db.Float)
    image_url = db.Column(db.String(50))

    def __repr__(self):
        return ("Crypto({} []{}])".format(self.symbol, self.long_name))
