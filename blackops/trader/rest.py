

class Reporter:

    def log_report(self, pnl):

        # pnl = self.calculate_pnl()

        logger.info(
            f"""
        pnl: {pnl}

        target buy: {self.theo_buy}
        best seller: {self.best_seller}

        target sell: {self.theo_sell}
        best buyer: {self.best_buyer}
        """
        )


    async def periodic_report(self, period: float):
        while True:
            self.log_report()
            await asyncio.sleep(period)


from enum import Enum


class OrderType(Enum):
    buy = 'buy'
    sell = 'sell'


@dataclass
class Order:
    ...


@dataclass
class LimitOrder(Order):
    type: OrderType
    qty: Decimal



@dataclass
class Report:
    ...


@dataclass
class PeriodicReport(Report):
    pnl: Decimal

    target_buy: Decimal
    best_seller: Decimal 
    
    target_sell:Decimal
    best_buyer: Decimal 

