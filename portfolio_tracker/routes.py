import os
import secrets
import datetime
from PIL import Image
from collections import OrderedDict
from flask import render_template, url_for, flash, redirect, request, abort
from portfolio_tracker import app, db, bcrypt, mail
from portfolio_tracker.forms import (RegistrationForm, LoginForm,
                                     UpdateAccountForm, RequestResetForm,
                                     ResetPasswordForm, EditOperationForm,
                                     ImportOperationsForm)
from portfolio_tracker.models import (User, Portfolio, TradePL, Price,
                                      Operation, PriceDelta)
from flask_login import login_user, current_user, logout_user, login_required
from flask_mail import Message
from portfolio_tracker.calculations import (calc_balance, calc_tot_pf_cost,
                                            get_last_price_dt,
                                            calc_pnl_history,
                                            calc_exch_summary,
                                            calc_portfolio_deltas,
                                            calc_portfolio_history,
                                            add_task,
                                            get_price_timestamp)
from portfolio_tracker.info_fetcher import import_operations_file
from portfolio_tracker.config import Params
from portfolio_tracker.utils import (set_logger, num_2_str, num_2_perc,
                                     split_portf_by_exch)

# Start logging
logger = set_logger('logs/Main.log', 'main')


def check_if_ops(user):
    """Check whether the user has operations or not in the database.
    """
    ops = Operation.query.filter_by(user_id=user.id).all()
    if ops:
        return True
    return False


@app.route("/register", methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('home'))
    form = RegistrationForm()
    if form.validate_on_submit():
        hashed_password = bcrypt.generate_password_hash(form.password.data)\
                                .decode('utf-8')
        user = User(username=form.username.data,
                    email=form.email.data,
                    password=hashed_password,
                    currency=form.currency.data)
        db.session.add(user)
        db.session.commit()
        flash('Your account has been created! You are now able to log in',
              'success')
        return redirect(url_for('login'))
    return render_template('register.html', title='Register', form=form)


