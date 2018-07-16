import datetime
import json
from copy import deepcopy
from portfolio_tracker import db
from portfolio_tracker.models import (Operation, TradePL, Price, Portfolio,
                                      PriceDelta, Task)
from portfolio_tracker.config import Params
from portfolio_tracker.utils import divide, num_2_str, num_2_perc, str_2_num
from portfolio_tracker.objects import PortfolioWarning, Balance


def add_task(name, user_id=None, not_before_time=None):
    """Add tasks to the queue of tasks to be executed by the daemon in
    background.
    """
    # Only add task if it is not already queued
    add_task = False
    db_task = Task.query.filter_by(name=name,
                                   status='Pending',
                                   user_id=user_id).first()
    if db_task:
        if not_before_time is None:
            db_task.status = 'Overtaken'
            add_task = True
        elif ((db_task.not_before_time is not None) and
              (not_before_time < db_task.not_before_time)):
            db_task.status = 'Overtaken'
            add_task = True
        db.session.commit()
    if (db_task is None) or (add_task is True):
        now = datetime.datetime.now()
        task = Task(request_time=now,
                    name=name,
                    status='Pending',
                    not_before_time=not_before_time,
                    start_time=None,
                    finish_time=None,
                    user_id=user_id,
                    return_info=None)
        db.session.add(task)
        db.session.commit()


def get_last_price_dt():
    # Get last execution of 'update_prices'
    last_timestamp = (Task.query.filter_by(name='update_prices', status='OK')
                      .order_by(Task.request_time.desc())
                      .first())
    if last_timestamp:
        # Read 'return_info' to get the last available date
        ret_info = json.loads(last_timestamp.return_info)
        if ret_info:
            dt = ret_info["last_dt"]
            dt = datetime.datetime.strptime(dt, "%Y-%m-%d")
            return dt
    return None


def get_price_timestamp():
    # Get last execution of 'update_prices'
    last_timestamp = (Task.query.filter_by(name='update_prices', status='OK')
                      .order_by(Task.request_time.desc())
                      .first())
    if last_timestamp:
        # Read 'return_info' to get the last available date
        return last_timestamp.start_time
    return None


def get_price(coin, currency, logger, date=None):
    """ Gets the price of 'coin' represented in 'currency' for the date 'date'
    """
    # If no date was provided, get price for last available date
    if date is None:
        date = get_last_price_dt()
    currencies = Params.CURRENCIES
    # If coin is a currency, triangulate with 'BTC' and 'currency'
    if coin in currencies:
        if coin == currency:
            return 1
        else:
            prc_btc_currency = Price.query.filter_by(coin='BTC',
                                                     currency=currency,
                                                     date=date).first()
            prc_btc_coin = Price.query.filter_by(coin='BTC',
                                                 currency=coin,
                                                 date=date).first()
            if ((prc_btc_currency and prc_btc_coin) and
                    (prc_btc_coin.price != 0)):
                return prc_btc_currency.price / prc_btc_coin.price
            else:
                logger.info("get_price: Could not triangulate price for "
                            "'{}-{}' [{}]".format(coin, currency, date))
                return 0
    else:
        # If coin is a crypto, query price directly
        price = Price.query.filter_by(coin=coin,
                                      currency=currency,
                                      date=date).first()
        if price:
            return price.price
        # If there is no direct price (bad hist?), triangulate with BTC
        else:
            prc_coin_btc = Price.query.filter_by(coin=coin,
                                                 currency='BTC',
                                                 date=date).first()
            prc_btc_currency = Price.query.filter_by(coin='BTC',
                                                     currency=currency,
                                                     date=date).first()
            if (prc_coin_btc and prc_btc_currency):
                return prc_coin_btc.price * prc_btc_currency.price
            else:
                logger.debug("get_price: Could not triangulate price for "
                             "'{}-{}' [{}]".format(coin, currency, date))
                return 0


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


