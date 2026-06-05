# Crypto Integration Plan

Goal: add crypto as a separate Elliott Wave Brain asset class without mixing it
with the stock probability model.

## Contract

- `asset_class = stocks | crypto | unsupported`.
- Stocks use `probability_calibration_v0.json`.
- Crypto must use `probability_calibration_crypto_v0.json`.
- If crypto calibration is missing, Python/Pine must return `WAIT / research`
  instead of stock-calibrated `BUY / SELL`.
- One user-facing Pine indicator is preferred, but it must show the active
  model badge: `stocks-v0` or `crypto-v0`.

## MVP Sequence

1. Add crypto universe, cost model, and stock/crypto separated historical runs.
2. Run crypto historical grid on `15m, 30m, 1h, 4h, 1d, 1w`.
3. Build `probability_calibration_crypto_v0.json` and `.md`.
4. Add Python crypto daily report and crypto Pine parity checklist.
5. Add `Market mode = Stocks / Crypto / Auto` to the main Pine indicator.
6. Enable crypto alerts only when crypto calibration exists and the active
   chart symbol is crypto.

## Data Notes

Crypto grid research now uses Binance spot klines for exchange-grade 24/7 bars.
TradingView parity still needs manual venue checks, because Binance spot,
perpetual futures, and other exchanges can have different bar boundaries,
spreads, and liquidity.

Migrated or poor-history tickers should stay out of production defaults. The
current research artifact still includes legacy `MATIC-USD`, so Polygon
migration history must be treated as a data-quality finding before crypto
defaults are promoted.

## Risk Notes

- Spot and perpetual futures need separate calibration.
- Funding, leverage and liquidation risk are out of scope for the first crypto
  MVP.
- Same-bar TP/SL ambiguity stays conservative: SL is checked before TP.
