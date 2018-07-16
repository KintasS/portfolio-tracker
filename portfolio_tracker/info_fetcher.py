import datetime
import json
import math
import time
from urllib.request import urlopen
import sys
from portfolio_tracker import db
from portfolio_tracker.utils import error_notificator, is_positive_number
from portfolio_tracker.models import Operation, Price, Crypto
from portfolio_tracker.config import Params
from portfolio_tracker.objects import FileLineError


def import_operations_file(user, file, logger):
    """Imports the operations from a CSV image_file.
    In case errors are found, they are return in a list.
    """

    def validate_header(line):
        expected_header = Params.IMPORT_HEADER
        line = line.replace("\n", "")
        if line != expected_header:
            err = FileLineError(0,
                                "La cabecera no tiene el formato esperado",
                                line)
            return err
        return None

    def validate_line(line, line_num, f_contents):
        ln_errors = []
        ln = (line.replace("\n", "")).split(";")
        # Number of fields is OK
        if len(ln) != 10:
            err = FileLineError(line_num,
                                "Se esperaban '10 campos' y se encontraron "
                                "'{}' (nota: asegúrese de que el separador"
                                " utilizado es ';')".format(len(ln)),
                                line)
            ln_errors.append(err)
            return ln_errors

        # VALIDATIONS ON ***'Date'*** FIELD
        date = ln[0]
        # 'Date' field must not be empty
        if len(date) == 0:
            err = FileLineError(line_num,
                                "El campo 'Date' es obligatorio",
                                line)
            ln_errors.append(err)
        # Check 'Date' format
        else:
            try:
                date = datetime.datetime.strptime(date, "%Y-%m-%d")
            except Exception as e:
                err = FileLineError(line_num,
                                    "El campo 'Date' no tiene formato "
                                    "correcto (YYYY-MM-DD)",
                                    line)
                ln_errors.append(err)

        # VALIDATIONS ON ***'Exchange'*** FIELD
        exchange = ln[1]
        # 'Exchange' field must not be empty
        if len(exchange) == 0:
            err = FileLineError(line_num,
                                "El campo 'Exchange' es obligatorio",
                                line)
            ln_errors.append(err)
        # 'Exchange' field must not be longer than '20' characters
        if len(exchange) > 20:
            err = FileLineError(line_num,
                                "El campo 'Exchange' es demasiado largo "
                                "(máximo 20 caracteres)",
                                line)
            ln_errors.append(err)

        # VALIDATIONS ON ***'Type'*** FIELD
        type = ln[2]
        # 'Type' field must not be empty
        if len(type) == 0:
            err = FileLineError(line_num,
                                "El campo 'Type' es obligatorio",
                                line)
            ln_errors.append(err)
        # 'Type' field must be a valid choice
        if type not in Params.OPERATION_TYPES:
            err = FileLineError(line_num,
                                "El campo 'Type' no contiene un valor "
                                "reconocido {}".format(Params.OPERATION_TYPES),
                                line)
            ln_errors.append(err)

        # VALIDATIONS ON ***'Buy Amount'*** FIELD
        buy_amount = ln[3]
        # 'Buy Amount' must be filled only for specific types of operations
        if type in ['Expense', 'Withdrawal']:
            if len(buy_amount) > 0:
                err = FileLineError(line_num,
                                    "El campo '{}' debe estar vacío para una "
                                    "operación de tipo '{}'"
                                    .format("Buy Amount", type),
                                    line)
                ln_errors.append(err)
        else:
            if len(buy_amount) == 0:
                err = FileLineError(line_num,
                                    "El campo '{}' es obligatorio para una "
                                    "operación de tipo '{}'"
                                    .format("Buy Amount", type),
                                    line)
                ln_errors.append(err)
            elif not is_positive_number(buy_amount):
                err = FileLineError(line_num,
                                    "El campo '{}' debe ser un número (no "
                                    "negativo)".format("Buy Amount"),
                                    line)
                ln_errors.append(err)

        # VALIDATIONS ON ***'Buy Coin'*** FIELD
        buy_coin = ln[4]
        # 'Buy Coin' must be filled only for specific types of operations
        if type in ['Expense', 'Withdrawal']:
            if len(buy_coin) > 0:
                err = FileLineError(line_num,
                                    "El campo '{}' debe estar vacío para una "
                                    "operación de tipo '{}'"
                                    .format("Buy Coin", type),
                                    line)
                ln_errors.append(err)
        else:
            if len(buy_coin) == 0:
                err = FileLineError(line_num,
                                    "El campo '{}' es obligatorio para una "
                                    "operación de tipo '{}'"
                                    .format("Buy Coin", type),
                                    line)
                ln_errors.append(err)
            # 'Buy Coin' field must not be longer than '10' characters
            if len(buy_coin) > 10:
                err = FileLineError(line_num,
                                    "El campo 'Buy Coin' es demasiado largo "
                                    "(máximo 10 caracteres)",
                                    line)
                ln_errors.append(err)

        # VALIDATIONS ON ***'Sell Amount'*** FIELD
        sell_amount = ln[5]
        # 'Sell Amount' must be filled only for specific types of operations
        if type in ['Airdrop', 'Deposit', 'Fork', 'Income']:
            if len(sell_amount) > 0:
                err = FileLineError(line_num,
                                    "El campo '{}' debe estar vacío para una "
                                    "operación de tipo '{}'"
                                    .format("Sell Amount", type),
                                    line)
                ln_errors.append(err)
        else:
            if len(sell_amount) == 0:
                err = FileLineError(line_num,
                                    "El campo '{}' es obligatorio para una "
                                    "operación de tipo '{}'"
                                    .format("Sell Amount", type),
                                    line)
                ln_errors.append(err)
            elif not is_positive_number(sell_amount):
                err = FileLineError(line_num,
                                    "El campo '{}' debe ser un número (no "
                                    "negativo)".format("Sell Amount"),
                                    line)
                ln_errors.append(err)

        # VALIDATIONS ON ***'Sell Coin'*** FIELD
        sell_coin = ln[6]
        # 'Sell Coin' must be filled only for specific types of operations
        if type in ['Airdrop', 'Deposit', 'Fork', 'Income']:
            if len(sell_coin) > 0:
                err = FileLineError(line_num,
                                    "El campo '{}' debe estar vacío para una "
                                    "operación de tipo '{}'"
                                    .format("Sell Coin", type),
                                    line)
                ln_errors.append(err)
        else:
            if len(sell_coin) == 0:
                err = FileLineError(line_num,
                                    "El campo '{}' es obligatorio para una "
                                    "operación de tipo '{}'"
                                    .format("Sell Coin", type),
                                    line)
                ln_errors.append(err)
            # 'Sell Coin' field must not be longer than '10' characters
            if len(sell_coin) > 10:
                err = FileLineError(line_num,
                                    "El campo 'Sell Coin' es demasiado largo "
                                    "(máximo 10 caracteres)",
                                    line)
                ln_errors.append(err)

        # VALIDATIONS ON ***'Fee Amount'*** FIELD
        fee_amount = ln[7]
        # 'Fee Amount' must be filled only for specific types of operations
        if type in ['Airdrop', 'Deposit', 'Fork', 'Income']:
            if len(fee_amount) > 0:
                err = FileLineError(line_num,
                                    "El campo '{}' debe estar vacío para una "
                                    "operación de tipo '{}'"
                                    .format("Fee Amount", type),
                                    line)
                ln_errors.append(err)
        else:
            if len(fee_amount) == 0:
                err = FileLineError(line_num,
                                    "El campo '{}' es obligatorio para una "
                                    "operación de tipo '{}'"
                                    .format("Fee Amount", type),
                                    line)
                ln_errors.append(err)
            elif not is_positive_number(fee_amount):
                err = FileLineError(line_num,
                                    "El campo '{}' debe ser un número (no "
                                    "negativo)".format("Fee Amount"),
                                    line)
                ln_errors.append(err)

        # VALIDATIONS ON ***'Fee Coin'*** FIELD
        fee_coin = ln[8]
        # 'Fee Coin' must be filled only for specific types of operations
        if type in ['Airdrop', 'Deposit', 'Fork', 'Income']:
            if len(fee_coin) > 0:
                err = FileLineError(line_num,
                                    "El campo '{}' debe estar vacío para una "
                                    "operación de tipo '{}'"
                                    .format("Fee Coin", type),
                                    line)
                ln_errors.append(err)
        else:
            if len(fee_coin) == 0:
                err = FileLineError(line_num,
                                    "El campo '{}' es obligatorio para una "
                                    "operación de tipo '{}'"
                                    .format("Fee Coin", type),
                                    line)
                ln_errors.append(err)
            # 'Fee Coin' field must not be longer than '10' characters
            if len(fee_coin) > 10:
                err = FileLineError(line_num,
                                    "El campo 'Fee Coin' es demasiado largo "
                                    "(máximo 10 caracteres)",
                                    line)
                ln_errors.append(err)

        # VALIDATIONS ON ***'Comment'*** FIELD
        comment = ln[9]
        # 'Comment' field must not be longer than '10' characters
        if len(comment) > 200:
            err = FileLineError(line_num,
                                "El campo 'Comment' es demasiado largo "
                                "(máximo 200 caracteres)",
                                line)
            ln_errors.append(err)

        # CHECK IF LINE ALREADY EXISTS IN DB
        op = Operation.query.filter_by(date=date, exchange=ln[1], type=ln[2],
                                       buy_amount=ln[3], buy_coin=ln[4],
                                       sell_amount=ln[5],  sell_coin=ln[6],
                                       fee_amount=ln[7], fee_coin=ln[8],
                                       user_id=user.id).first()
        if op:
            err = FileLineError(line_num,
                                "Línea ya existente en la Base de Datos",
                                line)
            ln_errors.append(err)

        # CHECK IF TWO EQUAL LINES IN FILEB
        for row, row_content in enumerate(f_contents):
            if (row_content == line) and (row != line_num):
                err = FileLineError(line_num,
                                    "Línea duplicada en fichero (igual a "
                                    "línea '{}')".format(row),
                                    line)
                ln_errors.append(err)

        return ln_errors

    """MAIN CODE FOR 'import_operations_file'"""
    errors = []
    try:
        with open(file, "r", encoding='utf-8') as f:
            f_contents = f.readlines()
    except Exception as e:
        err = FileLineError("-",
                            "Error al leer el fichero '{}'".format(file),
                            "")
        errors.append(err)
        return errors
    # Loop for each line
    for line_num, line in enumerate(f_contents):
        if line_num == 0:
            err = validate_header(line)
            if err:
                errors.append(err)
        else:
            line_errors = validate_line(line, line_num, f_contents)
            for item in line_errors:
                errors.append(item)
    # If no errors were found, import records
    if len(errors) == 0:
        tmp_user_id = user.id + 1000000
        # Delete records of 'user.id + 1000000' (just in case)
        db.session.query(Operation).filter_by(user_id=tmp_user_id).delete()
        # Copy records of user to tmp_user
        user_operations = Operation.query.filter_by(user_id=user.id)
        for op in user_operations:
            tmp_op = Operation(date=op.date, exchange=op.exchange,
                               type=op.type, buy_amount=op.buy_amount,
                               buy_coin=op.buy_coin,
                               sell_amount=op.sell_amount,
                               sell_coin=op.sell_coin,
                               fee_amount=op.fee_amount, fee_coin=op.fee_coin,
                               comment=op.comment, user_id=tmp_user_id)
            db.session.add(tmp_op)
        db.session.commit()
        # Loop to insert each line
        for line_num, line in enumerate(f_contents):
            if line_num == 0:
                continue
            # Replace '' for None (otherwise, it does not import)
            ln = (line.replace("\n", "")).split(";")
            for index, item in enumerate(ln):
                if len(item) == 0:
                    ln[index] = None
            # Insert in database for 'user.id + 1000000'
            date = datetime.datetime.strptime(ln[0], "%Y-%m-%d")
            operation = Operation(date=date, exchange=ln[1], type=ln[2],
                                  buy_amount=ln[3], buy_coin=ln[4],
                                  sell_amount=ln[5],  sell_coin=ln[6],
                                  fee_amount=ln[7], fee_coin=ln[8],
                                  comment=ln[9], user_id=tmp_user_id)
            db.session.add(operation)
    db.session.commit()
    logger.info("import_operations_file: Operations imported "
                "({} rows)".format(len(f_contents)))
    return errors


