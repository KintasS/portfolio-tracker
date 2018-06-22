import logging


def set_logger(file_name, logger_name):
    """Sets logging configuration.
    """
    # Set-up logger in both file
    logger = logging.getLogger(logger_name)
    logger.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(asctime)s:%(levelname)s:%(message)s')
    file_handler = logging.FileHandler(file_name)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    # Set-up looger in console
    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)
    # Return logger to allow it to be called from outside
    return logger


def error_notificator(logger_name, function, error):
    """Handles application erros to notify its creator.
    """
    logger_name.error("Not handled error in '{}': {}".format(function, error))
    pass
