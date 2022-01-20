import sys

from loguru import logger

logger.add(sys.stderr, colorize=True, backtrace=True, format="{time} {level} {message}")
