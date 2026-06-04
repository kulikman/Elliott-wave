"""Symbol universe and market costs used by research scripts."""
from __future__ import annotations


SP500 = [
    "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA", "BRK-B", "JPM", "V",
    "UNH", "XOM", "JNJ", "WMT", "MA", "PG", "HD", "LLY", "ABBV", "KO",
    "PEP", "MRK", "CVX", "AVGO", "ORCL", "CSCO", "NFLX", "CRM", "AMD", "INTC",
]
ETFS = ["SPY", "QQQ", "IWM", "DIA", "GLD", "SLV", "USO", "TLT", "XLF", "XLE"]
CRYPTO = ["BTC-USD", "ETH-USD", "SOL-USD", "BNB-USD", "XRP-USD", "ADA-USD", "AVAX-USD", "DOGE-USD"]
FOREX = ["EURUSD=X", "GBPUSD=X", "USDJPY=X", "AUDUSD=X", "USDCAD=X"]
COMMODS = ["GC=F", "SI=F", "CL=F", "NG=F", "HG=F"]

SYMBOLS = SP500 + ETFS + CRYPTO + FOREX + COMMODS


def cost_for(ticker: str) -> float:
    """Round-trip model's per-side cost by asset class."""
    if ticker.endswith("-USD") or ticker.endswith("=X") or ticker.endswith("=F"):
        return 0.0013
    return 0.0008
