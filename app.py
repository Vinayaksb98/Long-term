
import io
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import numpy as np
import pandas as pd
import streamlit as st
import yfinance as yf

st.set_page_config(
    page_title="Setup 3 — Support → Pullback → Reversal → Breakout",
    page_icon="🎯",
    layout="wide",
)

NIFTY500_URL = "https://www.niftyindices.com/IndexConstituent/ind_nifty500list.csv"
NSE_EQUITY_URL = "https://archives.nseindia.com/content/equities/EQUITY_L.csv"

st.title("🎯 SETUP 3 — SUPPORT → PULLBACK → REVERSAL → BREAKOUT")
st.caption(
    "Yahoo Finance powered research scanner for fundamentally strong NSE stocks "
    "forming 20–45 session bases, pulling back toward support, showing reversal evidence, "
    "and offering a realistic 20–30% technical opportunity."
)

with st.expander("How this version works"):
    st.markdown("""
    **No mandatory fundamentals CSV.** The app reads fundamental data from Yahoo Finance
    automatically. An optional `fundamentals.csv` can still be placed beside `app.py`
    if you want to override/add data manually.

    **Important:** Yahoo Finance is a third-party data source. Missing fundamentals are
    treated as missing, not as strong. A 20–30% target is an opportunity estimate, not a guarantee.
    """)

@st.cache_data(ttl=24*60*60, show_spinner=False)
def load_universe():
    # Prefer official NIFTY 500 constituent list. Fall back to NSE equity master.
    try:
        df = pd.read_csv(NIFTY500_URL)
        col = next((c for c in ["Symbol", "SYMBOL"] if c in df.columns), None)
        if col:
            syms = (
                df[col].astype(str).str.strip().str.upper()
                .replace("", np.nan).dropna().drop_duplicates().tolist()
            )
            return [s + ".NS" for s in syms], "NIFTY 500"
    except Exception:
        pass

    try:
        df = pd.read_csv(NSE_EQUITY_URL)
        col = "SYMBOL" if "SYMBOL" in df.columns else df.columns[0]
        syms = (
            df[col].astype(str).str.strip().str.upper()
            .replace("", np.nan).dropna().drop_duplicates().tolist()
        )
        return [s + ".NS" for s in syms], "NSE equity master"
    except Exception as e:
        raise RuntimeError(f"Could not load NSE/NIFTY universe: {e}")

@st.cache_data(ttl=12*60*60, show_spinner=False)
def yahoo_info(symbol):
    t = yf.Ticker(symbol)
    try:
        return t.get_info()
    except Exception:
        try:
            return t.info
        except Exception:
            return {}

def _history(symbol, period="6mo"):
    try:
        return yf.download(
            symbol, period=period, interval="1d",
            auto_adjust=False, progress=False, threads=False,
            timeout=20,
        )
    except Exception:
        return pd.DataFrame()

def clean_history(df):
    if df is None or df.empty:
        return pd.DataFrame()
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    cols = [c for c in ["Open","High","Low","Close","Volume"] if c in df.columns]
    if len(cols) < 4:
        return pd.DataFrame()
    out = df[cols].copy()
    for c in cols:
        out[c] = pd.to_numeric(out[c], errors="coerce")
    return out.dropna(subset=["Close"]).sort_index()

def pct(x):
    try:
        return float(x) * 100.0
    except Exception:
        return np.nan

def fundamentals_from_info(info):
    market_cap = info.get("marketCap")
    roe = info.get("returnOnEquity")
    revenue_growth = info.get("revenueGrowth")
    earnings_growth = info.get("earningsGrowth")
    debt_equity = info.get("debtToEquity")
    op_cf = info.get("operatingCashflow")
    free_cf = info.get("freeCashflow")
    profit_margin = info.get("profitMargins")
    roce = info.get("returnOnCapitalEmployed")

    # Yahoo sometimes reports debt/equity as a percentage.
    if debt_equity is not None:
        try:
            debt_equity = float(debt_equity) / 100.0
        except Exception:
            debt_equity = np.nan

    return {
        "market_cap": market_cap,
        "roe": pct(roe),
        "roce": pct(roce),
        "revenue_growth": pct(revenue_growth),
        "earnings_growth": pct(earnings_growth),
        "debt_equity": debt_equity,
        "operating_cf": op_cf,
        "free_cf": free_cf,
        "profit_margin": pct(profit_margin),
        "name": info.get("longName") or info.get("shortName") or "",
    }

