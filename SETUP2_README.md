# Setup 2 — Quality Base → Reversal → Breakout

This app is separate from the original PRE-BOP strategy.

## Permanent fundamentals database

The app automatically reads `fundamentals.csv` from the same GitHub repository.
You do **not** need to upload the CSV through Streamlit every time.

Required columns:

`Symbol, MarketCapCr, ROE, ROCE, SalesGrowth3Y, ProfitGrowth3Y, DebtEquity, CFOPositive`

To refresh fundamentals, replace/update `fundamentals.csv` in GitHub and reboot/redeploy the Streamlit app.

The included `fundamentals.csv` contains headers only. Do not treat placeholder/example data as real financial data.

## Scoring

- Fundamental: 25 points
- Base: 20 points
- Reversal: 20 points
- Breakout readiness: 20 points
- Opportunity / R:R: 15 points

The scanner is a research tool, not a guarantee of returns.
