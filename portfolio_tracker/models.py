from datetime import datetime
from itsdangerous import TimedJSONWebSignatureSerializer as Serializer
from portfolio_tracker import db, login_manager, app
from flask_login import UserMixin


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(20), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    image_file = db.Column(db.String(20), nullable=False,
                           default='default.jpg')
    password = db.Column(db.String(60), nullable=False)
    posts = db.relationship('Post', backref='author', lazy=True)
    operations = db.relationship('Operation', backref='trader', lazy=True)
    trade_PLs = db.relationship('TradePL', backref='trader', lazy=True)
    positions = db.relationship('Portfolio', backref='trader', lazy=True)
    balances = db.relationship('Balance', backref='trader', lazy=True)

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
        return f"User('{self.id}', '{self.username}', '{self.email}')"


class Post(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    date_posted = db.Column(db.DateTime, nullable=False,
                            default=datetime.utcnow)
    content = db.Column(db.Text, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

    def __repr__(self):
        return f"Post('{self.title}', '{self.date_posted}')"


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
    comment = db.Column(db.String(100))
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

    def __repr__(self):
        date = self.date.strftime("%Y%m%d")
        return ("Operation('{}-{}-{}', Buy:{}|{}, Sell:{}|{}, Fee:{}|{})"
                .format(date, self.exchange, self.type,
                        self.buy_amount, self.buy_coin, self.sell_amount,
                        self.sell_coin, self.fee_amount, self.fee_coin))


class Price(db.Model):
    coin = db.Column(db.String(10), primary_key=True, nullable=False)
    currency = db.Column(db.String(10), primary_key=True, nullable=False)
    date = db.Column(db.DateTime, primary_key=True, nullable=False)
    price = db.Column(db.Float, nullable=False)

    def __repr__(self):
        date = self.date.strftime("%Y-%m-%d")
        return ("Price({}/{} ({}): {})"
                .format(self.coin, self.currency, date, self.price))


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
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

    def __repr__(self):
        date = self.date.strftime("%Y%m%d")
        return ("TradePL({}-{}-{}: amount={}, buy_cost={}; , sell_income={};"
                " , rem_FIFO={}; , realized_PL={}; , user_id={})"
                .format(date, self.coin, self.type, self.amount, self.buy_cost,
                        self.sell_income, self.rem_FIFO, self.realized_PL,
                        self.user_id))


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


class Balance(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.DateTime, nullable=False)
    coin = db.Column(db.String(10), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    value = db.Column(db.Float, nullable=False)
    value_btc = db.Column(db.Float, nullable=False)
    perc = db.Column(db.Float)
    realized_PL = db.Column(db.Float, nullable=False)
    unrealized_PL = db.Column(db.Float, nullable=False)
    total_PL = db.Column(db.Float, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

    def __repr__(self):
        date = self.date.strftime("%Y%m%d")
        return ("Balance({}-{}-{}: {})"
                .format(date, self.coin, self.amount, self.value))