def technical_setup(hist):
    h = clean_history(hist)
    if len(h) < 80:
        return None

    close = h["Close"]
    high = h["High"]
    low = h["Low"]
    vol = h["Volume"].replace(0, np.nan)

    current = float(close.iloc[-1])
    atr = float((high - low).rolling(14).mean().iloc[-1])
    if not np.isfinite(atr) or atr <= 0:
        atr = current * 0.02

    # 20–45 session base: compare recent range to its midpoint and volatility.
    base = h.tail(45)
    base_high = float(base["High"].max())
    base_low = float(base["Low"].min())
    base_range_pct = (base_high - base_low) / max(base_low, 1e-9) * 100

    # Find a tighter recent consolidation inside the last 20–45 sessions.
    best_window = 45
    best_range = base_range_pct
    for w in [20, 25, 30, 35, 40, 45]:
        x = h.tail(w)
        r = (x["High"].max() - x["Low"].min()) / max(x["Low"].min(), 1e-9) * 100
        if r < best_range:
            best_range, best_window = float(r), w

    recent = h.tail(best_window)
    support = float(recent["Low"].quantile(0.20))
    resistance = float(recent["High"].quantile(0.80))

    # Pullback distance toward support.
    dist_support = (current - support) / max(current, 1e-9) * 100
    near_support = 0 <= dist_support <= 8.0

    # Reversal evidence: recent bullish close, higher close vs 3 sessions ago,
    # and price reclaiming short-term average.
    sma5 = close.rolling(5).mean()
    sma20 = close.rolling(20).mean()
    bullish_today = close.iloc[-1] > close.iloc[-1] * 0 + close.iloc[-1]  # safe placeholder
    bullish_candle = close.iloc[-1] >= (high.iloc[-1] + low.iloc[-1]) / 2
    reclaim5 = current >= float(sma5.iloc[-1])
    improving = float(close.iloc[-1]) > float(close.iloc[-4])
    reversal = bool(bullish_candle and reclaim5 and improving)

    # Breakout evidence: close above recent resistance with volume expansion.
    avg_vol20 = float(vol.tail(20).mean()) if vol.notna().any() else np.nan
    vol_ratio = float(vol.iloc[-1] / avg_vol20) if np.isfinite(avg_vol20) and avg_vol20 > 0 else np.nan
    breakout = bool(current > resistance * 1.005 and (not np.isfinite(vol_ratio) or vol_ratio >= 1.2))

    # A practical pullback condition: price is not already too extended above support.
    pullback = near_support or (dist_support <= 12 and current < resistance)

    # Buy zone: support to a modest 3% band above support.
    buy_low = support
    buy_high = support * 1.03

    stop = support - max(0.8 * atr, support * 0.03)
    stop = max(stop, support * 0.90)

    # T2 aims for 20–30%, but cap by recent technical resistance if too low.
    t2 = current * 1.25
    if resistance > current:
        t2 = max(t2, resistance * 1.10)

    potential = (t2 / current - 1) * 100
    rr = (t2 - current) / max(current - stop, 1e-9)

    # Scoring
    base_score = 0
    base_score += 10 if best_window >= 20 else 0
    base_score += 10 if best_range <= 20 else 5 if best_range <= 30 else 0

    reversal_score = 20 if reversal else 10 if improving else 0
    pullback_score = 20 if near_support else 12 if pullback else 0
    breakout_score = 20 if breakout else 8 if current >= resistance * 0.97 else 0

    if breakout:
        signal = "🚀 BREAKOUT BUY"
    elif reversal and near_support:
        signal = "🟢 REVERSAL BUY"
    elif pullback:
        signal = "🟡 PULLBACK WATCH"
    else:
        signal = "🔵 WAIT"

    return {
        "current": current,
        "support": support,
        "resistance": resistance,
        "buy_low": buy_low,
        "buy_high": buy_high,
        "stop": stop,
        "t2": t2,
        "potential": potential,
        "rr": rr,
        "base_window": best_window,
        "base_range": best_range,
        "dist_support": dist_support,
        "vol_ratio": vol_ratio,
        "base_score": base_score,
        "pullback_score": pullback_score,
        "reversal_score": reversal_score,
        "breakout_score": breakout_score,
        "reversal": reversal,
        "breakout": breakout,
        "signal": signal,
    }

def fundamental_score(f):
    score = 0
    details = []

    mc = f.get("market_cap")
    if mc is not None and np.isfinite(float(mc)) and float(mc) >= 1e11:
        score += 25
        details.append("Market cap ≥ ₹10,000 Cr")
    else:
        return 0, False, ["Market cap below ₹10,000 Cr or missing"]

    roe = f.get("roe")
    if np.isfinite(roe) and roe >= 15:
        score += 15
        details.append("ROE ≥ 15%")
    elif np.isfinite(roe) and roe >= 10:
        score += 8
        details.append("ROE ≥ 10%")

    rg = f.get("revenue_growth")
    if np.isfinite(rg) and rg >= 8:
        score += 10
        details.append("Revenue growth ≥ 8%")
    elif np.isfinite(rg) and rg > 0:
        score += 5

    eg = f.get("earnings_growth")
    if np.isfinite(eg) and eg >= 10:
        score += 10
        details.append("Earnings growth ≥ 10%")
    elif np.isfinite(eg) and eg > 0:
        score += 5

    de = f.get("debt_equity")
    if np.isfinite(de) and de <= 1.0:
        score += 10
        details.append("Debt/Equity ≤ 1")
    elif np.isfinite(de) and de <= 1.5:
        score += 5

    ocf = f.get("operating_cf")
    if ocf is not None and np.isfinite(float(ocf)) and float(ocf) > 0:
        score += 10
        details.append("Positive operating cash flow")

    margin = f.get("profit_margin")
    if np.isfinite(margin) and margin > 0:
        score += 5

    roce = f.get("roce")
    if np.isfinite(roce) and roce >= 12:
        score += 15
        details.append("ROCE ≥ 12%")

    strong = score >= 60
    return score, strong, details

