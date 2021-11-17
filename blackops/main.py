def start_real():
    stg = create_strategy(symbols.UMA, symbols.TRY, symbols.USDT)
    asyncio.run(stg.run())


if __name__ == "__main__":
    start_real()