def calc_trade_PL(user, logger):
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
            # db.session.commit()
            if amount == 0:
                break
        return buy_cost

    """ MAIN CODE OF 'calc_trade_PL()':
    """
    currency = user.currency
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
        # If Type=='Airdrop'/'Fork'/'Income', add BUY with '0 cost'
        if ((op.type == 'Airdrop') or (op.type == 'Fork') or
                (op.type == 'Income')):
            if op.buy_coin != currency:
                trade = TradePL(date=op.date,
                                coin=op.buy_coin,
                                type='BUY',
                                amount=op.buy_amount,
                                buy_cost=0,
                                sell_income=None,
                                rem_FIFO=op.buy_amount,
                                realized_PL=None,
                                perc=None,
                                user_id=user.id)
                db.session.add(trade)
                # db.session.commit()
        # If Type=='Withdrawal'/'Expense', add fees to next SELL
        elif (op.type == 'Withdrawal') or (op.type == 'Expense'):
            if op.fee_coin == currency:
                fee_cost = op.fee_amount
            else:
                if op.fee_amount is None:
                    fee_cost = 0
                    logger.warning("calculate_trade_PL: Could not calculate "
                                   "fee cost for '{}'".format(op.type))
                else:
                    fee_cost = op.fee_amount * get_price(op.fee_coin, currency,
                                                         logger, op.date)
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
                    buy_cost = op.sell_amount * get_price(op.sell_coin,
                                                          currency,
                                                          logger,
                                                          op.date)
                trade = TradePL(date=op.date,
                                coin=op.buy_coin,
                                type='BUY',
                                amount=op.buy_amount,
                                buy_cost=buy_cost,
                                sell_income=None,
                                rem_FIFO=op.buy_amount,
                                realized_PL=None,
                                perc=None,
                                user_id=user.id)
                db.session.add(trade)
                # db.session.commit()
            # Handle SELL section
            if op.sell_coin != currency:
                if op.buy_coin == currency:
                    sell_income = op.buy_amount
                else:
                    sell_income = op.sell_amount * get_price(op.sell_coin,
                                                             currency,
                                                             logger,
                                                             op.date)
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
                        sell_income -= op.fee_amount * get_price(op.fee_coin,
                                                                 currency,
                                                                 logger,
                                                                 op.date)
                        substract_FIFO_quant(op.fee_coin, op.fee_amount)
                realized_PL = sell_income - buy_cost
                if buy_cost == 0:
                    perc = None
                else:
                    perc = round(realized_PL / buy_cost, 4)
                    if perc > 1000000:
                        perc = None
                trade = TradePL(date=op.date,
                                coin=op.sell_coin,
                                type='SELL',
                                amount=op.sell_amount,
                                buy_cost=buy_cost,
                                sell_income=sell_income,
                                rem_FIFO=None,
                                realized_PL=realized_PL,
                                perc=perc,
                                user_id=user.id)
                db.session.add(trade)
                # db.session.commit()
        # If Type is not recognized, warn and jump to next
        else:
            logger.warning("calculate_trade_PL: Operation type not recognized "
                           "({}). Row skipped".format(op.type))
            continue
    db.session.commit()
    logger.info(f"calc_trade_PL: Trades updated for '{user}'")