@app.route("/login", methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user and bcrypt.check_password_hash(user.password,
                                               form.password.data):
            login_user(user, remember=form.remember.data)
            next_page = request.args.get('next')
            if next_page:
                return redirect(next_page)
            else:
                return redirect(url_for('dashboard'))
        else:
            flash('Login Unsuccessful. Please check email and password',
                  'danger')
    return render_template('login.html', title='Login', form=form)


@app.route("/logout")
def logout():
    logout_user()
    return redirect(url_for('login'))


def save_picture(form_picture):
    random_hex = secrets.token_hex(8)
    _, f_ext = os.path.splitext(form_picture.filename)
    picture_fn = random_hex + f_ext
    picture_path = os.path.join(app.root_path,
                                'static/profile_pics',
                                picture_fn)
    output_size = (125, 125)
    i = Image.open(form_picture)
    i.thumbnail(output_size)
    i.save(picture_path)
    return picture_fn


@app.route("/account", methods=['GET', 'POST'])
@login_required
def account():
    form = UpdateAccountForm()
    if form.validate_on_submit():
        prev_currency = current_user.currency
        if form.picture.data:
            picture_file = save_picture(form.picture.data)
            current_user.image_file = picture_file
        current_user.username = form.username.data
        current_user.email = form.email.data
        current_user.currency = form.currency.data
        db.session.commit()
        if current_user.currency != prev_currency:
            # Request recalculate balance & P&L
            add_task('calc_trade_PL', current_user.id)
            add_task('calc_portfolio_history', current_user.id)
        flash('Your account has been updated!', 'success')
        return redirect(url_for('account'))
    elif request.method == 'GET':
        form.username.data = current_user.username
        form.email.data = current_user.email
        form.currency.data = current_user.currency
    image_file = url_for('static',
                         filename='profile_pics/' + current_user.image_file)
    return render_template('account.html', title='Account',
                           image_file=image_file, form=form)


def send_reset_email(user):
    token = user.get_reset_token()
    msg = Message('Password Reset Request',
                  sender='noreply@demo.com',
                  recipients=[user.email])
    msg.body = f'''Para resetear su contraseña, visite el sigiuiente link:
{url_for('reset_token', token=token, _external=True)}

Si usted no realizó esta petición de reseteo de contraseña, simplemente ignore este email y no se realizarán cambios sobre su cuenta.
'''
    mail.send(msg)


@app.route("/reset_password", methods=['GET', 'POST'])
def reset_request():
    if current_user.is_authenticated:
        return redirect(url_for('home'))
    form = RequestResetForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        send_reset_email(user)
        flash('Se ha enviado un email con instrucciones a la cuenta indicada.',
              'info')
        return redirect(url_for('login'))
    return render_template('reset_request.html',
                           title='Reset Password',
                           form=form)


@app.route("/reset_password/<token>", methods=['GET', 'POST'])
def reset_token(token):
    if current_user.is_authenticated:
        return redirect(url_for('home'))
    user = User.verify_reset_token(token)
    if user is None:
        flash('El token no es válido o ha expirado', 'warning')
        return redirect(url_for('reset_request'))
    form = ResetPasswordForm()
    if form.validate_on_submit():
        hashed_password = bcrypt.generate_password_hash(form.password.data)\
                                .decode('utf-8')
        user.password = hashed_password
        db.session.commit()
        flash('Contraseña actualizada. Ya puedes iniciar sesión de nuevo',
              'success')
        return redirect(url_for('login'))
    return render_template('reset_token.html',
                           title='Reset Password',
                           form=form)


@app.route("/start")
def start():
    return render_template('no_operations.html', title='Start')


@app.route("/")
@app.route("/home")
@app.route("/dashboard")
@login_required
def dashboard():
    # If user has no operations in DB, jump to start
    if not check_if_ops(current_user):
        return redirect(url_for('start'))
    # If user has operations, proceed
    curr = current_user.currency
    # Generate information for Portfolio Summary
    pf_delta = calc_portfolio_deltas(current_user, logger)
    # Generate information for Coin-Table
    today = get_last_price_dt()
    balances = calc_balance(current_user, curr, logger)
    coin_dashbord = {}
    for bal in balances:
        if bal.value == 0:
            continue
        coin = bal.coin
        if coin not in Params.CURRENCIES:
            curr_delta = PriceDelta.query.filter_by(coin=coin,
                                                    currency=curr).first()
            btc_delta = PriceDelta.query.filter_by(coin=coin,
                                                   currency='BTC').first()
            price = db.session.query(Price.price)\
                .filter_by(coin=coin, currency=curr, date=today)\
                .first()
            if price:
                price = price[0]
            else:
                price_btc = '-'
            price_btc = db.session.query(Price.price)\
                .filter_by(coin=coin,
                           currency='BTC',
                           date=today).first()
            if price_btc:
                price_btc = price_btc[0]
            else:
                price_btc = '-'
            if curr_delta and btc_delta:
                price = num_2_str(price, curr)
                price_btc = num_2_str(price_btc, 'BTC')
                value = num_2_str(bal.value, curr, 0)
                value_btc = num_2_str(bal.value_btc, 'BTC', 4)
                perc = num_2_perc(bal.perc, 2)
                curr_1d = num_2_perc(curr_delta.delta_1d, 2)
                curr_7d = num_2_perc(curr_delta.delta_7d, 2)
                curr_1m = num_2_perc(curr_delta.delta_1m, 2)
                curr_3m = num_2_perc(curr_delta.delta_3m, 2)
                curr_6m = num_2_perc(curr_delta.delta_6m, 2)
                curr_1y = num_2_perc(curr_delta.delta_1y, 2)
                curr_2y = num_2_perc(curr_delta.delta_2y, 2)
                btc_1d = num_2_perc(btc_delta.delta_1d, 2)
                btc_7d = num_2_perc(btc_delta.delta_7d, 2)
                btc_1m = num_2_perc(btc_delta.delta_1m, 2)
                btc_3m = num_2_perc(btc_delta.delta_3m, 2)
                btc_6m = num_2_perc(btc_delta.delta_6m, 2)
                btc_1y = num_2_perc(btc_delta.delta_1y, 2)
                btc_2y = num_2_perc(btc_delta.delta_2y, 2)
                coin_dashbord.update({coin: {"Value": value,
                                             "ValueBTC": value_btc,
                                             "Price": price,
                                             "PriceBTC": price_btc,
                                             "Perc": perc,
                                             "curr_1d": curr_1d,
                                             "curr_7d": curr_7d,
                                             "curr_1m": curr_1m,
                                             "curr_3m": curr_3m,
                                             "curr_6m": curr_6m,
                                             "curr_1y": curr_1y,
                                             "curr_2y": curr_2y,
                                             "btc_1d": btc_1d,
                                             "btc_7d": btc_7d,
                                             "btc_1m": btc_1m,
                                             "btc_3m": btc_3m,
                                             "btc_6m": btc_6m,
                                             "btc_1y": btc_1y,
                                             "btc_2y": btc_2y}})
    ts = get_price_timestamp()
    return render_template('dashboard.html', pf_delta=pf_delta,
                           coin_dashbord=coin_dashbord, timestamp=ts,
                           title='Dashboard')


@app.route("/balance/<string:date>")
@login_required
def balance(date):
    # If user has no operations in DB, jump to start
    if not check_if_ops(current_user):
        return redirect(url_for('start'))
    # If user has operations, proceed
    if date == 'Today':
        dt = get_last_price_dt()
    else:
        try:
            dt = datetime.datetime.strptime(date, "%Y-%m-%d")
        except Exception as e:
            dt = get_last_price_dt()
            flash("Por favor, seleccione un formato correcto de fecha: "
                  "'YYYY-MM-DD'", 'danger')
    curr = current_user.currency
    crypto_portfolio = Portfolio.query.filter_by(user_id=current_user.id,
                                                 date=dt).all()
    if not crypto_portfolio:
        flash("No se ha encontrado información sobre el portfolio para "
              "la fecha '{}'".format(date), 'danger')
        dt = get_last_price_dt()
        crypto_portfolio = Portfolio.query.filter_by(user_id=current_user.id,
                                                     date=dt).all()
    # Prepare list of coins & exchanges to be used later
    exchanges = []
    coins = []
    for pos in crypto_portfolio:
        if pos.coin not in coins:
            coins.append(pos.coin)
        if pos.exchange not in exchanges:
            exchanges.append(pos.exchange)
    exchanges = sorted(exchanges)
    coins = sorted(coins)
    # Loop to calculate Totals
    total_value = 0
    total_value_btc = 0
    for pos in crypto_portfolio:
        total_value += pos.value
        total_value_btc += pos.value_btc
    # Loop to calculate Exchange summary
    exch_value = 0
    exch_value_btc = 0
    exch_summary = {}
    for exch in exchanges:
        for pos in crypto_portfolio:
            if exch == pos.exchange:
                exch_value += pos.value
                exch_value_btc += pos.value_btc
        perc = "{:.2%}".format(exch_value / total_value)
        exch_value = num_2_str(exch_value, curr, 0)
        exch_value_btc = num_2_str(exch_value_btc, 'BTC', 4)
        exch_summary.update({exch: {'value': exch_value,
                                    'value_btc': exch_value_btc,
                                    'perc': perc}})
        exch_value = 0
        exch_value_btc = 0
    # Loop to calculate Coin summary
    coin_amount = 0
    coin_value = 0
    coin_value_btc = 0
    coin_summary = {}
    for coin in coins:
        for pos in crypto_portfolio:
            if coin == pos.coin:
                coin_amount += pos.amount
                coin_value += pos.value
                coin_value_btc += pos.value_btc
        perc = "{:.2%}".format(coin_value / total_value)
        coin_value = num_2_str(coin_value, curr, 0)
        coin_value_btc = num_2_str(coin_value_btc, 'BTC', 4)
        coin_amount = "{:20,.8f}".format(coin_amount)
        coin_summary.update({coin: {'amount': coin_amount,
                                    'value': coin_value,
                                    'value_btc': coin_value_btc,
                                    'perc': perc}})
        coin_amount = 0
        coin_value = 0
        coin_value_btc = 0
    # Format Totals
    total_value = num_2_str(total_value, curr, 0)
    total_value_btc = num_2_str(total_value_btc, 'BTC', 4)
    ts = get_price_timestamp()
    # Render website
    return render_template('balance.html', date=dt,
                           exch_summary=exch_summary,
                           coin_summary=coin_summary,
                           total_value=total_value,
                           total_value_btc=total_value_btc,
                           timestamp=ts,
                           title='Balance Histórico')


@app.route("/balance/exchange")
@login_required
def balance_exch():
    # If user has no operations in DB, jump to start
    if not check_if_ops(current_user):
        return redirect(url_for('start'))
    # If user has operations, proceed
    curr = current_user.currency
    # Obtener balance, eliminar fiats y agrupar por exchange
    last_price_dt = get_last_price_dt()
    crypto_portfolio = Portfolio.query.filter_by(user_id=current_user.id,
                                                 date=last_price_dt).all()
    split_portf = split_portf_by_exch(crypto_portfolio)
    split_portf = OrderedDict(sorted(split_portf.items()))
    exch_summary = calc_exch_summary(split_portf, curr)
    # Calc total values & format results
    total_value = 0
    total_value_btc = 0
    for exch in exch_summary:
        total_value += exch_summary[exch]['value']
        total_value_btc += exch_summary[exch]['value_btc']
        exch_summary[exch]['value'] = num_2_str(exch_summary[exch]['value'],
                                                curr, 0)
        exch_summary[exch]['value_btc'] = num_2_str(exch_summary[exch]['value_btc'], 'BTC', 4)
    total_value = num_2_str(total_value, curr, 0)
    total_value_btc = num_2_str(total_value_btc, 'BTC', 4)
    ts = get_price_timestamp()
    # Render page
    return render_template('balance_exch.html', split_portf=split_portf,
                           curr=curr, exch_summary=exch_summary,
                           total_value=total_value,
                           total_value_btc=total_value_btc,
                           timestamp=ts,
                           title='Balance por Exchange')


@app.route("/pnl_total")
@login_required
def pnl_total():
    # If user has no operations in DB, jump to start
    if not check_if_ops(current_user):
        return redirect(url_for('start'))
    # If user has operations, proceed and get balance for last avail.date
    curr = current_user.currency
    today = get_last_price_dt()
    balances = calc_balance(current_user, curr, logger)
    # Calc total portfolio value
    tot_value = 0
    for coin in balances:
        tot_value += coin.value
    tot_value = round(tot_value, 2)
    # Get total cost value
    tot_cost = calc_tot_pf_cost(current_user, logger, today)
    tot_PL = round(tot_value - tot_cost, 2)
    tot_value = num_2_str(tot_value, curr, 0)
    tot_cost = num_2_str(tot_cost, curr, 0)
    tot_PL = num_2_str(tot_PL, curr, 0)
    ts = get_price_timestamp()
    return render_template('pnl_total.html', balances=balances, title='Balance',
                           tot_value=tot_value, tot_cost=tot_cost,
                           tot_PL=tot_PL, curr=curr, timestamp=ts, today=today)


@app.route("/pnl_history")
@login_required
def pnl_history():
    # If user has no operations in DB, jump to start
    if not check_if_ops(current_user):
        return redirect(url_for('start'))
    # If user has operations, proceed
    portf_evol = calc_pnl_history(current_user, logger)
    ts = get_price_timestamp()
    return render_template('pnl_history.html', portf_evol=portf_evol,
                           timestamp=ts,
                           title='Histórico de Pérdidas y Ganancias')


@app.route("/pnl_trades")
@login_required
def pnl_trades():
    # If user has no operations in DB, jump to start
    if not check_if_ops(current_user):
        return redirect(url_for('start'))
    # If user has operations, proceed
    curr = current_user.currency
    trades = TradePL.query.filter_by(user_id=current_user.id).all()
    ts = get_price_timestamp()
    return render_template('pnl_trades.html', trades=trades, curr=curr,
                           timestamp=ts,
                           title='Pérdidas & Ganancias por Operación')


@app.route("/operations")
@login_required
def operations():
    ops = Operation.query.filter_by(user_id=current_user.id).all()
    return render_template('operations.html', ops=ops,
                           title='Histórico de operaciones')


@app.route("/operations/delete", methods=['POST'])
@login_required
def delete_all_operations():
    Operation.query.filter_by(user_id=current_user.id).delete()
    Portfolio.query.filter_by(user_id=current_user.id).delete()
    TradePL.query.filter_by(user_id=current_user.id).delete()
    db.session.commit()
    flash('Operaciones eliminados correctamente', 'success')
    return redirect(url_for('operations'))


@app.route("/operations/<int:op_id>/delete", methods=['POST'])
@login_required
def delete_operation(op_id):
    # Delete operation
    op = Operation.query.get_or_404(op_id)
    if op.user != current_user:
        abort(403)
    db.session.delete(op)
    db.session.commit()
    # Request recalculate balance & P&L
    add_task('calc_trade_PL', current_user.id)
    add_task('calc_portfolio_history', current_user.id)
    # Exit
    flash('Operación eliminada correctamente', 'success')
    return redirect(url_for('operations'))


@app.route("/operations/<int:op_id>/edit", methods=['GET', 'POST'])
@login_required
def edit_operation(op_id):
    # Edit operation
    op = Operation.query.get_or_404(op_id)
    if op.user != current_user:
        abort(403)
    form = EditOperationForm()
    if form.validate_on_submit():
        # If nothing was changed, don't update
        if (form.date.data == op.date and
            form.exchange.data == op.exchange and
            form.type.data == op.type and
            form.buy_amount.data == op.buy_amount and
            form.buy_coin.data == op.buy_coin and
            form.sell_amount.data == op.sell_amount and
            form.sell_coin.data == op.sell_coin and
            form.fee_amount.data == op.fee_amount and
            form.fee_coin.data == op.fee_coin and
                form.comment.data == op.comment):
            flash('Registro no actualizado: no se ha modificado ningún valor',
                  'warning')
            return redirect(url_for('edit_operation', op_id=op.id))
        # If anything was changed, then update
        else:
            op.date = form.date.data
            op.exchange = form.exchange.data
            op.type = form.type.data
            op.buy_amount = form.buy_amount.data
            if ((op.buy_amount is None) and
                    (op.type not in ['Expense', 'Withdrawal'])):
                op.buy_amount = 0
            op.buy_coin = form.buy_coin.data
            op.sell_amount = form.sell_amount.data
            if ((op.sell_amount is None) and
                    (op.type not in ['Airdrop', 'Deposit', 'Fork', 'Income'])):
                op.sell_amount = 0
            op.sell_coin = form.sell_coin.data
            op.fee_amount = form.fee_amount.data
            if ((op.fee_amount is None) and
                    (op.type not in ['Airdrop', 'Deposit', 'Fork', 'Income'])):
                op.fee_amount = 0
            op.fee_coin = form.fee_coin.data
            op.comment = form.comment.data
            db.session.commit()
            # Request recalculate balance & P&L
            add_task('calc_trade_PL', current_user.id)
            add_task('calc_portfolio_history', current_user.id)
            # Exit
            flash('Operación correctamente actualizada', 'success')
        return redirect(url_for('operations'))
    elif request.method == 'GET':
        form.date.data = op.date
        form.exchange.data = op.exchange
        form.type.data = op.type
        form.buy_amount.data = op.buy_amount
        form.buy_coin.data = op.buy_coin
        form.sell_amount.data = op.sell_amount
        form.sell_coin.data = op.sell_coin
        form.fee_amount.data = op.fee_amount
        form.fee_coin.data = op.fee_coin
        form.comment.data = op.comment
    return render_template('operation_edit.html', form=form,
                           title='Editar operación')


@app.route("/operations/new", methods=['GET', 'POST'])
@login_required
def new_operation():
    form = EditOperationForm()
    if form.validate_on_submit():
        # Insert new operation in DB
        op = Operation(date=form.date.data,
                       exchange=form.exchange.data,
                       type=form.type.data,
                       buy_amount=form.buy_amount.data,
                       buy_coin=form.buy_coin.data,
                       sell_amount=form.sell_amount.data,
                       sell_coin=form.sell_coin.data,
                       fee_amount=form.fee_amount.data,
                       fee_coin=form.fee_coin.data,
                       comment=form.comment.data,
                       user_id=current_user.id)
        db.session.add(op)
        db.session.commit()
        # Request recalculate balance & P&L
        add_task('calc_trade_PL', current_user.id)
        add_task('calc_portfolio_history', current_user.id)
        # Exit
        flash('Nueva operación guardada correctamente', 'success')
        return redirect(url_for('operations'))
    return render_template('operation_edit.html', form=form,
                           title='Nueva operación')


@app.route("/operations/import", methods=['GET', 'POST'])
@login_required
def import_operations():
    form = ImportOperationsForm()
    file_errors = []
    cons_errors = []
    if form.validate_on_submit():
        # Save CSV in HD with random name
        random_hex = secrets.token_hex(8)
        _, f_ext = os.path.splitext(form.file.data.filename)
        random_fn = random_hex + f_ext
        file_path = os.path.join(app.root_path, 'static/imports', random_fn)
        form.file.data.save(file_path)
        # Process file
        file_errors = import_operations_file(current_user, file_path, logger)
        if len(file_errors) == 0:
            # Calc Portolio History to eval consistency (delete first JIC)
            tmp_user_id = current_user.id + 1000000
            db.session.query(Portfolio).filter_by(user_id=tmp_user_id).delete()
            db.session.commit()
            cons_errors = calc_portfolio_history(tmp_user_id,
                                                 current_user.currency,
                                                 logger)
            if len(cons_errors) == 0:
                # # Delete current records in 'real_user'
                # db.session.query(Operation)\
                #           .filter_by(user_id=current_user.id).delete()
                # # Move records in 'tmp_user' to 'real_user'
                # tmp_records = Operation.query.filter_by(user_id=tmp_user_id)
                # for record in tmp_records:
                #     record.user_id = current_user.id
                # db.session.commit()
                # flash("Fichero importado correctamente.", 'success')
                return redirect(url_for('confirm_import_operations'))
            else:
                flash("Formato de fichero correcto, pero se han identificado "
                      "algunos problemas en la consistencia de la información."
                      " Por favor, revíselos detenidamente para decidir si "
                      "quiere proceder con la carga.", 'warning')
        else:
            flash("Fichero no cargado al haberse encontrado los errores "
                  "indicados a continuación. Por favor, corríjalos y vuelva "
                  "a intentarlo.", 'danger')
    return render_template('operations_import.html', form=form,
                           file_errors=file_errors, cons_errors=cons_errors,
                           title='Actualizar operaciones')


@app.route("/operations/import/confirm", methods=['GET'])
@login_required
def confirm_import_operations():
    tmp_user_id = current_user.id + 1000000
    # Move 'operations' in 'tmp_user' to 'real_user'
    db.session.query(Operation).filter_by(user_id=current_user.id).delete()
    tmp_records = Operation.query.filter_by(user_id=tmp_user_id)
    for record in tmp_records:
        record.user_id = current_user.id
    db.session.commit()
    # Move 'balance' in 'tmp_user' to 'real_user'
    db.session.query(Portfolio).filter_by(user_id=current_user.id).delete()
    tmp_records = Portfolio.query.filter_by(user_id=tmp_user_id)
    for record in tmp_records:
        record.user_id = current_user.id
    db.session.commit()
    # Calc Trade P&L
    add_task('calc_trade_PL', current_user.id)
    # Message & Exit
    flash("Fichero importado. Por favor, revise el balance de su cuenta para "
          "asegurar que las operaciones cargadas son correctas", 'success')
    return redirect(url_for('operations'))


@app.route("/operations/import/cancel", methods=['GET'])
@login_required
def cancel_import_operations():
    tmp_user_id = current_user.id + 1000000
    # Delete records of 'tmp_user'
    db.session.query(Operation).filter_by(user_id=tmp_user_id).delete()
    db.session.query(Portfolio).filter_by(user_id=tmp_user_id).delete()
    # Commit and exit
    db.session.commit()
    flash("Importación del fichero cancelada. No se han efectuado cambios",
          'warning')
    return redirect(url_for('operations'))


@app.route("/operations/consistency", methods=['GET'])
@login_required
def check_consistency():
    # Duplicate operations for temp user
    tmp_user_id = current_user.id + 2000000
    db.session.query(Operation).filter_by(user_id=tmp_user_id).delete()
    ops = Operation.query.filter_by(user_id=current_user.id)
    for op in ops:
        duplicate_op = Operation(date=op.date,
                                 exchange=op.exchange,
                                 type=op.type,
                                 buy_amount=op.buy_amount,
                                 buy_coin=op.buy_coin,
                                 sell_amount=op.sell_amount,
                                 sell_coin=op.sell_coin,
                                 fee_amount=op.fee_amount,
                                 fee_coin=op.fee_coin,
                                 comment=op.comment,
                                 user_id=tmp_user_id)
        db.session.add(duplicate_op)
    db.session.commit()
    # Calc Portolio History to eval consistency (delete first JIC)
    db.session.query(Portfolio).filter_by(user_id=tmp_user_id).delete()
    db.session.commit()
    cons_errors = calc_portfolio_history(tmp_user_id,
                                         current_user.currency,
                                         logger)
    # Delete temperal rows
    db.session.query(Operation).filter_by(user_id=tmp_user_id).delete()
    db.session.query(Portfolio).filter_by(user_id=tmp_user_id).delete()
    db.session.commit()
    if len(cons_errors) == 0:
        flash("No se han encontrado problemas de consistencia en las "
              "operaciones.", 'success')
        return redirect(url_for('operations'))
    else:
        flash("Inconsistencias encontradas en las operaciones. Por favor, "
              "revise el listado de abajo y efectúe los cambios que considere "
              "necesarios en sus movimientos.", 'warning')
        return render_template('operations_check.html',
                               cons_errors=cons_errors,
                               title='Revisión de consistencia')


@app.route("/test")
def test():
    return render_template('no_operations.html', title='Test')