def scan_one(symbol):
    try:
        info = yahoo_info(symbol)
        f = fundamentals_from_info(info)
        fscore, strong, fdetails = fundamental_score(f)
        if not strong:
            return None

        hist = _history(symbol, "6mo")
        tech = technical_setup(hist)
        if not tech:
            return None

        total = fscore + tech["base_score"] + tech["pullback_score"] + tech["reversal_score"] + tech["breakout_score"]
        # Prefer realistic opportunity and risk/reward.
        if tech["potential"] < 20:
            return None

        return {
            "Stock": symbol.replace(".NS", ""),
            "Company": f["name"],
            "Current": tech["current"],
            "Buy Zone": f"₹{tech['buy_low']:.2f}–₹{tech['buy_high']:.2f}",
            "Stop": tech["stop"],
            "T1": tech["current"] * 1.10,
            "T2": tech["t2"],
            "Potential %": tech["potential"],
            "R:R": tech["rr"],
            "Fundamental": fscore,
            "Base": tech["base_score"],
            "Pullback": tech["pullback_score"],
            "Reversal": tech["reversal_score"],
            "Breakout": tech["breakout_score"],
            "Score": total,
            "Base Sessions": tech["base_window"],
            "Base Range %": tech["base_range"],
            "Support": tech["support"],
            "Resistance": tech["resistance"],
            "Vol Ratio": tech["vol_ratio"],
            "Signal": tech["signal"],
        }
    except Exception:
        return None

st.sidebar.header("Scanner controls")
max_symbols = st.sidebar.slider("Maximum stocks to scan", 50, 500, 200, 50)
workers = st.sidebar.slider("Parallel Yahoo requests", 2, 12, 6)
min_score = st.sidebar.slider("Minimum total score", 60, 140, 80, 5)

if st.button("🔄 Scan Setup 3 — Yahoo Fundamentals", type="primary"):
    with st.spinner("Loading NSE universe..."):
        symbols, universe_name = load_universe()

    symbols = symbols[:max_symbols]
    st.info(
        f"Universe: **{universe_name}** • Scanning **{len(symbols)}** symbols. "
        "Yahoo Finance requests can take a few minutes and may be rate-limited."
    )

    rows = []
    progress = st.progress(0)
    status = st.empty()

    with ThreadPoolExecutor(max_workers=workers) as ex:
        futures = {ex.submit(scan_one, s): s for s in symbols}
        done = 0
        for fut in as_completed(futures):
            done += 1
            status.write(f"Scanned {done}/{len(futures)}")
            progress.progress(done / len(futures))
            result = fut.result()
            if result:
                rows.append(result)

    progress.empty()
    status.empty()

    if not rows:
        st.warning(
            "No candidates passed all filters. Try scanning more symbols or lowering "
            "the minimum score. Yahoo may also temporarily rate-limit requests."
        )
    else:
        df = pd.DataFrame(rows)
        df = df[df["Score"] >= min_score].sort_values(
            ["Score", "Potential %", "R:R"], ascending=[False, False, False]
        ).reset_index(drop=True)
        df.insert(0, "Rank", np.arange(1, len(df) + 1))

        st.success(f"Found {len(df)} candidates.")

        st.subheader("🏆 SETUP 3 — TOP CANDIDATES")
        display = df[
            ["Rank","Stock","Current","Buy Zone","Stop","T1","T2",
             "Potential %","R:R","Fundamental","Base","Pullback",
             "Reversal","Breakout","Score","Signal"]
        ].copy()

        st.dataframe(
            display.style.format({
                "Current": "₹{:.2f}",
                "Stop": "₹{:.2f}",
                "T1": "₹{:.2f}",
                "T2": "₹{:.2f}",
                "Potential %": "{:.1f}%",
                "R:R": "{:.2f}x",
                "Fundamental": "{:.0f}",
                "Base": "{:.0f}",
                "Pullback": "{:.0f}",
                "Reversal": "{:.0f}",
                "Breakout": "{:.0f}",
                "Score": "{:.0f}",
            }),
            use_container_width=True,
            hide_index=True,
        )

        st.subheader("🔎 Detailed candidate data")
        st.dataframe(df, use_container_width=True, hide_index=True)

        csv = df.to_csv(index=False).encode("utf-8")
        st.download_button(
            "⬇️ Download scan results CSV",
            data=csv,
            file_name="setup3_yahoo_scan_results.csv",
            mime="text/csv",
        )

st.divider()
st.warning(
    "Research tool only. Yahoo Finance data can be delayed, incomplete, or unavailable. "
    "A 20–30% opportunity estimate is not a guarantee. Validate every signal with "
    "historical backtesting and your own risk rules before trading."
)