def calc_portfolio_history(user_id, curr, logger):
    """Calculates all the portfolio history of 'user' and stores the result
    in 'Portfolio' table.
    Returns a list with the warnings found during the process.
    """

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

    def rm_from_portfolio_evol(date, exch, coin, amount, dic):
        """ Removes 'amount' from 'date|exch|coin' and returns back 'dic'.
        If the entry is not found, it displays a warning.
        If the amount to be removed is greater than the available amount,
        display warning.
        The available amount is rounded to avoid spurious numbers.
        If the entry is entirely consumed, it is deleted.
        """
        warning = None
        if exch not in dic.keys():
            warning = ("El exchange '{}' no existe en la cartera para "
                       "poder anotar la siguiente operación de venta: "
                       "('{}|{}|{}|{}')"
                       .format(exch, date, exch, coin, amount))
            logger.debug("rm_from_portfolio_evol: {}".format(warning))
            return [dic, warning]
        elif coin not in dic[exch].keys():
            warning = ("La moneda '{}' no existe en la cartera para "
                       "poder anotar la siguiente operación de venta: "
                       "('{}|{}|{}|{}')"
                       .format(coin, date, exch, coin, amount))
            logger.debug("rm_from_portfolio_evol: {}".format(warning))
            return [dic, warning]
        avail_amount = round(dic[exch][coin]["Amount"], 8)
        # If attempting to remove more than available, display warning
        if amount > avail_amount:
            warning = ("Operación de venta por importe superior al saldo "
                       "disponible en ese momento ('{}' Vs '{}'): "
                       "'{}|{}|{}|{}'".format(amount, avail_amount, date, exch,
                                              coin, amount))
            logger.debug("rm_from_portfolio_evol: {}".format(warning))
        # Remove amount from dic
        dic[exch][coin]["Amount"] = dic[exch][coin]["Amount"] - amount
        dic[exch][coin]["Amount"] = round(dic[exch][coin]["Amount"], 8)
        logger.debug("rm_from_portfolio_evol: '{}' removed from '{}|{}|{}'"
                     " ('{}' remaining)".format(amount, date,
                                                exch, coin,
                                                dic[exch][coin]["Amount"]))
        if amount == avail_amount:
            logger.debug("rm_from_portfolio_evol: Entry removed: "
                         "'{}|{}|{}'".format(date, exch, coin))
            del dic[exch][coin]
            if (len(dic[exch].items()) == 0):
                del dic[exch]
        return [dic, warning]

    def calc_portfolio_value(dic, date, curr):
        """ Updates the portfolio value with the prices of the given date and
        returns the modified dic.
        """
        for exch in dic.keys():
            for coin in dic[exch].keys():
                amount = dic[exch][coin]["Amount"]
                value = amount * get_price(coin, curr, logger, date)
                dic[exch][coin]["Value"] = value
        return dic

    """ MAIN CODE OF 'calc_portfolio_history()':
    """
    logger.info("calc_portfolio_history: Generating portfolio history for "
                "user_id '{}'".format(user_id))
    # Variable that will be returned
    warning_list = []
    # Variable that will store all the calcs before submitting them to DB
    portfolio_evol = {}
    # Calculate initial and final dates to loop through
    first_user_op = Operation.query.filter_by(user_id=user_id)\
        .order_by(Operation.date).first()
    print("first_user_op: {}".format(first_user_op))
    if first_user_op is None:
        logger.warning("calc_portfolio_history: No operations found for "
                       "user {}. Exiting...".format(user_id))
        return 0
    calc_date = first_user_op.date
    calc_date_str = calc_date.strftime('%Y-%m-%d')
    last_date = get_last_price_dt()
    # Loop for each date
    rolling_dic = {}
    while (calc_date <= last_date):
        date_ops = Operation.query.filter_by(user_id=user_id, date=calc_date)
        # Loop for each operation for the date under analysis
        for op in date_ops:
            # If Type=="Deposit"/"Airdrop"/"Fork"/"Income"
            if op.type in ["Deposit", "Airdrop", "Fork", "Income"]:
                # Add BUY coins
                rolling_dic = add_to_portfolio_evol(calc_date_str,
                                                    op.exchange,
                                                    op.buy_coin,
                                                    op.buy_amount,
                                                    rolling_dic)
            # If Type=="Trade"
            if op.type in ["Withdrawal", "Expense"]:
                # Remove 'SELL' coins
                rolling_dic, warn = rm_from_portfolio_evol(calc_date_str,
                                                           op.exchange,
                                                           op.sell_coin,
                                                           op.sell_amount,
                                                           rolling_dic)
                if warn:
                    warning_list.append(PortfolioWarning(warn, op))
                # Remove 'FEE' coins (if fee_coin != sell_coin)
                if op.fee_coin != op.sell_coin:
                    rolling_dic, warn = rm_from_portfolio_evol(calc_date_str,
                                                               op.exchange,
                                                               op.fee_coin,
                                                               op.fee_amount,
                                                               rolling_dic)
                    if warn:
                        warning_list.append(PortfolioWarning(warn, op))
            # If Type=="Trade"
            if op.type == "Trade":
                # Add 'BUY' coins
                rolling_dic = add_to_portfolio_evol(calc_date_str,
                                                    op.exchange,
                                                    op.buy_coin,
                                                    op.buy_amount,
                                                    rolling_dic)
                # Remove 'SELL' coins
                rolling_dic, warn = rm_from_portfolio_evol(calc_date_str,
                                                           op.exchange,
                                                           op.sell_coin,
                                                           op.sell_amount,
                                                           rolling_dic)
                if warn:
                    warning_list.append(PortfolioWarning(warn, op))
                # Remove 'FEE' coins (if fee_coin != sell_coin & buy_coin)
                if op.fee_coin not in [op.buy_coin, op.sell_coin, None]:
                    rolling_dic, warn = rm_from_portfolio_evol(calc_date_str,
                                                               op.exchange,
                                                               op.fee_coin,
                                                               op.fee_amount,
                                                               rolling_dic)
                    if warn:
                        warning_list.append(PortfolioWarning(warn, op))
        # Get portfolio value for 'calc_date'
        rolling_dic = calc_portfolio_value(rolling_dic, calc_date, curr)
        portfolio_evol.update({calc_date_str: deepcopy(rolling_dic)})
        calc_date += datetime.timedelta(days=1)
        calc_date_str = calc_date.strftime('%Y-%m-%d')
    # Delete user records from 'Portfolio' table
    db.session.query(Portfolio).filter_by(user_id=user_id).delete()
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
                                user_id=user_id)
                db.session.add(pos)
    db.session.commit()
    logger.info("calc_portfolio_history: 'Portfolio' updated for user '{}'"
                .format(user_id))
    return warning_list


