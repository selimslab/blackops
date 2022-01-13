from dataclasses import dataclass, field
from typing import AsyncGenerator

import src.pubsub.log_pub as log_pub
import src.streams.bn as bn_streams
import src.streams.btcturk as btc_streams
from src.exchanges.factory import ExchangeType, NetworkType
from src.monitoring import logger


@dataclass
class StreamFactory:
    STREAMS: dict = field(default_factory=dict)

    def create_stream_if_not_exists(
        self, ex_type: ExchangeType, network: NetworkType, symbol: str
    ) -> AsyncGenerator:
        key = "_".join((ex_type.value, network.value, symbol))

        if key in self.STREAMS:
            return self.STREAMS[key]

        if ex_type == ExchangeType.BINANCE:
            stream = bn_streams.create_book_stream(symbol)
        elif ex_type == ExchangeType.BTCTURK:
            stream = btc_streams.create_book_stream(symbol)

        self.STREAMS[key] = stream

        return stream


stream_factory = StreamFactory()
