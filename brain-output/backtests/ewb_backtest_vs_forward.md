# EWB Backtest vs Forward

This report is the bot reality check. If forward metrics diverge from history, do not scale capital.

## Portfolio Comparison

| Scope | Trades | Win | Exp | PF | DD |
|---|---|---|---|---|---|
| Historical baseline | 1518 | 59.9% | 1.44% | 1.83 | -96.2% |
| Forward closed | 1 | 100.0% | 26.54% | n/a | 0.0% |

## Forward Closed By Setup

| TF | Pattern | Side | Trades | Win | Exp | PF | DD |
|---|---|---|---|---|---|---|---|
| 1d | flat | long | 1 | 100.0% | 26.54% | n/a | 0.0% |

## Decision Rule

- Fewer than 30 closed forward trades: observe only.
- Forward expectancy below 0 or profit factor below 1.1: do not automate live size.
- Big gap between historical and forward winrate: audit alerts, fill prices, repaint and HTF context.
