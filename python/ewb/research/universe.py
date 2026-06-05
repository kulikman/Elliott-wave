"""Symbol universe and market costs used by research scripts."""
from __future__ import annotations


SP500 = [
    "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA", "BRK-B", "JPM", "V",
    "UNH", "XOM", "JNJ", "WMT", "MA", "PG", "HD", "LLY", "ABBV", "KO",
    "PEP", "MRK", "CVX", "AVGO", "ORCL", "CSCO", "NFLX", "CRM", "AMD", "INTC",
]
ETFS = ["SPY", "QQQ", "IWM", "DIA", "GLD", "SLV", "USO", "TLT", "XLF", "XLE"]
CRYPTO = [
    "BTC-USD", "ETH-USD", "SOL-USD", "BNB-USD", "XRP-USD",
    "ADA-USD", "AVAX-USD", "DOGE-USD", "LINK-USD", "DOT-USD",
    "TRX-USD", "LTC-USD", "BCH-USD", "UNI-USD", "ATOM-USD",
    "ETC-USD", "FIL-USD", "APT-USD", "ARB-USD", "OP-USD",
]
FOREX = ["EURUSD=X", "GBPUSD=X", "USDJPY=X", "AUDUSD=X", "USDCAD=X"]
COMMODS = ["GC=F", "SI=F", "CL=F", "NG=F", "HG=F"]

SYMBOLS = SP500 + ETFS + CRYPTO + FOREX + COMMODS


def asset_class_for(ticker: str) -> str:
    """Return the research asset class for a yfinance-style ticker."""
    if ticker in CRYPTO or ticker.endswith("-USD"):
        return "crypto"
    if ticker.endswith("=X"):
        return "forex"
    if ticker.endswith("=F"):
        return "futures"
    if ticker in ETFS:
        return "etf"
    return "stock"


def cost_for_asset_class(asset_class: str) -> float:
    """Per-side cost model including fee/spread/slippage assumptions."""
    if asset_class == "crypto":
        return 0.0015
    if asset_class in {"forex", "futures"}:
        return 0.0013
    return 0.0008


def cost_for(ticker: str) -> float:
    """Per-side cost model by ticker asset class."""
    return cost_for_asset_class(asset_class_for(ticker))