def calc_balance(user, currency, logger):
    """ Calculates the balance of the user for the last date for which there
    are prices in the database, and stores it in 'Balance' objects.
    """
    # Update trades&portfolio if necessary
    last_pf_entry = Portfolio.query.filter_by(user_id=user.id)\
                                   .order_by(Portfolio.date.desc()).first()
    calc_date = get_last_price_dt()
    if (last_pf_entry is None) or (last_pf_entry.date < calc_date):
        calc_portfolio_history(user, logger)
    # Get user data
    user_pos_today = Portfolio.query.filter_by(user_id=user.id,
                                               date=calc_date).all()
    user_coins = db.session.query(Portfolio.coin)\
                           .filter_by(user_id=user.id)\
                           .distinct(Portfolio.coin).all()
    user_trades = TradePL.query.filter_by(user_id=user.id).all()
    # Calc total portfolio value
    total_value = 0
    for pos in user_pos_today:
        total_value += pos.value
    # Loop for each coin in today's user portfolio
    balances = []
    for coin in user_coins:
        # Sum Amount & Value of all exchanges
        tot_coin_amt = 0
        tot_coin_val = 0
        # Get current coin price
        last_coin_prc = get_price(coin.coin, currency, logger)
        # Calc coin totals
        for pos in user_pos_today:
            if coin.coin == pos.coin:
                tot_coin_amt += pos.amount
                tot_coin_val += pos.value
        # Calculate BTC Value
        tot_coin_val_btc = btc_value(tot_coin_val, currency, calc_date)
        # Calculate portfolio percentage
        coin_perc = round(tot_coin_val / total_value, 4)
        # Calculate Realized & UnRealized P&L
        realized_PL = 0
        unrealized_PL = 0
        for trade in user_trades:
            if coin.coin == trade.coin:
                if trade.type == 'BUY':
                    if trade.amount != 0:
                        unrealized_PL += (trade.rem_FIFO * (last_coin_prc -
                                                            (trade.buy_cost / trade.amount)))
                elif trade.type == 'SELL':
                    realized_PL += trade.realized_PL
        # Round numbers
        try:
            prev_val = tot_coin_val - unrealized_PL
            unrealized_perc = (tot_coin_val - prev_val) / prev_val
            if abs(unrealized_perc) > 1000:
                unrealized_perc = None
        except ZeroDivisionError as e:
            unrealized_perc = None
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
                              perc=coin_perc,
                              value_btc=tot_coin_val_btc,
                              realized_PL=realized_PL,
                              unrealized_PL=unrealized_PL,
                              unrealized_perc=unrealized_perc,
                              total_PL=total_PL)
        balances.append(balance_row)
    logger.info("calc_balance: 'Balance' calculated for user {}"
                .format(user.id))
    # Return calculated values
    return balances


# def calc_tot_value(balance, logger):
#     """Calculates the total portfolio balance of the given 'balance'
#     """
#     non_cryptos = Params.NON_CRYPTOS
#     tot_value = 0
#     for coin in balance:
#         if coin.coin not in non_cryptos:
#             tot_value += coin.value
#     return round(tot_value, 2)


# def calc_tot_pf_cost(user, logger, date=None):
#     """Calculates the total cost of the portfolio of the given 'user'.
#     If a specific date is requested, it returns the total cost for that date.
#     Otherwise, it returns a list with all dates: [[<date1>, <cost_dt_1>],...]
#     """
#     if date is None:
#         date = get_last_price_dt()
#     ops = Operation.query.filter_by(user_id=user.id)
#     currencies = Params.CURRENCIES
#     total_cost = 0
#     for op in ops:
#         # Only consider operations <= date. Otherwise, skip operation
#         if date < op.date:
#             continue
#         # If 'op' is a Deposit of a 'currency', add to total cost
#         if op.type == 'Deposit' and op.buy_coin in currencies:
#             if op.buy_coin == user.currency:
#                 total_cost += op.buy_amount
#             else:
#                 prc = get_price(op.buy_coin, user.currency, logger, op.date)
#                 total_cost += op.buy_amount * prc
#         # If 'op' is a Withdrawal of a 'currency', remove from total cost
#         if op.type == 'Withdrawal' and op.sell_coin in currencies:
#             if op.sell_coin == user.currency:
#                 total_cost -= op.sell_amount
#             else:
#                 prc = get_price(op.sell_coin, user.currency, logger, op.date)
#                 total_cost -= op.sell_amount * prc
#     return round(total_cost, 2)


