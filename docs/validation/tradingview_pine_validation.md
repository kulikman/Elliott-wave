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
- Static guard check that `Probability Overlay v0` no longer uses legacy
  `Market mode = Any`.

Result: `39 passed`.

## Browser Observation

Current in-app browser URL: `https://www.tradingview.com/chart/`

Follow-up observation after commit `78c297b` on `2026-06-05`:

- Current chart: `BTCUSDT`, `1D`, Binance.
- Visible indicator: `EWB Mono`.
- Live chart still shows an old stock-style crypto signal:
  - `Trade = SHORT`
  - `Фигура = Flat fade`
  - `P≈ = 61.0%`
  - `Entry / TP` and `SL / invalid` are visible numeric levels.
- Pine Editor contains the newer local code area around `Action now`, `Market`
  and `Calib / TF`, but clicking `Add to chart` did not replace the live chart
  instance.
- Opening the existing indicator settings confirmed the chart instance is old:
  - block name is still `Торговый слой Антона (RESEARCH: FLAT/DC FADE)`;
  - visible probabilities are still `Flat = 61`, `Double Correction = 89`;
  - the new `Mode = CRYPTO RESEARCH` panel contract is not active on the chart.

Result:

| Symbol | TF | Result | Reason |
|---|---|---|---|
| `BTCUSDT` | `1D` | FAIL / blocked | old saved `EWB Mono` still shows stock-style SHORT on crypto |
| `ETHUSDT` | n/a | not executed | same stale-script blocker; BTC already fails the safety gate |
| `SOLUSDT` | n/a | not executed | same stale-script blocker; BTC already fails the safety gate |
| `TRXUSDT` | n/a | not executed | same stale-script blocker; BTC already fails the safety gate |
| stock sanity check | n/a | not executed | must update TradingView Pine script first |

Conclusion: live TradingView parity is still blocked until the saved TradingView
script is manually updated from `pine/ewb_monowaves_mtf.pine` and re-added to the
chart. Local static checks pass, but the live chart is not running that code.

Follow-up observation on `2026-06-05`:

- Chart title reported by TradingView: `SPCE 4.29 ... BTC USD`.
- Pine Editor was open for `EWBProbv0`.
- The editor still displayed an older saved overlay version:
  - `Market mode` options still behaved like the legacy `Any` contract.
  - The panel code displayed only `syminfo.type` in the Market row instead of
    `syminfo.type + " / " + marketModel`.
- Browser automation could read the editor but did not reliably replace the
  Monaco editor contents, so the live TradingView script must be updated
  manually from the local file.

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
The latest browser attempt after commit `78c297b` still showed the old saved
indicator on BTCUSDT.

## Browser Attempt After Commit `6eb40fe`

Status: `partially mitigated / still blocked`.

What was verified:

- The local `pine/ewb_monowaves_mtf.pine` still contains the crypto guard:
  `Market mode`, `CRYPTO RESEARCH ONLY`, and the `decisionMode` table row.
- The TradingView Pine Editor accepted the current local script text and showed
  the new info-panel code around `Action now`, `Reason`, `Mode`, `Market`, and
  `Calib / TF`.
- The old live BTCUSDT chart instance still displayed the stale
  stock-calibrated panel before removal: `SHORT`, `Flat fade`, `P≈ 61.0%`,
  numeric `Entry / TP`, and numeric `SL / invalid`.
- The stale `EWB Mono` chart instance was removed from the BTCUSDT chart, so
  the live chart no longer shows that misleading crypto SHORT overlay.

Remaining blocker:

- Clicking `Add to chart` from the TradingView Pine Editor did not add the new
  `EWB Mono` instance back to the chart.
- The Pine Editor stayed on `Untitled script` with a loading spinner and no
  visible compile error in the browser text/logs.

Current live TradingView state:

- BTCUSDT chart has no stale `EWB Mono` indicator instance.
- The updated local repository Pine code is not yet confirmed as live on the
  chart.

Minimal next manual step:

1. In TradingView, reload the chart or reopen Pine Editor.
2. Paste the full contents of `pine/ewb_monowaves_mtf.pine`.
3. Save the script as a private TradingView script.
4. Add the saved script to the chart.
5. Confirm the BTCUSDT panel shows `WAIT / CRYPTO RESEARCH ONLY`.

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
- Expected code checks:
  - `Market mode` options are `Stocks`, `Crypto`, `Auto`, `Research any`
  - no legacy `Any` option remains
  - crypto charts show `crypto-v0 research`
  - crypto/unsupported charts hide stock `P / EV`, `Conf / N`, `Entry`,
    `Stop`, and `TP1-3` values in the overlay panel

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