def update_prices(logger):
    """Updates the prices stored in the database.
    Returns the oldest date that has been updated.
    """

    def fetch_coin_prices(coin, currency):
        """ Fetches the history series for 'coin'/'currency'.
        """
        try:
            with urlopen("https://min-api.cryptocompare.com/data/histoday?"
                         "fsym={}&tsym={}&limit=950&aggregate=1"
                         "".format(coin, currency)) as response:
                source = response.read()
            json_data = json.loads(source)
            if json_data["Response"] == 'Success':
                logger.debug("fetch_coin_prices: Prices fetched for '{}/{}'"
                             "".format(coin, currency))
                return json_data
            else:
                logger.warning("fetch_coin_prices: URL did not return "
                               "'Success' for '{}/{}'".format(coin, currency))
                return None
        except Exception as e:
            return None

    """MAIN CODE FOR 'update_prices()'.
    """
    logger.info("update_coin_prices: Updating prices...")
    # Variable to to return the oldest date updated
    oldest_updated_date = datetime.datetime.now().date()
    # Get cryptos that exist in DB ('Operation' table):
    cryptos = db.session.query(Operation.buy_coin)\
                        .distinct(Operation.buy_coin).all()
    if cryptos:
        cryptos = [item[0] for item in cryptos]
        logger.debug("update_prices: Coins found in Trades ({}):"
                     " {}".format(len(cryptos), cryptos))
        # Remove non-cryptos from list of cryptos
        non_cryptos = Params.NON_CRYPTOS
        for item in non_cryptos:
            try:
                cryptos.remove(item)
            except ValueError as e:
                continue
        # Romove cryptos not in 'Crypto' table
        cryptos_in_db = db.session.query(Crypto.symbol).all()
        if cryptos_in_db:
            cryptos_in_db = [item[0] for item in cryptos_in_db]
        for item in cryptos:
            if item not in cryptos_in_db:
                logger.info("update_prices: Coin '{}' not found in DB."
                            .format(item))
                cryptos.remove(item)
        logger.debug("update_prices: Coins found in Trades after"
                     " cleaning ({}): {}".format(len(cryptos), cryptos))
    else:
        logger.error("update_prices: No cryptos found "
                     "in 'Operation' table")
    # Variable to store records to be inserted
    new_records = []
    # Update prices for each Crypto and Currency managed in the system:
    currencies = Params.CURRENCIES + ['BTC']
    for crypto in cryptos:
        logger.debug("update_prices: Fetching prices for '{}'".format(crypto))
        for currency in currencies:
            if crypto == currency:
                continue
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
                continue
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
                        new_records.append(prc)
                        # Update oldest date if necessary
                        if (rec_date < oldest_updated_date):
                            oldest_updated_date = rec_date
                    else:
                        last_price_row.price = price
                logger.debug("update_coin_prices: 'Price' table updated "
                             "for '{}/{}'".format(crypto, currency))
            # Warning if not unicode characters are found in the JSON
            except UnicodeEncodeError as e:
                logger.warning("update_coin_prices()[2]: {}".format(e))
                continue
    for record in new_records:
        db.session.add(record)
    db.session.commit()
    # Return last date updated and oldest date updated
    last_prc_entry = Price.query.order_by(Price.date.desc()).first()
    last_dt = (last_prc_entry.date).strftime('%Y-%m-%d')
    oldest_dt = oldest_updated_date.strftime('%Y-%m-%d')
    logger.info("update_coin_prices: 'Price' table updated")
    return json.dumps({"last_dt": last_dt,
                       "oldest_dt": oldest_dt})