def calc_tot_pf_cost(user, logger, date=None):
    """Calculates the total cost of the portfolio of the given 'user'.
    If a specific date is requested, it returns the total cost for that date.
    Otherwise, it returns a dic with all dates: {<date1>: <cost_dt_1>,...}
    """

    def add_to_pf_cost(cost, op):
        total_cost = cost
        # If 'op' is a Deposit of a 'currency', add to total cost
        if op.type == 'Deposit' and op.buy_coin in currencies:
            if op.buy_coin == user.currency:
                total_cost += op.buy_amount
            else:
                prc = get_price(op.buy_coin, user.currency, logger, op.date)
                total_cost += op.buy_amount * prc
        # If 'op' is a Withdrawal of a 'currency', remove from total cost
        if op.type == 'Withdrawal' and op.sell_coin in currencies:
            if op.sell_coin == user.currency:
                total_cost -= op.sell_amount
            else:
                prc = get_price(op.sell_coin, user.currency, logger, op.date)
                total_cost -= op.sell_amount * prc
        return total_cost

    """MAIN CODE FOR 'calc_tot_pf_cost'"""
    ops = Operation.query.filter_by(user_id=user.id)\
                         .order_by(Operation.date).all()
    currencies = Params.CURRENCIES
    total_costs = {}
    cost_by_date = 0
    if ops:
        calc_date = ops[0].date
    for op in ops:
        if op.date <= calc_date:
            cost_by_date = add_to_pf_cost(cost_by_date, op)
        else:
            # Store costs for all pending dates
            while (op.date > calc_date):
                # If arrived to requered date, return cost
                if calc_date == date:
                    return cost_by_date
                calc_date_str = calc_date.strftime('%Y-%m-%d')
                total_costs.update({calc_date_str: round(cost_by_date, 2)})
                calc_date += datetime.timedelta(days=1)
            # Add cost of current operation
            cost_by_date = add_to_pf_cost(cost_by_date, op)
    # Store dates until today
    last_dt = get_last_price_dt()
    while (last_dt >= calc_date):
        # If arrived to requered date, return cost
        if calc_date == date:
            return cost_by_date
        calc_date_str = calc_date.strftime('%Y-%m-%d')
        total_costs.update({calc_date_str: round(cost_by_date, 2)})
        calc_date += datetime.timedelta(days=1)
    # If no date was provided, return array with costs
    return total_costs


