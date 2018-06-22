import datetime
import json
from copy import deepcopy
from flaskblog import db
from flaskblog.models import (Operation, TradePL, Price, Portfolio,
                              Balance)
from flaskblog.config import Params


def fx_exchange(coin, currency, amount, date, logger):
    """Performs the FX exchange of 'amount' from 'coin' to 'currency'
    for the prices available for the given 'date'.
    The result is rounded to 8 decimals.
    """
    coin_price = Price.query.filter_by(coin=coin,
                                       currency=currency,
                                       date=date).first()
    if coin_price is None:
        logger.warning("fx_exchange: No price found for '{}/{}' for "
                       "date '{}'".format(coin, currency, date))
        return 0
    return round(coin_price.price * amount, 8)


def btc_value(coin_value, currency, date):
    """Calculates the BTC value of 'coin_value' (provided in 'currency' units)
    for the given date.
    """
    btc_price = db.session.query(Price.price)\
                          .filter_by(coin='BTC', currency=currency, date=date)\
                          .first()
    if btc_price and (btc_price != 0):
        return round(coin_value / btc_price[0], 8)
    return 0


def calc_trade_PL(user, currency, logger):
    """Calculate the realized P&L of all the operations.
    """

    def substract_FIFO_quant(coin, amount):
        """Applies FIFO to substract the given 'amount' from the oldest
        recors available for the given 'coin'.
        Returns the cost value of the deducted coins measured in 'currency'.
        """
        buy_cost = 0
        buy_ops = TradePL.query.filter_by(user_id=user.id,
                                          coin=coin,
                                          type='BUY').all()
        for buy_op in buy_ops:
            # If OP already consumed, jump to next
            if buy_op.rem_FIFO == 0:
                continue
            # If amount search greater than remaining, remove all
            if amount > buy_op.rem_FIFO:
                buy_cost += buy_op.rem_FIFO * buy_op.buy_cost / buy_op.amount
                amount = round(amount - buy_op.rem_FIFO, 8)
                buy_op.rem_FIFO = 0
            # If amount search smaller than remaining, remove partially
            else:
                buy_cost += amount * buy_op.buy_cost / buy_op.amount
                buy_op.rem_FIFO = round(buy_op.rem_FIFO - amount, 8)
                amount = 0
            db.session.commit()
            if amount == 0:
                break
        return buy_cost

    """ MAIN CODE OF 'calc_trade_PL()':
    """
    # Variable to store fees pending to be substracted from Sells
    pend_fees = {}
    # Get trades from DB
    ops = Operation.query.filter_by(user_id=user.id).all()
    if len(ops) == 0:
        logger.error("calculate_trade_PL: No trade found. Calculation skipped")
        return None
    # Delete user records from TRADE_PL
    db.session.query(TradePL).filter_by(user_id=user.id).delete()
    db.session.commit()
    # Loop for each trade
    for op in ops:
        # If Type=='Airdrop/Fork'/'Income', add BUY with '0 cost'
        if (op.type == 'Airdrop/Fork') or (op.type == 'Income'):
            if op.buy_coin != currency:
                trade = TradePL(date=op.date,
                                coin=op.buy_coin,
                                type='BUY',
                                amount=op.buy_amount,
                                buy_cost=0,
                                sell_income=None,
                                rem_FIFO=op.buy_amount,
                                realized_PL=None,
                                user_id=user.id)
                db.session.add(trade)
                db.session.commit()
        # If Type=='Withdrawal'/'Expense', add fees to next SELL
        elif (op.type == 'Withdrawal') or (op.type == 'Expense'):
            if op.fee_coin == currency:
                fee_cost = op.fee_amount
            else:
                fee_cost = fx_exchange(op.fee_coin, currency,
                                       op.fee_amount, op.date, logger)
                substract_FIFO_quant(op.fee_coin, op.fee_amount)
            if op.fee_coin in pend_fees.keys():
                pend_fees[op.fee_coin] += fee_cost
            else:
                pend_fees.update({op.fee_coin: fee_cost})
        # If Type=='Deposit', do nothing
        elif op.type == 'Deposit':
            continue
        # If Type=='Trade', add BUY and SELL rows
        elif op.type == 'Trade':
            # Handle BUY section
            if op.buy_coin != currency:
                if op.sell_coin == currency:
                    buy_cost = op.sell_amount
                else:
                    buy_cost = fx_exchange(op.buy_coin, currency,
                                           op.buy_amount, op.date, logger)
                trade = TradePL(date=op.date,
                                coin=op.buy_coin,
                                type='BUY',
                                amount=op.buy_amount,
                                buy_cost=buy_cost,
                                sell_income=None,
                                rem_FIFO=op.buy_amount,
                                realized_PL=None,
                                user_id=user.id)
                db.session.add(trade)
                db.session.commit()
            # Handle SELL section
            if op.sell_coin != currency:
                if op.buy_coin == currency:
                    sell_income = op.buy_amount
                else:
                    sell_income = fx_exchange(op.sell_coin, currency,
                                              op.sell_amount, op.date,
                                              logger)
                # If there were withdraw costs pending to be included, do it
                if op.sell_coin in pend_fees.keys():
                    sell_income -= pend_fees.pop(op.sell_coin)
                # Calculate buy_cost using FIFO
                buy_cost = substract_FIFO_quant(op.sell_coin, op.sell_amount)
                # If Fees in different coin than Buy/sell_coin, add them
                if ((op.fee_coin != op.buy_coin)
                    and (op.fee_coin != op.sell_coin)
                        and (op.fee_coin is not None)):
                    if op.fee_coin == currency:
                        sell_income -= op.fee_amount
                    else:
                        sell_income -= fx_exchange(op.fee_coin, currency,
                                                   op.fee_amount, op.date,
                                                   logger)
                        substract_FIFO_quant(op.fee_coin, op.fee_amount)
                trade = TradePL(date=op.date,
                                coin=op.sell_coin,
                                type='SELL',
                                amount=op.sell_amount,
                                buy_cost=buy_cost,
                                sell_income=sell_income,
                                rem_FIFO=None,
                                realized_PL=sell_income - buy_cost,
                                user_id=user.id)
                db.session.add(trade)
                db.session.commit()
        # If Type is not recognized, warn and jump to next
        else:
            logger.warning("calculate_trade_PL: Operation type not recognized "
                           "({}). Row skipped".format(op.type))
            continue
    logger.error(f"calc_trade_PL: Trades updated for '{user}'")


