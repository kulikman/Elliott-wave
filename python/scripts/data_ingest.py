"""Continuous OHLC ingestion — keep the backtest cache fresh (run hourly).

The live auto-trader already fetches fresh OHLC for signals each scan; this job
keeps a PERSISTENT cache current so the validation backtests (wave3, core) run
on up-to-date data and thin setups can mature as bars accumulate.

- Stocks: 1d OHLC via the provider layer (Tiingo), throttled to stay under the
  free-tier rate limit (~50 req/hr) — 30 tickers x 1 interval = ~30 req.
- Crypto: 1d/4h/1h/1w via Binance (keyless, unlimited).

Cache layout matches what the backtests read:
  python/data/ohlc_cache/tiingo/{TICKER}_1d_5y.parquet   (date col + OHLC)
  python/data/ohlc_cache/binance/{TICKER}_{label}.parquet

Run: python scripts/data_ingest.py        (one pass)
Scheduled hourly via launchd com.ewb.dataingest.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "python"))

from ewb.research.data import download_ohlc                # noqa: E402
from ewb.research.providers import download_binance_ohlc, is_crypto  # noqa: E402

WATCHLIST = ROOT / "configs" / "watchlist.yaml"
CACHE = ROOT / "python" / "data" / "ohlc_cache"
STOCK_THROTTLE_S = 0.8          # pace Tiingo requests under the rate limit
CRYPTO_INTERVALS = [("1d", "1500d"), ("4h", "900d"), ("1h", "730d"), ("1w", "3650d")]


def _write_cache(provider: str, ticker: str, label: str, period: str, df: pd.DataFrame) -> None:
    safe = ticker.replace("/", "-").replace(".", "-").replace(" ", "-")
    path = CACHE / provider / f"{safe}_{label}_{period}.parquet"
    path.parent.mkdir(parents=True, exist_ok=True)
    out = df.copy()
    out.index.name = "date"
    out.reset_index().to_parquet(path, index=False)


def _watchlist() -> dict:
    return yaml.safe_load(WATCHLIST.read_text(encoding="utf-8")) or {}


def main() -> None:
    wl = _watchlist()
    stocks = [str(t).upper() for t in wl.get("stocks", []) if not is_crypto(t)]
    crypto = [str(t).upper() for t in wl.get("crypto", [])]
    now = pd.Timestamp.now("UTC").isoformat()
    ok = fail = 0

    # Stocks: 1d cache (what wave3/core read). Throttled for Tiingo.
    for tk in stocks:
        df = download_ohlc(tk, "1d", "5y", min_rows=50)
        if df is not None and not df.empty:
            _write_cache("tiingo", tk, "1d", "5y", df)
            ok += 1
        else:
            fail += 1
        time.sleep(STOCK_THROTTLE_S)

    # Crypto: all intervals via Binance (no rate limit).
    for tk in crypto:
        for label, period in CRYPTO_INTERVALS:
            df = download_binance_ohlc(tk, label, period, min_rows=50)
            if df is not None and not df.empty:
                _write_cache("binance", tk, label, period, df)
                ok += 1
            else:
                fail += 1

    print(f"{now}  data_ingest: stocks={len(stocks)} crypto={len(crypto)} "
          f"cached_ok={ok} failed={fail}")


if __name__ == "__main__":
    main()