def calc_pnl_history(user, logger):
    """Calculates the daily evolution of the portfolio of the given user.
    Returns a dictionary containing the value in currency & BTC for each date.
    """
    currency = user.currency
    hst_dic = {}
    portf_history = Portfolio.query.filter_by(user_id=user.id)\
                                   .order_by(Portfolio.date).all()
    if portf_history is None:
        logger.warning("calc_portfolio_evol: No recors found in 'Portfolio'"
                       "for '{}'".format(user))
        return {}
    # Get total portfolio cost for each date
    tot_cost_by_date = calc_tot_pf_cost(user, logger)
    # Loop for each row in portfolio history
    calc_date = portf_history[0].date
    pnl = 0
    pnl_btc = 0
    portf = 0
    portf_btc = 0
    first_date = True
    prev_portf = None
    prev_portf_btc = None
    prev_pnl = None
    prev_pnl_btc = None
    for idx, row in enumerate(portf_history):
        # While date does not change, sum values
        if row.date == calc_date:
            portf += row.value
            portf_btc += row.value_btc
        # If date changes, store results and initialize variables
        if (row.date != calc_date) or (idx + 1 == len(portf_history)):
            pnl = portf - tot_cost_by_date[calc_date.strftime('%Y-%m-%d')]
            pnl_btc = portf_btc - btc_value(pnl, currency, calc_date)
            if first_date:
                portf_dif = '-'
                portf_dif_perc = '-'
                portf_btc_dif = '-'
                portf_btc_dif_perc = '-'
                pnl_dif = '-'
                pnl_dif_perc = '-'
                pnl_btc_dif = '-'
                pnl_btc_dif_perc = '-'
                first_date = False
            else:
                portf_dif = portf - prev_portf
                portf_dif_perc = divide(portf_dif, prev_portf)
                portf_btc_dif = portf_btc - prev_portf_btc
                portf_btc_dif_perc = divide(portf_btc_dif, prev_portf_btc)
                pnl_dif = pnl - prev_pnl
                pnl_dif_perc = divide(pnl_dif, prev_pnl)
                pnl_btc_dif = pnl_btc - prev_pnl_btc
                pnl_btc_dif_perc = divide(pnl_btc_dif, prev_pnl_btc)
            # Save values for next iteration before formating
            prev_portf = portf
            prev_portf_btc = portf_btc
            prev_pnl = pnl
            prev_pnl_btc = pnl_btc
            # Format outputs and insert
            portf = num_2_str(portf, currency, 0)
            portf_dif = num_2_str(portf_dif, currency, 0)
            portf_dif_perc = num_2_perc(portf_dif_perc, 2)
            portf_btc = num_2_str(portf_btc, 'BTC', 4)
            portf_btc_dif = num_2_str(portf_btc_dif, 'BTC', 4)
            portf_btc_dif_perc = num_2_perc(portf_btc_dif_perc, 2)
            pnl = num_2_str(pnl, currency, 0)
            pnl_dif = num_2_str(pnl_dif, currency, 0)
            pnl_dif_perc = num_2_perc(pnl_dif_perc, 2)
            pnl_btc = num_2_str(pnl_btc, 'BTC', 4)
            pnl_btc_dif = num_2_str(pnl_btc_dif, 'BTC', 4)
            pnl_btc_dif_perc = num_2_perc(pnl_btc_dif_perc, 2)
            date_str = calc_date.strftime('%Y-%m-%d')
            hst_dic.update({date_str: {"portf": portf,
                                       "portf-Dif": portf_dif,
                                       "portf-DifPerc": portf_dif_perc,
                                       "portfBTC": portf_btc,
                                       "portfBTC-Dif": portf_btc_dif,
                                       "portfBTC-DifPerc": portf_btc_dif_perc,
                                       "pnl": pnl,
                                       "pnl-Dif": pnl_dif,
                                       "pnl-DifPerc": pnl_dif_perc,
                                       "pnlBTC": pnl_btc,
                                       "pnlBTC-Dif": pnl_btc_dif,
                                       "pnlBTC-DifPerc": pnl_btc_dif_perc}})
            # Set variables for next date iteration
            calc_date = row.date
            portf = row.value
            portf_btc = row.value_btc
            pnl = None
            pnl_btc = None
    # Return result
    logger.info("calc_portfolio_evol: Portfolio evolution calculated "
                "for '{}'".format(user))
    return hst_dic


def get_portfolio_by_date(user, date, logger):
    """Gets the portfolio status of a given date.
    """
    # hst_dic = {}
    portf_history = Portfolio.query.filter_by(user_id=user.id, date=date)\
                                   .order_by(Portfolio.date).all()
    if portf_history is None:
        logger.warning("calc_portfolio_evol: No recors found in 'Portfolio'"
                       "for '{}'".format(user))
        return {}


def calc_exch_summary(split_portf, curr):
    """Given a dic of a Position spplited by exchanges,
    calculates the summary.
    """
    # Calculate exchange summary
    exch_summary = {}
    for exch in split_portf:
        value = 0
        value_btc = 0
        for pos in split_portf[exch]:
            value += pos.value
            value_btc += pos.value_btc
        exch_summary.update({exch: {'value': value, 'value_btc': value_btc}})
    return exch_summary


