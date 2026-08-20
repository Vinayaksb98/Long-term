# Setup 3 — Yahoo Finance FINAL FIX

This version fixes the **Loading NSE universe...** problem.

### What changed
- The stock universe is bundled locally in `nifty500_symbols.csv`.
- The app does NOT download the NSE universe at startup.
- Yahoo Finance is used only for fundamentals and price history.
- There is no `fundamentals.csv` and no fundamentals upload.
- Default scan is 100 stocks; you can increase it to 500 in the sidebar.

### GitHub upload
Delete the old Setup 3 files first, then upload exactly:
- `app.py`
- `requirements.txt`
- `nifty500_symbols.csv`
- `README.md`

All four files must be in the repository root.

### Streamlit Cloud
- Branch: `main`
- Main file: `app.py`

### Important
The bundled universe is a convenience snapshot. NSE says NIFTY 500 represents the top 500 companies by full market capitalisation; constituents can change over time. Yahoo Finance data can also be delayed, incomplete or rate-limited.

The strategy is a research scanner:
Fundamentals → 20–45 session base → Support → Pullback → Reversal → Breakout.

The 20–30% target is an opportunity estimate, not a guaranteed return.
