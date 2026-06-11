"""Continuous OHLC ingestion — keep the backtest cache fresh.

The live auto-trader already fetches fresh OHLC for signals each scan; this job
keeps a PERSISTENT cache current so the validation backtests (wave3, core) run
on up-to-date data and thin setups mature as bars accumulate.

Scopes (--scope):
  crypto : Binance 1d/4h/1h/1w for all watchlist crypto (keyless, hourly).
  stocks : Tiingo 1d for all watchlist stocks, but ONLY inside the US market
           windows — right after the open (09:30-09:40 ET) and just before the
           close (15:55-16:00 ET), once per window (a 30-min cooldown stops the
           5-min scheduler from re-refreshing and blowing the Tiingo rate limit).
           Window is checked in America/New_York time, so it tracks US DST
           automatically (open = 16:30 MSK in summer, 17:30 in winter).
  all    : both, ignoring the window gate (manual/one-off runs).

Cache layout matches what the backtests read:
  python/data/ohlc_cache/tiingo/{TICKER}_1d_5y.parquet   (date col + OHLC)
  python/data/ohlc_cache/binance/{TICKER}_{label}.parquet

Schedule: com.ewb.dataingest (crypto, hourly) + com.ewb.stockingest (stocks,
every 5 min, self-gated to the market windows).
"""
from __future__ import annotations

import argparse
import sys
import time
from datetime import datetime, time as dtime
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "python"))

from ewb.research.data import download_ohlc                # noqa: E402
from ewb.research.providers import download_binance_ohlc, is_crypto  # noqa: E402

WATCHLIST = ROOT / "configs" / "watchlist.yaml"
CACHE = ROOT / "python" / "data" / "ohlc_cache"
STOCK_MARKER = ROOT / "brain-output" / ".last_stock_ingest"
STOCK_THROTTLE_S = 0.8          # pace Tiingo requests under the rate limit
CRYPTO_INTERVALS = [("1d", "1500d"), ("4h", "900d"), ("1h", "730d"), ("1w", "3650d")]
ET = ZoneInfo("America/New_York")
COOLDOWN_S = 30 * 60            # one stock refresh per market window


def _write_cache(provider: str, ticker: str, label: str, period: str, df: pd.DataFrame) -> None:
    safe = ticker.replace("/", "-").replace(".", "-").replace(" ", "-")
    path = CACHE / provider / f"{safe}_{label}_{period}.parquet"
    path.parent.mkdir(parents=True, exist_ok=True)
    out = df.copy()
    out.index.name = "date"
    out.reset_index().to_parquet(path, index=False)


def _watchlist() -> dict:
    return yaml.safe_load(WATCHLIST.read_text(encoding="utf-8")) or {}


def _is_trading_day(now_et: datetime) -> bool:
    if now_et.weekday() >= 5:
        return False
    try:
        import pandas_market_calendars as mcal
        sched = mcal.get_calendar("NYSE").schedule(
            start_date=now_et.date(), end_date=now_et.date())
        return not sched.empty
    except Exception:
        return True   # fallback: weekday is enough


def _in_stock_window(now_et: datetime) -> bool:
    """Right after the open or a couple minutes before the close."""
    if not _is_trading_day(now_et):
        return False
    t = now_et.time()
    open_win = dtime(9, 30) <= t <= dtime(9, 40)        # just after 09:30 ET open
    close_win = dtime(15, 55) <= t <= dtime(16, 0)      # last minutes before 16:00 ET close
    return open_win or close_win


def _cooldown_active() -> bool:
    if not STOCK_MARKER.exists():
        return False
    age = time.time() - STOCK_MARKER.stat().st_mtime
    return age < COOLDOWN_S


def _ingest_stocks(stocks: list[str]) -> tuple[int, int]:
    ok = fail = 0
    for tk in stocks:
        df = download_ohlc(tk, "1d", "5y", min_rows=50)
        if df is not None and not df.empty:
            _write_cache("tiingo", tk, "1d", "5y", df)
            ok += 1
        else:
            fail += 1
        time.sleep(STOCK_THROTTLE_S)
    STOCK_MARKER.parent.mkdir(parents=True, exist_ok=True)
    STOCK_MARKER.touch()
    return ok, fail


def _ingest_crypto(crypto: list[str]) -> tuple[int, int]:
    ok = fail = 0
    for tk in crypto:
        for label, period in CRYPTO_INTERVALS:
            df = download_binance_ohlc(tk, label, period, min_rows=50)
            if df is not None and not df.empty:
                _write_cache("binance", tk, label, period, df)
                ok += 1
            else:
                fail += 1
    return ok, fail


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--scope", choices=["crypto", "stocks", "all"], default="all")
    args = ap.parse_args()

    wl = _watchlist()
    stocks = [str(t).upper() for t in wl.get("stocks", []) if not is_crypto(t)]
    crypto = [str(t).upper() for t in wl.get("crypto", [])]
    now = pd.Timestamp.now("UTC").isoformat()
    now_et = datetime.now(ET)

    if args.scope in ("crypto", "all"):
        c_ok, c_fail = _ingest_crypto(crypto)
        print(f"{now}  data_ingest[crypto]: {len(crypto)} tickers ok={c_ok} fail={c_fail}")

    if args.scope in ("stocks", "all"):
        gated = args.scope == "stocks"   # only the scheduled stock job is window-gated
        if gated and not _in_stock_window(now_et):
            print(f"{now}  data_ingest[stocks]: outside market window ({now_et:%H:%M} ET) — skip")
        elif gated and _cooldown_active():
            print(f"{now}  data_ingest[stocks]: already refreshed this window — skip")
        else:
            s_ok, s_fail = _ingest_stocks(stocks)
            print(f"{now}  data_ingest[stocks]: {len(stocks)} tickers ok={s_ok} fail={s_fail} "
                  f"({now_et:%H:%M} ET)")


if __name__ == "__main__":
    main()
