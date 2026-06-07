# EWB Backtest vs Forward

This report is the bot reality check. If forward metrics diverge from history, do not scale capital.

## Portfolio Comparison

| Scope | Trades | Win | Exp | PF | DD |
|---|---|---|---|---|---|
| Historical baseline | 1518 | 59.9% | 1.44% | 1.83 | -96.2% |
| Forward closed | 0 | n/a | n/a | n/a | n/a |

## Forward Closed By Setup

No closed forward trades yet.

## Decision Rule

- Fewer than 30 closed forward trades: observe only.
- Forward expectancy below 0 or profit factor below 1.1: do not automate live size.
- Big gap between historical and forward winrate: audit alerts, fill prices, repaint and HTF context.
