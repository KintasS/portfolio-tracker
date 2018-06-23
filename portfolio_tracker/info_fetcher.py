import datetime
import json
from urllib.request import urlopen
import sys
from portfolio_tracker import db
from portfolio_tracker.utils import error_notificator
from portfolio_tracker.models import Operation, Price
from portfolio_tracker.config import Params


def import_operations(user, file, logger):
    """Imports the operations from a CSV image_file.
    """

    def validate_line(line, line_num):
        ln = (line.replace("\n", "")).split(";")
        for index, item in enumerate(ln):
            if len(item) == 0:
                ln[index] = None
        # Number of fields is OK
        if len(ln) != 11:
            logger.error("import_operations: Line does not have the "
                         "expected fields (11): '{}'".format(line))
            sys.exit()
        # 'Date' field is not empty
        date = ln[0]
        if len(date) == 0:
            logger.error("import_operations: 'Date' is empty (line {}). "
                         "--> '{}'".format(line_num+1, line))
            sys.exit()
        # 'Exchange' field is not empty
        exchange = ln[1]
        if len(exchange) == 0:
            logger.error("import_operations: 'Exchange' is empty (line {}). "
                         "--> '{}'".format(line_num+1, line))
            sys.exit()
        # 'Type' field is not empty
        type = ln[2]
        if len(type) == 0:
            logger.error("import_operations: 'Type' is empty (line {}). "
                         "--> '{}'".format(line_num+1, line))
            sys.exit()
        # Look for exact line in DB
        date = datetime.datetime.strptime(ln[0], "%Y-%m-%d")
        qry = Operation.query.filter_by(date=date, exchange=ln[1], type=ln[2],
                                        buy_amount=ln[3], buy_coin=ln[4],
                                        sell_amount=ln[5],  sell_coin=ln[6],
                                        fee_amount=ln[7], fee_coin=ln[8],
                                        comment=ln[9], user_id=ln[10]).first()
        if qry:
            logger.error("import_operations: File line already exists in DB "
                         "(line {}). Line: {}".format(line_num+1, line))
            sys.exit()
        return ln

    # MAIN FC CODE:
    try:
        with open(file, "r") as f:
            f_contents = f.readlines()
    except Exception as e:
        logger.error(f"import_operations: Error reading file '{file}'")
        sys.exit()
    for line_num, line in enumerate(f_contents):
        ln = validate_line(line, line_num)
        date = datetime.datetime.strptime(ln[0], "%Y-%m-%d")
        operation = Operation(date=date, exchange=ln[1], type=ln[2],
                              buy_amount=ln[3], buy_coin=ln[4],
                              sell_amount=ln[5],  sell_coin=ln[6],
                              fee_amount=ln[7], fee_coin=ln[8],
                              comment=ln[9], user_id=user.id)
        db.session.add(operation)
    db.session.commit()
    logger.info("import_operations: Operations imported "
                "({} rows)".format(len(f_contents)))


def update_prices(logger):
    """Updates the prices stored in the database.
    """

    def fetch_coin_prices(coin, currency):
        """ Fetches the history series for 'coin'/'currency'.
        """
        try:
            with urlopen("https://min-api.cryptocompare.com/data/histoday?"
                         "fsym={}&tsym={}&limit=600&aggregate=1"
                         "".format(coin, currency)) as response:
                source = response.read()
            json_data = json.loads(source)
            if json_data["Response"] == 'Success':
                logger.info("fetch_coin_prices: Prices fetched for '{}/{}'"
                            "".format(coin, currency))
                return json_data
            else:
                logger.warning("fetch_coin_prices: URL did not return "
                               "'Success' for '{}/{}'".format(coin, currency))
                return None
        except Exception as e:
            error_notificator(logger, "fetch_coin_prices()", e)
            sys.exit(764)

    # Get cryptos that exist in DB ('Operation' table):
    cryptos = db.session.query(Operation.buy_coin)\
                        .distinct(Operation.buy_coin).all()
    if cryptos:
        cryptos = [item[0] for item in cryptos]
        logger.debug("get_cryptos_in_trades: Coins found in Trades ({}):"
                     " {}".format(len(cryptos), cryptos))
        # Remove non-cryptos from list of cryptos
        non_cryptos = Params.NON_CRYPTOS
        for item in non_cryptos:
            try:
                cryptos.remove(item)
            except ValueError as e:
                continue
        logger.debug("get_cryptos_in_trades: Coins found in Trades after"
                     " cleaning ({}): {}".format(len(cryptos), cryptos))
    else:
        logger.error("get_cryptos_in_trades: No cryptos found "
                     "in 'Operation' table")
    # Update prices for each Crypto and Currency managed in the system:
    currencies = Params.CURRENCIES
    for crypto in cryptos:
        for currency in currencies:
            # Get last date currently stored in DB
            last_price_row = db.session.query(Price)\
                .filter_by(coin=crypto, currency=currency)\
                .order_by(Price.date.desc()).first()
            # If no records are found, set 'last_price_row' to 01-01-2017
            if last_price_row is None:
                last_date = datetime.datetime.strptime(Params.HISTORY_INIT,
                                                       "%Y-%m-%d").date()
            else:
                last_date = last_price_row.date.date()
            # Fetch Prices for crypto|currency
            json_data = fetch_coin_prices(crypto, currency)
            if json_data is None:
                logger.warning("update_coin_prices: Could not fetch prices"
                               " for '{}/{}'".format(crypto, currency))
                return
            # Scan JSON information to update DB
            try:
                for timestamp in json_data["Data"]:
                    rec_date_int = int(timestamp["time"])
                    rec_date = datetime.date.fromtimestamp(rec_date_int)
                    # Continue until a new date is found
                    if rec_date < last_date:
                        continue
                    # When a new date found, insert in DB (or update if last!)
                    price = timestamp["close"]
                    if ((rec_date != last_date) or (last_price_row is None)):
                        prc = Price(coin=crypto, currency=currency,
                                    date=rec_date, price=price)
                        db.session.add(prc)
                    else:
                        last_price_row.price = price
                db.session.commit()
                logger.info("update_coin_prices: 'Price' table updated "
                            "for '{}/{}'".format(crypto, currency))
            # Warning if not unicode characters are found in the JSON
            except UnicodeEncodeError as e:
                logger.warning("update_coin_prices()[2]: {}".format(e))
                continue