def calc_price_deltas(logger):
    """Calculates the percentage of variation in price from today
    and 1D/7D/1M/3M/6M/1Y/2Y in the past.
    """

    def calc_coin_delta(today, delta, crypto, currency):
        """Calculates the percentage of variation in price from today
        and 'delta' days before, for 'crypto/currency' pair.
        """
        # Get price today
        prc_today = Price.query.filter_by(coin=crypto,
                                          currency=currency,
                                          date=today).first()
        if prc_today:
            prc_today = prc_today.price
        else:
            prc_today = 0
        # Get price previous day
        prev_date = today - datetime.timedelta(days=delta)
        prev_prc = Price.query.filter_by(coin=crypto,
                                         currency=currency,
                                         date=prev_date).first()
        # Calc delta
        if prev_prc and prev_prc.price != 0:
            return round((prc_today - prev_prc.price) / prev_prc.price, 4)
        return None

    """MAIN CODE FOR 'calc_price_deltas'"""
    logger.info("calc_price_deltas: Updating price deltas...")
    # Delete user records from PriceDelta
    db.session.query(PriceDelta).delete()
    # Get cryptos that exist in DB ('Operation' table):
    cryptos = db.session.query(Operation.buy_coin)\
                        .distinct(Operation.buy_coin).all()
    if cryptos:
        cryptos = [item[0] for item in cryptos]
        # Remove non-cryptos from list of cryptos
        non_cryptos = Params.NON_CRYPTOS
        for item in non_cryptos:
            try:
                cryptos.remove(item)
            except ValueError as e:
                continue
        logger.debug("calc_price_deltas: Coins found in Trades after"
                     " cleaning ({}): {}".format(len(cryptos), cryptos))
    else:
        logger.error("calc_price_deltas: No cryptos found "
                     "in 'Operation' table")
    pass
    # Update prices for each Crypto and Currency managed in the system:
    currencies = Params.CURRENCIES + ['BTC']
    # Loop for each crypto & currency
    today = get_last_price_dt()
    for crypto in cryptos:
        for currency in currencies:
            if crypto == currency:
                # Insert row
                delta_row = PriceDelta(coin=crypto,
                                       currency=currency,
                                       delta_1d=None,
                                       delta_7d=None,
                                       delta_1m=None,
                                       delta_3m=None,
                                       delta_6m=None,
                                       delta_1y=None,
                                       delta_2y=None)
                db.session.add(delta_row)
                continue
            # Get previous prices
            delta_1d = calc_coin_delta(today, 1, crypto, currency)
            delta_7d = calc_coin_delta(today, 7, crypto, currency)
            delta_1m = calc_coin_delta(today, 30, crypto, currency)
            delta_3m = calc_coin_delta(today, 91, crypto, currency)
            delta_6m = calc_coin_delta(today, 182, crypto, currency)
            delta_1y = calc_coin_delta(today, 365, crypto, currency)
            delta_2y = calc_coin_delta(today, 720, crypto, currency)
            # Insert row
            delta_row = PriceDelta(coin=crypto,
                                   currency=currency,
                                   delta_1d=delta_1d,
                                   delta_7d=delta_7d,
                                   delta_1m=delta_1m,
                                   delta_3m=delta_3m,
                                   delta_6m=delta_6m,
                                   delta_1y=delta_1y,
                                   delta_2y=delta_2y)
            db.session.add(delta_row)
    db.session.commit()
    logger.info("calc_price_deltas: 'PriceDelta' updated")


