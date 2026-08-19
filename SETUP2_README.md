# SETUP 2 — Quality Base → Reversal → Breakout

This is a **separate strategy** from the existing PRE-BOP `app.py`.

## GitHub files

Keep your existing files unchanged:

```text
README.md
app.py
requirements.txt
```

Add these new files:

```text
setup2.py
SETUP2_README.md
fundamentals_template.csv
```

Run the second strategy with:

```bash
streamlit run setup2.py
```

## Strategy objective

Find NSE stocks that combine:

1. Fundamental quality
2. Market cap target of at least ₹10,000 Cr
3. A 20–45 trading-session consolidation/base
4. Support holding and volatility/volume compression
5. A developing reversal / higher-low structure
6. Proximity to breakout resistance
7. At least 20% technical opportunity where possible
8. Risk/reward of at least 1.5, preferably 2+

### Important

A 20–30% figure is **potential upside**, not a promised return.

The app is a research scanner and must be backtested before real-money use.

## 100-point score

### Fundamental — 25

- Market cap ≥ ₹10,000 Cr — 4
- ROCE ≥15% — 4
- ROE ≥15% — 3
- 3Y sales growth >0% — 3
- 3Y profit growth >0% — 4
- Debt/Equity ≤1 — 3
- Positive operating cash flow — 2
- 3Y profit growth ≥10% — 2

### Base — 20

- 20–45 session consolidation — 4
- Base range ≤20% — 3
- Volume drying/compression — 3
- Volatility compression — 3
- Resistance tested at least twice — 3
- Support holding — 2
- Price near upper base boundary — 2

### Reversal — 20

- Higher-low / no fresh lower low — 4
- EMA9 > EMA21 — 3
- RSI >50 and rising — 3
- MACD histogram improving — 2
- Up-volume participation — 2
- ADX improving — 2
- Price ≥ EMA20 — 2
- Price ≥ EMA50 — 2

### Breakout readiness — 20

- 0–5% below breakout resistance — 4
- Resistance exists — 3
- Bollinger compression — 3
- EMA20 turning upward — 3
- ADX ≥18 — 2
- RVOL ≥0.9 — 2
- MACD histogram >0 — 1
- RSI 50–68 — 2

### Opportunity / risk — 15

- Potential ≥20% — 5
- Potential ≥25% — 3
- R:R ≥1.5 — 4
- R:R ≥2.0 — 3

## Signal interpretation

- **75–100:** A+ candidate
- **65–74:** Buy candidate / strong watch
- **55–64:** Watch
- **Below 55:** Avoid

The app also applies stricter technical/fundamental gates before displaying an A+ signal.

## Fundamentals CSV

The current free market-price feed does not reliably provide all the fundamental fields required for this strategy.

Therefore the app **does not invent fundamental values**.

Upload a verified CSV with exactly these columns:

```text
Symbol,MarketCapCr,ROE,ROCE,SalesGrowth3Y,ProfitGrowth3Y,DebtEquity,CFOPositive
```

Example:

```text
ABC,25000,18.5,21.2,12.4,16.8,0.35,True
```

Use your verified source for the values. Do not treat the example values as real stock data.

## Entry concept

### Early entry

Consider only when:
- strong fundamental score
- strong base
- reversal confirmed
- close to resistance
- R:R ≥1.5

### Conservative entry

Wait for:
- resistance breakout
- meaningful volume confirmation
- preferably a successful retest

## Targets

The app shows:

- **T1:** nearest structural resistance
- **T2:** larger structural/base-height objective
- **T3:** ATR-based extension reference

The displayed "Potential %" uses the larger technically justified objective.

## Stop

The app uses a conservative structural/ATR stop based on:
- recent 10-session swing low
- 1.25 ATR

This is a heuristic and should be validated in backtesting.

## Time to target

This version does **not** claim that a 20–30% move will happen in a fixed number of days.

The next development should backtest:

- probability of +10%
- probability of +20%
- probability of +30%
- median trading days to each target
- stop-first rate
- maximum drawdown
- maximum favorable excursion
- average/median return
- 1, 3 and 6 month outcomes

A reasonable research horizon for the 20–30% objective is up to 6 months, but the actual holding period should come from historical testing.

## Important separation from PRE-BOP

Do **not** replace your old `app.py`.

This strategy is intentionally a separate file:

```text
app.py       = PRE-BOP strategy
setup2.py    = Quality Base/Reversal strategy
```

Both can live in the same GitHub repository.
