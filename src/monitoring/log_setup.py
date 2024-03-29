import logging
import os
import sys

from loguru import logger  # type:ignore

LOG_LEVEL = logging.getLevelName(os.environ.get("LOG_LEVEL", "DEBUG"))
JSON_LOGS = True if os.environ.get("JSON_LOGS", "0") == "1" else False


class InterceptHandler(logging.Handler):
    def emit(self, record):
        # Get corresponding Loguru level if it exists
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        # Find caller from where originated the logged message
        frame, depth = logging.currentframe(), 2
        while frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1

        logger.opt(depth=depth, exception=record.exc_info).log(
            level, record.getMessage()
        )


def setup_logging():
    # intercept everything at the root logger
    # logging.root.handlers = [InterceptHandler()]

    logging.getLogger("uvicorn").handlers = [InterceptHandler()]
    logging.getLogger("uvicorn").propagate = True

    # remove every other logger's handlers
    # and propagate to root logger
    # for name in logging.root.manager.loggerDict.keys():
    #     logging.getLogger(name).handlers = []
    #     logging.getLogger(name).propagate = True

    # print(logging.root.manager.loggerDict.keys())
    # logging.getLogger('sentry_sdk').propagate = False
    # logging.getLogger('sentry_sdk.errors').propagate = False

    # configure loguru
    # logger.add(sys.stdout, colorize=True, format="{time} {level} {message}")

    logger.configure(
        handlers=[{"sink": sys.stdout, "serialize": JSON_LOGS}],
    )
    return logger