def update_coins(logger):
    """Gets the 'coin_num' coins by volume from CryptoCompare.
    """
    logger.info("update_coins(): Starting process")
    try:
        with urlopen("https://min-api.cryptocompare.com/data/all/coinlist"
                     "") as response:
            source = response.read()
        coins = json.loads(source)
        # If CryptoCompare respond successfully, process data:
        if coins["Response"] != 'Success':
            error = coins["Response"]
            logger.error("update_coins(): CryptoCompare error: '{}'"
                         .format(error))
            return
    except Exception as e:
        logger.error("get_coin_info(): {}".format(e))
        return
    # Delete table contents
    Crypto.query.delete()
    db.session.commit()
    # Insert new information in the table
    coins = coins["Data"]
    for coin in coins:
        try:
            # Get symbol and long_name
            symbol = coins[coin]["Symbol"]
            long_name = coins[coin]["CoinName"]
            # If Symbol has blank spaces, don't store coin (bad format)
            if " " in symbol:
                logger.warning("update_coins: Coin '{}' not stored due to "
                               "wrong symbol format (blank spaces)"
                               "".format(symbol))
                continue
            # Get Algorithm
            try:
                algorithm = coins[coin]["Algorithm"]
            except KeyError as e:
                algorithm = None
            if algorithm == 'N/A':
                algorithm = None
            # Get Consensus Type
            try:
                consensus_type = coins[coin]["ProofType"]
            except KeyError as e:
                consensus_type = None
            if consensus_type == 'N/A':
                consensus_type = None
            # Get Image URL
            try:
                image_url = coins[coin]["ImageUrl"]
            except KeyError as e:
                image_url = None
            if image_url == 'N/A':
                image_url = None
            # Get Supply
            try:
                supply = coins[coin]["TotalCoinSupply"]
            except KeyError as e:
                supply = None
            try:
                supply = float(supply)
            except ValueError as e:
                supply = None
            # Insert coin in DB
            c = Crypto(symbol=symbol,
                       long_name=long_name,
                       algorithm=algorithm,
                       consensus_type=consensus_type,
                       supply=supply,
                       image_url=image_url)
            db.session.add(c)
            db.session.commit()
        # Warning if unicode characters are found in the JSON
        except UnicodeEncodeError as e:
            logger.warning("update_coins() [UnicodeEncodeError] [{}]: {}"
                           .format(symbol, e))
            continue
        except KeyError as e:
            logger.warning("update_coins() [KeyError] [{}]: {}"
                           .format(symbol, e))
            continue
    logger.info("update_coins(): 'COINS' updated")


