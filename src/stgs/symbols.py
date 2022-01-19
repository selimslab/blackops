SUPPORTED_BRIDDGES = set(["USDT"])


BTCTURK_TRY_BASES = set(
    [
        "ADA",
        "ANKR",
        "ATIC",
        "ATOM",
        "AVAX",
        "AXS",
        "BAT",
        "BTC",
        "CHZ",
        "COMP",
        "DASH",
        "DOGE",
        "DOT",
        "ENJ",
        "EOS",
        "ETH",
        "FIL",
        "FTM",
        "GRT",
        "LINK",
        "LRC",
        "LTC",
        "MANA",
        "MKR",
        "NEO",
        "OMG",
        "SHIB",
        "SNX",
        "SOL",
        "STX",
        "TRX",
        "UMA",
        "UNI",
        "USDC",
        "USDT",
        "XLM",
        "XRP",
        "XTZ",
        "GALA",
        "MATIC",
        "AAVE",
        "AMP",
        "SAND",
        "NU",
        "AUDIO",
        "POLY",
        "FET",
        "SPELL",
        "STORJ",
    ]
)


ALL_SYMBOLS = BTCTURK_TRY_BASES.union(set(["TRY"]))


# f = [line.split("/")[0] for line in s.split() if "/" in line]
# print(set(f).difference(BTCTURK_TRY_BASES))
