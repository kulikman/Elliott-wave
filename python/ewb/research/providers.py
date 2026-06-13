"""Market-data providers — crypto via Binance (keyless), stocks via Tiingo.

Single place that knows how to fetch OHLC and the latest price from a real
data source, replacing yfinance as the primary provider. yfinance stays as a
fallback in ``data.download_ohlc`` when a provider returns nothing (or the
Tiingo key is missing).

Why this exists: yfinance has no native 4h/1w interval and is rate-limited.
Binance serves crypto 1h/4h/1d/1w natively without a key; Tiingo serves stock
daily/weekly + IEX intraday with a free API key (TIINGO_API_KEY in .env).
"""
from __future__ import annotations

import json
import logging
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

# ─── Tiingo daily request counter ───────────────────────────────────────────
# Tiingo Free: 500 req/day. Track calls so we can warn before hitting the cap.
# Keyed by UTC date string; not persisted across process restarts (good enough
# for a daily cron — one process per scan run).
_TIINGO_DAILY_COUNT: dict[str, int] = {}
_TIINGO_DAILY_WARN = 400    # warn at this count (20% headroom)
_TIINGO_DAILY_CAP  = 490    # hard-stop before the 429 cascade (10 headroom)


def _tiingo_request_ok() -> bool:
    """Return True and increment the daily counter; return False when at cap."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    _TIINGO_DAILY_COUNT[today] = _TIINGO_DAILY_COUNT.get(today, 0) + 1
    n = _TIINGO_DAILY_COUNT[today]
    if n == _TIINGO_DAILY_WARN:
        log.warning("Tiingo: %d requests today — approaching 500/day limit", n)
    if n > _TIINGO_DAILY_CAP:
        log.error("Tiingo: daily cap reached (%d) — skipping request to avoid 429", n)
        return False
    return True


# ─── Tiingo scan-path OHLC cache ─────────────────────────────────────────────
# Avoids re-fetching Tiingo on every hourly cron pass. Cache TTLs match bar
# duration so data is never staler than 1 bar. Saves ~90% of Tiingo requests.
_SCAN_CACHE_ROOT = Path(__file__).resolve().parents[3] / "python" / "data" / "ohlc_cache" / "tiingo_scan"
_SCAN_CACHE_TTL: dict[str, timedelta] = {
    "1h": timedelta(hours=1),
    "4h": timedelta(hours=4),
    "1d": timedelta(hours=24),
    "1w": timedelta(days=7),
}

def _scan_cache_path(ticker: str, interval: str) -> Path:
    safe = ticker.replace("/", "-").replace(".", "-").replace(" ", "-")
    return _SCAN_CACHE_ROOT / f"{safe}_{interval}.parquet"

def _scan_cache_load(ticker: str, interval: str) -> pd.DataFrame | None:
    path = _scan_cache_path(ticker, interval)
    if not path.exists():
        return None
    ttl = _SCAN_CACHE_TTL.get(interval, timedelta(hours=1))
    age = datetime.now(timezone.utc) - datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
    if age > ttl:
        return None
    try:
        return pd.read_parquet(path)
    except Exception:
        return None

def _scan_cache_save(ticker: str, interval: str, df: pd.DataFrame) -> None:
    path = _scan_cache_path(ticker, interval)
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        df.to_parquet(path)
    except Exception:
        pass

def _load_env() -> None:
    """Make TIINGO_API_KEY available regardless of entry point.

    Uses python-dotenv when present; otherwise parses .env directly so the key
    still loads even if the optional dependency is missing.
    """
    env_path = Path(__file__).resolve().parents[3] / ".env"
    try:
        from dotenv import load_dotenv
        load_dotenv(env_path, override=False)
        return
    except Exception:
        pass
    try:
        if not env_path.exists():
            return
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            key, val = key.strip(), val.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = val
    except Exception:  # pragma: no cover - defensive
        pass


_load_env()

log = logging.getLogger(__name__)

CRYPTO_SUFFIXES = ("-USD", "-USDT", "-BTC", "-ETH", "-PERP")

BINANCE_INTERVAL_MS = {
    "15m": 15 * 60 * 1000,
    "30m": 30 * 60 * 1000,
    "1h": 60 * 60 * 1000,
    "4h": 4 * 60 * 60 * 1000,
    "1d": 24 * 60 * 60 * 1000,
    "1w": 7 * 24 * 60 * 60 * 1000,
}

# Tiingo: daily endpoint covers daily/weekly; IEX endpoint covers intraday.
_TIINGO_RESAMPLE = {"15m": "15min", "30m": "30min", "1h": "1hour", "1d": "daily", "1w": "weekly"}


def is_crypto(ticker: str) -> bool:
    t = str(ticker).upper()
    return any(t.endswith(s) for s in CRYPTO_SUFFIXES)


def period_to_days(period: str | None, default: int = 1825) -> int:
    if not period:
        return default
    try:
        unit, amount = period[-1], int(period[:-1])
    except (ValueError, IndexError):
        return default
    if unit == "d":
        return amount
    if unit == "y":
        return amount * 365
    return default


def _period_start(period: str | None) -> str:
    days = period_to_days(period)
    return (datetime.now(timezone.utc) - timedelta(days=days)).date().isoformat()


def _finalize(df: pd.DataFrame | None, min_rows: int) -> pd.DataFrame | None:
    """Sort, de-dupe, drop NaN, enforce UTC index and a minimum row count."""
    if df is None or df.empty:
        return None
    out = df.copy()
    idx = pd.to_datetime(out.index, utc=True)
    out = out.set_axis(idx).sort_index()
    out = out[~out.index.duplicated(keep="last")]
    base = ["open", "high", "low", "close"]
    if not set(base).issubset(out.columns):
        return None
    out = out.dropna(subset=base)
    return out if len(out) > min_rows else None


def _resample(df: pd.DataFrame | None, rule: str) -> pd.DataFrame | None:
    if df is None or df.empty:
        return None
    agg = {"open": "first", "high": "max", "low": "min", "close": "last"}
    if "volume" in df.columns:
        agg["volume"] = "sum"
    return df[[c for c in agg if c in df.columns]].resample(rule).agg(agg).dropna()


# ─── Binance (crypto, keyless) ────────────────────────────────────────────────

def binance_symbol(ticker: str) -> str:
    base = str(ticker).upper().replace("-USD", "").replace("-USDT", "")
    return f"{base}USDT"


def download_binance_ohlc(ticker: str, interval: str, period: str | None = None,
                          min_rows: int = 50, limit: int = 1000,
                          max_requests: int = 80) -> pd.DataFrame | None:
    """Paginated Binance klines → OHLCV. Native 1h/4h/1d/1w, no API key."""
    symbol = binance_symbol(ticker)
    interval_ms = BINANCE_INTERVAL_MS.get(interval)
    if interval_ms is None:
        return None
    end_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
    days = period_to_days(period, default=int(interval_ms / 86_400_000 * limit) or 365)
    start_ms = int((datetime.now(timezone.utc) - timedelta(days=days)).timestamp() * 1000)

    payload: list = []
    requests = 0
    while start_ms < end_ms and requests < max_requests:
        params = urllib.parse.urlencode({
            "symbol": symbol, "interval": interval, "limit": limit,
            "startTime": start_ms, "endTime": end_ms,
        })
        try:
            with urllib.request.urlopen(
                f"https://api.binance.com/api/v3/klines?{params}", timeout=20
            ) as resp:
                chunk = json.load(resp)
        except Exception as exc:
            log.warning("binance %s %s failed: %s", symbol, interval, exc)
            break
        if not isinstance(chunk, list) or not chunk:
            break
        payload.extend(chunk)
        requests += 1
        nxt = int(chunk[-1][0]) + interval_ms
        if nxt <= start_ms or len(chunk) < limit:
            break
        start_ms = nxt
        time.sleep(0.05)

    if not payload:
        return None
    rows = [{
        "ts": pd.to_datetime(int(r[0]), unit="ms", utc=True),
        "open": float(r[1]), "high": float(r[2]), "low": float(r[3]),
        "close": float(r[4]), "volume": float(r[5]),
    } for r in payload]
    df = pd.DataFrame(rows).set_index("ts")
    return _finalize(df, min_rows)


def binance_last_price(ticker: str) -> float | None:
    try:
        url = f"https://api.binance.com/api/v3/ticker/price?symbol={binance_symbol(ticker)}"
        with urllib.request.urlopen(url, timeout=10) as resp:
            data = json.load(resp)
        px = float(data["price"])
        return px if px > 0 else None
    except Exception:
        return None


# ─── Tiingo (stocks, API key) ─────────────────────────────────────────────────

def tiingo_token() -> str | None:
    return os.environ.get("TIINGO_API_KEY") or os.environ.get("TIINGO_TOKEN")


def _tiingo_get(url: str, params: dict, token: str, retries: int = 3) -> list | None:
    if not _tiingo_request_ok():
        return None
    query = urllib.parse.urlencode({**params, "token": token})
    req = urllib.request.Request(
        f"{url}?{query}",
        headers={"Content-Type": "application/json", "Authorization": f"Token {token}"},
    )
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=45) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
            return payload if isinstance(payload, list) else None
        except urllib.error.HTTPError as exc:
            if exc.code in {401, 403, 404}:
                log.warning("tiingo HTTP %s for %s", exc.code, url)
                return None
            if exc.code == 429:
                wait = 30 * (2 ** attempt)   # 30s, 60s, 120s
                log.warning("tiingo HTTP 429 (rate limit) — sleeping %ds before retry %d/%d",
                            wait, attempt + 1, retries)
                time.sleep(wait)
                if not _tiingo_request_ok():   # count the retry too
                    return None
                continue
            if attempt + 1 >= retries:
                return None
            time.sleep(2 ** attempt)
        except Exception:
            if attempt + 1 >= retries:
                return None
            time.sleep(2 ** attempt)
    return None


def _tiingo_rows_to_df(rows: list | None) -> pd.DataFrame | None:
    if not rows:
        return None
    df = pd.DataFrame(rows)
    if df.empty or "date" not in df.columns:
        return None
    for src, dst in (("adjOpen", "open"), ("adjHigh", "high"),
                     ("adjLow", "low"), ("adjClose", "close"), ("adjVolume", "volume")):
        if src in df.columns:
            df[dst] = df[src]
    base = ["open", "high", "low", "close"]
    if not set(base).issubset(df.columns):
        return None
    cols = base + (["volume"] if "volume" in df.columns else [])
    out = df[["date", *cols]].copy()
    out["date"] = pd.to_datetime(out["date"], utc=True)
    return out.set_index("date")


def download_tiingo_ohlc(ticker: str, interval: str, period: str | None = None,
                         min_rows: int = 50) -> pd.DataFrame | None:
    # Return cached data if fresh enough (avoids Tiingo rate-limit burn).
    cached = _scan_cache_load(ticker, interval)
    if cached is not None and len(cached) >= min_rows:
        return cached

    token = tiingo_token()
    if not token:
        return None
    symbol = str(ticker).lower()
    start = _period_start(period)
    # 4h has no native Tiingo frequency → pull 1h and resample.
    fetch_interval = "1h" if interval == "4h" else interval
    resample = _TIINGO_RESAMPLE.get(fetch_interval)
    if resample is None:
        return None
    if fetch_interval in ("1d", "1w"):
        url = f"https://api.tiingo.com/tiingo/daily/{urllib.parse.quote(symbol)}/prices"
    else:
        url = f"https://api.tiingo.com/iex/{urllib.parse.quote(symbol)}/prices"
    rows = _tiingo_get(url, {"startDate": start, "resampleFreq": resample}, token)
    df = _tiingo_rows_to_df(rows)
    if df is not None and interval == "4h":
        df = _resample(_finalize(df, 0), "4h")
    result = _finalize(df, min_rows)
    if result is not None:
        _scan_cache_save(ticker, interval, result)
    return result


def tiingo_last_price(ticker: str) -> float | None:
    token = tiingo_token()
    if not token:
        return None
    try:
        url = f"https://api.tiingo.com/iex/{urllib.parse.quote(str(ticker).lower())}"
        rows = _tiingo_get(url, {}, token)
        if rows:
            px = rows[0].get("last") or rows[0].get("tngoLast") or rows[0].get("prevClose")
            return float(px) if px else None
    except Exception:
        return None
    return None


# ─── unified latest-price ─────────────────────────────────────────────────────

def last_price(ticker: str) -> float | None:
    """Latest price: Binance for crypto, Tiingo for stocks. Returns None on miss
    (callers fall back to yfinance)."""
    if is_crypto(ticker):
        return binance_last_price(ticker)
    return tiingo_last_price(ticker)