def calc_portfolio_history(user, curr, logger, dest_file='portfolio.json'):

    def add_to_portfolio_evol(date, exch, coin, amount, dic):
        """ Adds 'amount' to 'date|exch|coin' and returns the modified dic.
        If the entry is not found, it creates it.
        Results are rounded to 8 decimals.
        """
        if exch not in dic.keys():
            dic.update({exch: {}})
        if coin not in dic[exch].keys():
            dic[exch].update({coin: {"Amount": amount, "Value": 99999}})
            logger.debug("add_to_portfolio_evol: New entry created: '{}|{}|{}'"
                         " ('{}' units)".format(date, exch, coin, amount))
        else:
            dic[exch][coin]["Amount"] = round(dic[exch][coin]["Amount"]
                                              + amount, 8)
            dic[exch][coin]["Value"] = 999999
            logger.debug("add_to_portfolio_evol: '{}' added to"
                         " '{}|{}|{}' ('{}' available)"
                         .format(amount, date, exch, coin,
                                 dic[exch][coin]["Amount"]))
        return dic

    def remove_from_portfolio_evol(date, exch, coin, amount, dic):
        """ Removes 'amount' from 'date|exch|coin' and returns back 'dic'.
        If the entry is not found, it displays a warning (only 'currencies are
        allowed to have a negative balance').
        If the amount to be removed is greater than the available amount,
        display warning (only 'currencies can have negative balance').
        The available amount is rounded to avoid spurious numbers.
        If the entry is entirely consumed, it is deleted.
        """
        currencies = Params.CURRENCIES
        if coin not in dic[exch].keys():
            if coin not in currencies:
                logger.warning("remove_from_portfolio_evol: Coin not found"
                               " for '{}|{}|{}|{}'".format(date, exch,
                                                           coin, amount))
                return dic
            else:
                dic[exch].update({coin: {"Amount": -amount,
                                         "Value": 99999}})
                logger.debug("remove_from_portfolio_evol: New entry created"
                             " for '{}|{}|{}' ('{}' units)"
                             .format(date, exch, coin, -amount))
                return dic
        avail_amount = round(dic[exch][coin]["Amount"], 8)
        # If attempting to remove more than available, display warning
        if (amount > avail_amount) and (coin not in currencies):
            logger.warning("remove_from_portfolio_evol: Removed more"
                           " than available ('{}' Vs '{}'): '{}|{}|{}'"
                           "".format(amount, avail_amount, date,
                                     exch, coin))
        # Remove amount from dic
        dic[exch][coin]["Amount"] = dic[exch][coin]["Amount"] - amount
        dic[exch][coin]["Amount"] = round(dic[exch][coin]["Amount"], 8)
        logger.debug("remove_from_portfolio_evol: '{}' removed from '{}|{}|{}'"
                     " ('{}' remaining)".format(amount, date,
                                                exch, coin,
                                                dic[exch][coin]["Amount"]))
        if amount == avail_amount:
            logger.debug("remove_from_portfolio_evol: Entry removed: "
                         "'{}|{}|{}'".format(date, exch, coin))
            del dic[exch][coin]
            if (len(dic[exch].items()) == 0):
                del dic[exch]
        return dic

    def calc_portfolio_value(dic, date, curr):
        """ Updates the portfolio value with the prices of the given date and
        returns the modified dic.
        """
        for exch in dic.keys():
            for coin in dic[exch].keys():
                amount = dic[exch][coin]["Amount"]
                if coin == curr:
                    value = amount
                else:
                    value = fx_exchange(coin, curr, amount, date, logger)
                dic[exch][coin]["Value"] = value
        return dic

    """ MAIN CODE OF 'calc_portfolio_history()':
    """
    # Variable that will store all the calcs before submitting them to DB
    portfolio_evol = {}
    # Calculate initial and final dates to loop through
    first_user_op = Operation.query.filter_by(user_id=user.id)\
        .order_by(Operation.date).first()
    if first_user_op is None:
        logger.warning("calc_portfolio_history: No operations found for "
                       "user {}. Exiting...".format(user.id))
        return 0
    calc_date = first_user_op.date
    calc_date_str = calc_date.strftime('%Y-%m-%d')
    last_date = get_last_price_dt()
    # Loop for each date
    rolling_dic = {}
    while (calc_date <= last_date):
        date_ops = Operation.query.filter_by(user_id=user.id, date=calc_date)
        # Loop for each operation for the date under analysis
        for op in date_ops:
            # If Type=="Deposit"/"Airdrop/Fork"/"Income"
            if op.type in ["Deposit", "Airdrop/Fork", "Income"]:
                # Add BUY coins
                rolling_dic = add_to_portfolio_evol(calc_date_str,
                                                    op.exchange,
                                                    op.buy_coin,
                                                    op.buy_amount,
                                                    rolling_dic)
            # If Type=="Trade"
            if op.type in ["Withdrawal", "Expense"]:
                # Remove 'SELL' coins
                rolling_dic = remove_from_portfolio_evol(calc_date_str,
                                                         op.exchange,
                                                         op.sell_coin,
                                                         op.sell_amount,
                                                         rolling_dic)
                # Remove 'FEE' coins (if fee_coin != sell_coin)
                if op.fee_coin != op.sell_coin:
                    rolling_dic = remove_from_portfolio_evol(calc_date_str,
                                                             op.exchange,
                                                             op.fee_coin,
                                                             op.fee_amount,
                                                             rolling_dic)
            # If Type=="Trade"
            if op.type == "Trade":
                # Add 'BUY' coins
                rolling_dic = add_to_portfolio_evol(calc_date_str,
                                                    op.exchange,
                                                    op.buy_coin,
                                                    op.buy_amount,
                                                    rolling_dic)
                # Remove 'SELL' coins
                rolling_dic = remove_from_portfolio_evol(calc_date_str,
                                                         op.exchange,
                                                         op.sell_coin,
                                                         op.sell_amount,
                                                         rolling_dic)
                # Remove 'FEE' coins (if fee_coin != sell_coin & buy_coin)
                if op.fee_coin not in [op.buy_coin, op.sell_coin, None]:
                    rolling_dic = remove_from_portfolio_evol(calc_date_str,
                                                             op.exchange,
                                                             op.fee_coin,
                                                             op.fee_amount,
                                                             rolling_dic)
        # Get portfolio value for 'calc_date'
        rolling_dic = calc_portfolio_value(rolling_dic, calc_date, curr)
        portfolio_evol.update({calc_date_str: deepcopy(rolling_dic)})
        calc_date += datetime.timedelta(days=1)
        calc_date_str = calc_date.strftime('%Y-%m-%d')
    # Save calculations in JSON file. This can be removed!
    with open(dest_file, "w") as f:
        json.dump(portfolio_evol, f)
    # Delete user records from 'Portfolio' table
    db.session.query(Portfolio).filter_by(user_id=user.id).delete()
    # Insert new information in the table
    for date_str in portfolio_evol:
        date = datetime.datetime.strptime(date_str, "%Y-%m-%d")
        btc_price = db.session.query(Price.price)\
                              .filter_by(coin='BTC', currency=curr, date=date)\
                              .first()
        for exch in portfolio_evol[date_str]:
            for coin in portfolio_evol[date_str][exch]:
                amt = portfolio_evol[date_str][exch][coin]["Amount"]
                value = portfolio_evol[date_str][exch][coin]["Value"]
                if btc_price and (btc_price[0] != 0):
                    value_btc = round(value / btc_price[0], 8)
                else:
                    value_btc = 0
                pos = Portfolio(date=date,
                                exchange=exch,
                                coin=coin,
                                amount=amt,
                                value=value,
                                value_btc=value_btc,
                                user_id=user.id)
                db.session.add(pos)
        db.session.commit()
    logger.info("calc_portfolio_history: 'Portfolio' updated for user {}"
                .format(user.id))


