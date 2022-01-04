from dataclasses import dataclass, field
from typing import AsyncGenerator

import blackops.streams.bn as bn_streams
import blackops.streams.btcturk as btc_streams
from blackops.exchanges.factory import ExchangeType


@dataclass
class StreamFactory:
    STREAMS: dict = field(default_factory=dict)

    def create_stream_if_not_exists(
        self, ex_type: ExchangeType, symbol: str, pub_channel: str
    ) -> AsyncGenerator:
        key = (ex_type, symbol)
        if key in self.STREAMS:

            return self.STREAMS[key]

        if ex_type == ExchangeType.BINANCE:
            stream = bn_streams.create_book_stream(symbol, pub_channel)
        elif ex_type == ExchangeType.BTCTURK:
            stream = btc_streams.create_book_stream(symbol, pub_channel)

        self.STREAMS[key] = stream

        return stream


stream_factory = StreamFactory()
