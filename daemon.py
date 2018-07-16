import time
import datetime
from portfolio_tracker import db
from portfolio_tracker.models import User, Task
from portfolio_tracker.utils import set_logger
from portfolio_tracker.info_fetcher import update_prices, update_coins
from portfolio_tracker.calculations import (calc_portfolio_history,
                                            calc_price_deltas, calc_trade_PL,
                                            add_task)

# Start logging
logger = set_logger('logs/Daemon.log', 'main')


def run_task(task):
    """Runs tasks in background.
    """
    # Change Status
    init_time = datetime.datetime.now()
    task.status = 'Running'
    task.start_time = init_time
    db.session.commit()
    # Run process
    ret = None
    if task.name == 'update_prices':
        # Set next update task for 1 hour latter
        next_run = datetime.datetime.now() + datetime.timedelta(hours=1)
        add_task('update_prices', None, next_run)
        # Run 'update_prices' task
        ret = update_prices(logger)
        # Add 'calc_price_deltas' task to queue
        add_task('calc_price_deltas')
        # Add 'calc_portfolio_history' task to queue for each user
        users = User.query
        for user in users:
            add_task('calc_portfolio_history', user.id)
    elif task.name == 'calc_price_deltas':
        calc_price_deltas(logger)
    elif task.name == 'update_coins':
        # Set next update task for 12 hours latter
        next_run = datetime.datetime.now() + datetime.timedelta(hours=12)
        add_task('update_coins', None, next_run)
        # Run 'update_coins' task
        update_coins(logger)
    elif task.name == 'calc_portfolio_history':
        user = User.query.filter_by(id=task.user_id).first()
        if user:
            calc_portfolio_history(user.id, user.currency, logger)
    elif task.name == 'calc_trade_PL':
        user = User.query.filter_by(id=task.user_id).first()
        if user:
            calc_trade_PL(user, logger)
    # Change task status and exit
    task.status = 'OK'
    task.finish_time = datetime.datetime.now()
    task.return_info = ret
    db.session.commit()
    return


# Clear pending and running tasks that did not finish
tasks = Task.query.filter_by(status='Pending')
for task in tasks:
    task.status = 'Cancelled'
tasks = Task.query.filter_by(status='Running')
for task in tasks:
    task.status = 'Cancelled'
db.session.commit()

# Add 'update_coins' and 'update_prices' and start
add_task('update_coins')
add_task('update_prices')
users = User.query
for user in users:
    add_task('calc_trade_PL', user.id)
iteration = 1
while True:
    print("\n\nStarting iteration '{}'".format(iteration))
    now = datetime.datetime.now()
    tasks = Task.query.filter_by(status='Pending')
    idle_daemon = True
    for task in tasks:
        if (task.not_before_time is None) or (now > task.not_before_time):
            logger.info("daemon: Starting task: '{}''".format(task))
            run_task(task)
            logger.info("daemon: Finished task: '{}''".format(task))
            idle_daemon = False
    if idle_daemon:
        print("No tasks to run. Going back to sleep...")
    iteration += 1
    time.sleep(1)
