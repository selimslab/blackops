from datetime import datetime
from src.stgs import StrategyType
from src.robots.sliding.main import SlidingWindowTrader


def create_sliding_stats_message(robot:SlidingWindowTrader) -> dict:
    stats = {
        "pair": robot.follower.pair.base.symbol +robot.follower.pair.quote.symbol,
        "current time": datetime.now(),
        "start time": robot.task_start_time,
        "orders delivered": {
            "buy": robot.follower.order_robot.buy_orders_delivered,
            "sell": robot.follower.order_robot.sell_orders_delivered,
        },
        "prices": {
            "binance": {
                "targets": asdict(robot.targets),
                "last update": robot.leader.theo_last_updated.time(),
                "books seen": robot.leader.books_seen,
            },
            "btcturk": {
                "bid": robot.follower.best_buyer,
                "ask": robot.follower.best_seller,
                "last update": robot.follower.bid_ask_last_updated.time(),
                "books seen": robot.follower.books_seen,
            }
        },
        "balances": {
            "step": robot.current_step,
            "start": {
                robot.follower.pair.base.symbol: {
                    "free": robot.follower.start_pair.base.free,
                    "locked": robot.follower.start_pair.base.locked,
                },
                robot.follower.pair.quote.symbol: {
                    "free": robot.follower.start_pair.quote.free,
                    "locked": robot.follower.start_pair.quote.locked,
                },
            },
            "current": {
                robot.follower.pair.base.symbol: {
                    "free": robot.follower.pair.base.free,
                    "locked": robot.follower.pair.base.locked,
                },
                robot.follower.pair.quote.symbol: {
                    "free": robot.follower.pair.quote.free,
                    "locked": robot.follower.pair.quote.locked,
                },
            },
        },
    }

    if robot.bridge_watcher:
        stats["bridge"] = {
            "exchange": robot.config.input.bridge_exchange,
            "quote": robot.bridge_watcher.quote,
            "last update": robot.bridge_watcher.last_updated,
        }

    stats["config"] = robot.config_dict

    return stats


STAT_MESSAGE_FUNCS = {
    StrategyType.SLIDING_WINDOW: create_sliding_stats_message
}

