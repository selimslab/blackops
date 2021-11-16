
import asyncio
import collections
import json
import operator
import pprint
import time
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Callable, Iterable, List, Optional

from aiostream import async_, stream

from blackops.clients.binance.stream import ws_generator_binance
from blackops.clients.btcturk.main import Client, btcturk_client
from blackops.clients.btcturk.stream import ws_generator_bt
from blackops.domain.models import Asset, AssetPair, Exchange, LeaderFollowerStrategy
from blackops.logger import logger
from blackops.util import decimal_division, decimal_mid




@dataclass
class Binance(Exchange):
    name:str = "binance"

    @staticmethod
    def get_mid(order_book: dict)->Optional[Decimal]:
        """ get mid price from binance orderbook  """
        if not order_book:
            return 

        try:
            order_book = order_book.get("data", {})

            best_ask_price = order_book.get("a", 0)
            best_bid_price = order_book.get("b", 0)

            return decimal_mid(best_ask_price, best_bid_price)

        except Exception as e:
            logger.info(e)
                    


    async def consume_orderbook_stream(self, book_generator):
        async for book in book_generator:
            if book:
                ...