def check_price_history():
    cryptos = db.session.query(Price.coin).distinct(Price.coin).all()
    cryptos = [item[0] for item in cryptos]
    currencies = db.session.query(Price.currency)\
                           .distinct(Price.currency).all()
    currencies = [item[0] for item in currencies]
    for crypto in cryptos:
        for currency in currencies:
            prev_prev_prev = None
            prev_prev = None
            prev = None
            prices = Price.query.filter_by(coin=crypto, currency=currency)\
                                .all()
            for prc in prices:
                if ((prc.price != 0) and (prc.price == prev) and
                        (prc.price == prev_prev) and
                        (prc.price == prev_prev_prev)):
                    print("History warning: {}".format(prc))
                prev_prev_prev = prev_prev
                prev_prev = prev
                prev = prc.price


def import_manual_hst(file):
    try:
        with open(file, "r", encoding='utf-8') as f:
            f_contents = f.readlines()
    except Exception as e:
        err = FileLineError("-",
                            "Error al leer el fichero '{}'".format(file),
                            "")
        return err
    # Loop for each line
    for line_num, line in enumerate(f_contents):
        # Replace '' for None (otherwise, it does not import)
        coin, curr, date, prc = (line.replace("\n", "")).split("¬")
        date = datetime.datetime.strptime(date, "%Y-%m-%d")
        # Query price to replace
        price = Price.query.filter_by(coin=coin,
                                      currency=curr,
                                      date=date).first()
        price.price = prc
    db.session.commit()
    return
