
# Setup 3 — Yahoo Fundamentals

## Purpose

A Streamlit research scanner for:

**Fundamentals → 20–45 session base → support → pullback → reversal → breakout**

The app automatically reads fundamental data from Yahoo Finance. You do **not** need to upload a fundamentals CSV every time.

## GitHub / Streamlit Cloud

Put these files directly in the repository root:

```text
app.py
requirements.txt
README.md
```

Streamlit Cloud settings:

```text
Branch: main
Main file path: app.py
```

## What is filtered

The scanner uses Yahoo Finance data for available fields such as:

- Market capitalization
- ROE
- Revenue growth
- Earnings growth
- Debt/Equity
- Operating cash flow
- Free cash flow
- Profit margin
- ROCE when Yahoo supplies it

A stock must pass the ₹10,000 Cr market-cap gate and reach the fundamental strength threshold before technical scoring.

## Technical logic

The technical layer looks for:

1. 20–45 session consolidation/base
2. Structural support
3. Pullback toward support
4. Reversal evidence
5. Breakout evidence
6. Stop below structure
7. 20–30% opportunity estimate
8. Risk/reward calculation

The scanner distinguishes between:

- WAIT
- PULLBACK WATCH
- REVERSAL BUY
- BREAKOUT BUY

## Important

Yahoo Finance is a third-party source and some fields can be missing or stale.

Missing data is **not** treated as strong data.

The scanner is a research/idea-generation tool, not a guarantee of returns.

Before using real money, backtest the exact rules over multiple market regimes and include brokerage, taxes, slippage and gaps.