def calc_balance(user, currency, logger):
    """ Calculates the balance of the user for the last date for which there
    are prices in the database.
    """
    # Delete user records from 'Balance'
    db.session.query(Balance).filter_by(user_id=user.id).delete()
    db.session.commit()
    # Update trades&portfolio if necessary
    last_pf_entry = Portfolio.query.filter_by(user_id=user.id)\
                                   .order_by(Portfolio.date.desc()).first()
    calc_date = get_last_price_dt()
    if (last_pf_entry is None) or (last_pf_entry.date < calc_date):
        calc_portfolio_history(user, Params.CALC_CURRENCY, logger)
    # Get user data
    user_pos_today = Portfolio.query.filter_by(user_id=user.id,
                                               date=calc_date).all()
    user_coins = db.session.query(Portfolio.coin)\
                           .filter_by(user_id=user.id, date=calc_date)\
                           .distinct(Operation.buy_coin).all()
    user_trades = TradePL.query.filter_by(user_id=user.id).all()
    # Calc total portfolio value
    non_crypto = Params.CURRENCIES
    total_value = 0
    for pos in user_pos_today:
        if pos.coin not in non_crypto:
            total_value += pos.value
    # Loop for each coin in today's user portfolio
    for coin in user_coins:
        # Sum Amount & Value of all exchanges
        tot_coin_amt = 0
        tot_coin_val = 0
        for pos in user_pos_today:
            if coin.coin == pos.coin:
                tot_coin_amt += pos.amount
                tot_coin_val += pos.value
        # Calculate BTC Value
        tot_coin_val_btc = btc_value(tot_coin_val, currency, calc_date)
        # Calculate portfolio percentage
        if coin.coin in non_crypto:
            coin_perc = None
        else:
            coin_perc = round(tot_coin_val / total_value, 4)
        # Calculate Realized & UnRealized P&L
        realized_PL = 0
        unrealized_PL = 0
        for trade in user_trades:
            if coin.coin == trade.coin:
                if trade.type == 'BUY':
                    if trade.amount != 0:
                        unrealized_PL += (trade.rem_FIFO * trade.buy_cost /
                                          trade.amount)
                elif trade.type == 'SELL':
                    realized_PL += trade.realized_PL
        # Round numbers
        tot_coin_amt = round(tot_coin_amt, 8)
        tot_coin_val = round(tot_coin_val, 2)
        realized_PL = round(realized_PL, 2)
        unrealized_PL = round(unrealized_PL, 2)
        total_PL = realized_PL + unrealized_PL
        # Insert row
        balance_row = Balance(date=calc_date,
                              coin=coin.coin,
                              amount=tot_coin_amt,
                              value=tot_coin_val,
                              value_btc=tot_coin_val_btc,
                              perc=coin_perc,
                              realized_PL=realized_PL,
                              unrealized_PL=unrealized_PL,
                              total_PL=total_PL,
                              user_id=user.id)
        db.session.add(balance_row)
    db.session.commit()
    logger.info("calc_balance: 'Balance' updated for user {}"
                .format(user.id))
    # Return calculated values
    return Balance.query.filter_by(user_id=user.id, date=calc_date)