def calc_portfolio_deltas(user, logger):
    """Calculates the percentage of variation of the portfolio and P&L
    between today and 1D/7D/1M/3M/6M/1Y/2Y in the past.
    """
    # Return dictionary
    curr = user.currency
    d = {curr: {'Portfolio': {'Value': None,
                              '1D': {'Dif': None, 'Perc': None},
                              '7D': {'Dif': None, 'Perc': None},
                              '1M': {'Dif': None, 'Perc': None},
                              '3M': {'Dif': None, 'Perc': None},
                              '6M': {'Dif': None, 'Perc': None},
                              '1Y': {'Dif': None, 'Perc': None},
                              '2Y': {'Dif': None, 'Perc': None}},
                'P&L': {'Value': None,
                        '1D': {'Dif': None, 'Perc': None},
                        '7D': {'Dif': None, 'Perc': None},
                        '1M': {'Dif': None, 'Perc': None},
                        '3M': {'Dif': None, 'Perc': None},
                        '6M': {'Dif': None, 'Perc': None},
                        '1Y': {'Dif': None, 'Perc': None},
                        '2Y': {'Dif': None, 'Perc': None}}},
         'BTC': {'Portfolio': {'Value': None,
                               '1D': {'Dif': None, 'Perc': None},
                               '7D': {'Dif': None, 'Perc': None},
                               '1M': {'Dif': None, 'Perc': None},
                               '3M': {'Dif': None, 'Perc': None},
                               '6M': {'Dif': None, 'Perc': None},
                               '1Y': {'Dif': None, 'Perc': None},
                               '2Y': {'Dif': None, 'Perc': None}},
                 'P&L': {'Value': None,
                         '1D': {'Dif': None, 'Perc': None},
                         '7D': {'Dif': None, 'Perc': None},
                         '1M': {'Dif': None, 'Perc': None},
                         '3M': {'Dif': None, 'Perc': None},
                         '6M': {'Dif': None, 'Perc': None},
                         '1Y': {'Dif': None, 'Perc': None},
                         '2Y': {'Dif': None, 'Perc': None}}}}
    # Calc portfolio evolution
    evol = calc_pnl_history(user, logger)
    # Get today's values
    today = get_last_price_dt()
    today_str = today.strftime('%Y-%m-%d')
    found_today = False
    pf_today = None
    pf_today_btc = None
    pnl_today = None
    pnl_today_btc = None
    for item in evol:
        if today_str == item:
            found_today = True
            pf_today = evol[item]['portf']
            pnl_today = evol[item]['pnl']
            pf_today_btc = evol[item]['portfBTC']
            pnl_today_btc = evol[item]['pnlBTC']
            # Store in dictionary
            d[curr]['Portfolio']['Value'] = pf_today
            d[curr]['P&L']['Value'] = pnl_today
            d['BTC']['Portfolio']['Value'] = pf_today_btc
            d['BTC']['P&L']['Value'] = pnl_today_btc
            # Convert to Float
            pf_today = str_2_num(pf_today)
            pnl_today = str_2_num(pnl_today)
            pf_today_btc = str_2_num(pf_today_btc)
            pnl_today_btc = str_2_num(pnl_today_btc)
            break
    if not found_today:
        logger.error("calc_portfolio_deltas: '{}' not found in portfolio "
                     "evolution".format(today_str))
        return d
    # Calc delta dates
    dt_array = [['1D', 1], ['7D', 7], ['1M', 30], ['3M', 91],
                ['6M', 182], ['1Y', 365], ['2Y', 720]]
    find_dates = []
    for item in dt_array:
        prev_date = today - datetime.timedelta(days=item[1])
        find_dates.append(prev_date.strftime('%Y-%m-%d'))
    # Loop to get all the dates
    num_dates_to_find = len(find_dates)
    for dt in evol:
        if dt in find_dates:
            pf_prev = str_2_num(evol[dt]['portf'])
            pnl_prev = str_2_num(evol[dt]['pnl'])
            pf_prev_btc = str_2_num(evol[dt]['portfBTC'])
            pnl_prev_btc = str_2_num(evol[dt]['pnlBTC'])
            # Calculate and absolute variations
            term = dt_array[find_dates.index(dt)][0]
            pf_dif = pf_today - pf_prev
            pnl_dif = pnl_today - pnl_prev
            pf_dif_btc = pf_today_btc - pf_prev_btc
            pnl_dif_btc = pnl_today_btc - pnl_prev_btc
            # Calculate percentage variations
            if pf_prev != 0:
                pf_perc = (pf_today - pf_prev) / pf_prev
            if pnl_prev != 0:
                pnl_perc = (pnl_today - pnl_prev) / pnl_prev
            if pf_prev_btc != 0:
                pf_perc_btc = (pf_today_btc - pf_prev_btc) / pf_prev_btc
            if pnl_prev_btc != 0:
                pnl_perc_btc = (pnl_today_btc - pnl_prev_btc) / pnl_prev_btc
            # Store results (in String format)
            d[curr]['Portfolio'][term]['Dif'] = num_2_str(pf_dif, curr, 0)
            d[curr]['P&L'][term]['Dif'] = num_2_str(pnl_dif, curr, 0)
            d['BTC']['Portfolio'][term]['Dif'] = num_2_str(pf_dif_btc, 'BTC', 4)
            d['BTC']['P&L'][term]['Dif'] = num_2_str(pnl_dif_btc, 'BTC', 4)
            d[curr]['Portfolio'][term]['Perc'] = num_2_perc(pf_perc, 2)
            d[curr]['P&L'][term]['Perc'] = num_2_perc(pnl_perc, 2)
            d['BTC']['Portfolio'][term]['Perc'] = num_2_perc(pf_perc_btc, 2)
            d['BTC']['P&L'][term]['Perc'] = num_2_perc(pnl_perc_btc, 2)
            # Substract 1 to exit loop as soon as possible
            num_dates_to_find -= 1
        if num_dates_to_find == 0:
            break
    logger.info("calc_portfolio_deltas: Calculation performed for user {}"
                .format(user.id))
    return d
