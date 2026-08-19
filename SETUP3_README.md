# Setup 3 — Support → Pullback → Reversal → Breakout

This is a new strategy and does not replace PRE-BOP or Setup 2.

## Strategy idea

1. Start with fundamentally strong NSE companies.
2. Require market capitalization of at least ₹10,000 Cr.
3. Find a completed 20–45 trading-session consolidation/base.
4. Identify a structural support zone inside/under the base.
5. Prefer stocks that pull back toward support rather than chasing current price.
6. Require reversal evidence before calling the setup a buy.
7. Keep breakout confirmation separate from reversal confirmation.
8. Calculate a planned entry, structural stop, T1 and T2.
9. Prefer roughly 20–30% technical opportunity and R:R ≥ 2.
10. Rank only stocks that pass the fundamental gate.

## Signal states

- 🔵 WAIT FOR PULLBACK — technically interesting, but price has not reached the desired pullback area.
- 🟡 PULLBACK WATCH — price is near/in the support zone; wait for reversal confirmation.
- 🟢 REVERSAL BUY — support has held and reversal confirmation is present.
- 🚀 BREAKOUT BUY — breakout has occurred with volume confirmation.
- ⚪ FUNDAMENTAL FILTER — fails the fundamental requirement.
- ⚪ AVOID — setup quality is insufficient.

## Important

A support touch is NOT automatically a buy.

The scanner intentionally separates:
- Support
- Planned Buy
- Stop
- Breakout
- T1
- T2

This is designed to avoid buying a falling stock merely because it reaches a prior low.

## Permanent fundamentals

The app reads `fundamentals.csv` from the repository. You do not upload it through Streamlit every session.

Required columns:

`Symbol,MarketCapCr,ROE,ROCE,SalesGrowth3Y,ProfitGrowth3Y,DebtEquity,CFOPositive`

The included CSV is a blank template. Populate it with verified data.

## Backtesting

This version is a scanner, not proof of profitability. Before risking real money, add and validate:
- historical signal detection
- entry after reversal confirmation
- stop-first vs target-first outcome
- 10%, 20%, 30% target hit rates
- average days to each target
- win rate
- expectancy
- maximum drawdown
- slippage and brokerage assumptions

No return is guaranteed.
