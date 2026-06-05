# TradingView Pine Validation

Generated: `2026-06-05`

## Scope

Validate the pushed Pine changes on the live TradingView chart:

- `pine/ewb_monowaves_mtf.pine`
- `pine/ewb_probability_overlay_v0.pine`

The key safety check is that crypto charts must not show stock-calibrated
BUY/SELL action.

## Local Checks

Passed:

- `python3 -m pytest python/tests -q`
- Static guard check for `Market mode`, `CRYPTO RESEARCH ONLY`, and removed
  `stockOnlyMode`.

Result: `34 passed`.

## Browser Observation

Current in-app browser URL: `https://www.tradingview.com/chart/`

Observed chart:

- Symbol: `BTCUSDT`
- Visible indicator: `EWB Mono`
- Visible table still shows stock-style trade output on BTC:
  - `Trade`: `SHORT`
  - `Фигура`: `Flat fade`
  - `P≈`: `61.0%`
  - `Entry / TP`: visible numeric trade plan
  - `SL / invalid`: visible numeric level

Pine Editor was opened in split-view and the current repository code was
visible there, including the new `Market` row. However, browser automation did
not successfully add/update the chart instance: the left chart continued to
show the old saved `EWB Mono` output.

## Finding

Status: `High`

The TradingView chart appears to be running an older saved version of
`Elliott Wave Brain — Monowaves MTF`, not the current repository version.

Why it matters:

- On BTC/crypto, the current repository code should show `WAIT` with
  `CRYPTO RESEARCH ONLY`.
- The visible chart still makes BTC look like a stock-calibrated SHORT setup.
- This can mislead Anton into treating a research-only crypto pattern as a
  tradeable sell signal.

Minimal fix:

1. Open TradingView Pine Editor.
2. Replace the script with the current contents of `pine/ewb_monowaves_mtf.pine`.
3. Save/update the indicator.
4. Add it back to the BTCUSDT chart.
5. Set `Market mode = Crypto`.
6. Confirm:
   - `Action now = WAIT`
   - `Reason = CRYPTO RESEARCH ONLY`
   - `Market = Crypto / crypto-v0 research`
   - BUY/SELL alerts do not fire on crypto

## Stock Check After Update

After the Pine update, validate one stock chart, for example `AAPL` or `MSFT`:

- `Market mode = Stocks`
- `Action now` may be `BUY`, `SELL`, or `WAIT` depending on freshness,
  TP/SL, late-entry, RR, probability, sample size, and HTF filters.
- `Market` row should show `Stocks / stocks-v0`.

## Result

Current validation result: `blocked until TradingView Pine script is updated`.

## Manual Update Package

Primary script for Anton's working indicator:

- `pine/ewb_monowaves_mtf.pine`
- Indicator title: `Elliott Wave Brain — Monowaves MTF`
- Short title: `EWB Mono`
- Expected code checks:
  - contains `Market mode`
  - contains `CRYPTO RESEARCH ONLY`
  - table has `Market` and `Calib / TF` rows

Research-only overlay:

- `pine/ewb_probability_overlay_v0.pine`
- Indicator title: `EWB — Probability Overlay v0`
- Short title: `EWBProbv0`
- Keep actions/alerts disabled unless intentionally doing research parity.

Manual validation after updating `EWB Mono`:

1. Open `BTCUSDT` on TradingView.
2. Add/update `Elliott Wave Brain — Monowaves MTF`.
3. Open indicator settings and set `Market mode = Crypto`.
4. Expected:
   - `Action now = WAIT`
   - `Reason = CRYPTO RESEARCH ONLY`
   - `Market = Crypto / crypto-v0 research`
   - no BUY/SELL alert is available as a fresh crypto action
5. Open a stock, for example `AAPL` or `MSFT`.
6. Set `Market mode = Stocks`.
7. Expected:
   - `Market = Stocks / stocks-v0`
   - `Action now` may be `BUY`, `SELL`, or `WAIT` depending on active filters.