def calc_tot_value(balance, logger):
    """Calculates the total portfolio balance of the given 'balance'
    """
    non_cryptos = Params.NON_CRYPTOS
    tot_value = 0
    for coin in balance:
        if coin.coin not in non_cryptos:
            tot_value += coin.value
    return round(tot_value, 2)


def calc_tot_cost(balance, logger):
    """Calculates the total cost of the given 'balance'
    """
    non_cryptos = Params.NON_CRYPTOS
    tot_cost = 0
    for coin in balance:
        if coin.coin in non_cryptos:
            tot_cost += coin.value
    return round(tot_cost, 2)


def calc_portfolio_evol(user, currency, logger):
    """Calculates the daily evolution of the portfolio of the given user.
    Returns a dictionary containing the value in currency & BTC for each date.
    """
    hst_dic = {}
    portf_history = Portfolio.query.filter_by(user_id=user.id)\
                                   .order_by(Portfolio.date).all()
    if portf_history is None:
        logger.warning("calc_portfolio_evol: No recors found in 'Portfolio'"
                       "for '{}'".format(user))
        return {}
    # If Portfolio is not up-to-date, recalculate it
    last_price_dt = get_last_price_dt()
    last_portf_dt = portf_history[len(portf_history)-1].date
    if last_price_dt != last_portf_dt:
        calc_portfolio_history(user, currency, logger)
        portf_history = Portfolio.query.filter_by(user_id=user.id)\
                                       .order_by(Portfolio.date).all()
        if portf_history is None:
            logger.warning("calc_portfolio_evol: No recors found in "
                           "'Portfolio' for '{}'".format(user))
            return {}
    # Loop for each row in portfolio history
    calc_date = portf_history[0].date
    calc_val = 0
    calc_val_btc = 0
    for idx, row in enumerate(portf_history):
        # While date does not change, sum values
        if row.date == calc_date:
            calc_val += row.value
            calc_val_btc += row.value_btc
        # If date changes, store results and initialize variables
        if (row.date != calc_date) or (idx + 1 == len(portf_history)):
            calc_val = round(calc_val, 2)
            calc_val_btc = round(calc_val_btc, 8)
            date_str = calc_date.strftime('%Y-%m-%d')
            hst_dic.update({date_str: {"Value": calc_val,
                                       "ValueBTC": calc_val_btc}})
            calc_date = row.date
            calc_val = row.value
            calc_val_btc = row.value_btc
    logger.info("calc_portfolio_evol: Portfolio evolution calculated "
                "for '{}'".format(user))
    return hst_dic


def get_last_price_dt():
    last_price_dt = db.session.query(Price.date)\
                              .order_by(Price.date.desc()).first()
    if last_price_dt:
        return last_price_dt[0]
    return None
