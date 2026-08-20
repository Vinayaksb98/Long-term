
import concurrent.futures
from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st
import yfinance as yf

st.set_page_config(
    page_title="Setup 3 — Support → Pullback → Reversal → Breakout",
    page_icon="🎯",
    layout="wide",
)

st.title("🎯 SETUP 3 — SUPPORT → PULLBACK → REVERSAL → BREAKOUT")
st.caption(
    "Yahoo Finance powered research scanner for fundamentally strong NSE stocks "
    "forming 20–45 session bases, pulling back toward support, showing reversal "
    "evidence and offering a realistic 20–30% technical opportunity."
)

st.success(
    "✅ Fixed version: the NSE universe is bundled locally. "
    "The app no longer waits for a remote NSE CSV to load."
)

with st.expander("How this version works"):
    st.markdown("""
    **1. Universe:** bundled NIFTY 500 symbol list — no NSE-universe download is needed.

    **2. Fundamental filter:** Yahoo Finance data is checked for market cap ≥ ₹10,000 Cr
    and a combination of ROE/ROCE, growth, leverage, cash flow and profitability.

    **3. Technical sequence:** 20–45 session base → support → pullback →
    reversal → breakout.

    **4. Risk:** structural-support stop, T1 around +10%, and T2 around +25%
    when the setup has enough room.

    **Important:** missing Yahoo data is not treated as a positive fundamental signal.
    A 20–30% target is an opportunity estimate, not a guarantee.
    """)

UNIVERSE_FILE = Path(__file__).with_name("nifty500_symbols.csv")

@st.cache_data
def load_universe():
    df = pd.read_csv(UNIVERSE_FILE)
    symbols = (
        df["Symbol"].astype(str).str.strip().replace("", np.nan).dropna().unique().tolist()
    )
    return [s + ".NS" for s in symbols]

def pct(x):
    try:
        return float(x) * 100
    except Exception:
        return np.nan

@st.cache_data(ttl=12 * 60 * 60, show_spinner=False)
def yahoo_info(symbol):
    try:
        return yf.Ticker(symbol).get_info()
    except Exception:
        return {}

@st.cache_data(ttl=6 * 60 * 60, show_spinner=False)
def yahoo_history(symbol):
    try:
        return yf.download(
            symbol, period="6mo", interval="1d",
            auto_adjust=False, progress=False, threads=False
        )
    except Exception:
        return pd.DataFrame()

def fundamentals(info):
    try:
        de = float(info.get("debtToEquity")) / 100
    except Exception:
        de = np.nan
    return {
        "market_cap": info.get("marketCap"),
        "roe": pct(info.get("returnOnEquity")),
        "roce": pct(info.get("returnOnCapitalEmployed")),
        "revenue_growth": pct(info.get("revenueGrowth")),
        "earnings_growth": pct(info.get("earningsGrowth")),
        "debt_equity": de,
        "ocf": info.get("operatingCashflow"),
        "fcf": info.get("freeCashflow"),
        "margin": pct(info.get("profitMargins")),
        "name": info.get("longName") or info.get("shortName") or "",
    }

def fundamental_score(f):
    try:
        mc = float(f["market_cap"])
    except Exception:
        return 0, False

    if mc < 100_000_000_000:  # ₹10,000 Cr
        return 0, False

    score = 25

    if np.isfinite(f["roe"]):
        score += 15 if f["roe"] >= 15 else 8 if f["roe"] >= 10 else 0
    if np.isfinite(f["roce"]):
        score += 15 if f["roce"] >= 12 else 8 if f["roce"] >= 8 else 0
    if np.isfinite(f["revenue_growth"]):
        score += 10 if f["revenue_growth"] >= 8 else 5 if f["revenue_growth"] > 0 else 0
    if np.isfinite(f["earnings_growth"]):
        score += 10 if f["earnings_growth"] >= 10 else 5 if f["earnings_growth"] > 0 else 0
    if np.isfinite(f["debt_equity"]):
        score += 10 if f["debt_equity"] <= 1 else 5 if f["debt_equity"] <= 1.5 else 0

    try:
        if float(f["ocf"]) > 0:
            score += 10
    except Exception:
        pass

    if np.isfinite(f["margin"]) and f["margin"] > 0:
        score += 5

    return score, score >= 60

def history_frame(df):
    if df is None or df.empty:
        return pd.DataFrame()
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    cols = ["High", "Low", "Close", "Volume"]
    if any(c not in df.columns for c in cols):
        return pd.DataFrame()
    x = df[cols].copy()
    for c in cols:
        x[c] = pd.to_numeric(x[c], errors="coerce")
    return x.dropna(subset=["Close"])

def technical_setup(raw):
    h = history_frame(raw)
    if len(h) < 80:
        return None

    close, high, low, vol = h["Close"], h["High"], h["Low"], h["Volume"]
    current = float(close.iloc[-1])

    atr = float((high - low).rolling(14).mean().iloc[-1])
    if not np.isfinite(atr) or atr <= 0:
        atr = current * 0.02

    # Tightest of the allowed 20–45 session bases.
    best_window, best_range = 45, 999.0
    for w in (20, 25, 30, 35, 40, 45):
        b = h.tail(w)
        rng = (b["High"].max() - b["Low"].min()) / max(b["Low"].min(), 1e-9) * 100
        if rng < best_range:
            best_window, best_range = w, float(rng)

    b = h.tail(best_window)
    support = float(b["Low"].quantile(0.20))
    resistance = float(b["High"].quantile(0.80))
    dist_support = (current - support) / max(current, 1e-9) * 100

    sma5 = close.rolling(5).mean()
    bullish_candle = close.iloc[-1] >= (high.iloc[-1] + low.iloc[-1]) / 2
    reversal = bool(
        bullish_candle
        and current >= float(sma5.iloc[-1])
        and current > float(close.iloc[-4])
    )

    avg_vol = float(vol.tail(20).replace(0, np.nan).mean())
    vol_ratio = current_vol_ratio = (
        float(vol.iloc[-1] / avg_vol) if np.isfinite(avg_vol) and avg_vol > 0 else np.nan
    )

    near_support = 0 <= dist_support <= 8
    pullback = near_support or (dist_support <= 12 and current < resistance)
    breakout = bool(
        current > resistance * 1.005
        and (not np.isfinite(vol_ratio) or vol_ratio >= 1.20)
    )

    stop = max(support - max(0.8 * atr, support * 0.03), support * 0.90)
    t1 = current * 1.10
    t2 = current * 1.25
    rr = (t2 - current) / max(current - stop, 1e-9)

    base_score = 20 if best_range <= 20 else 15 if best_range <= 30 else 8
    pullback_score = 20 if near_support else 12 if pullback else 0
    reversal_score = 20 if reversal else 10 if current > close.iloc[-4] else 0
    breakout_score = 20 if breakout else 8 if current >= resistance * 0.97 else 0

    if breakout:
        signal = "🚀 BREAKOUT BUY"
    elif reversal and near_support:
        signal = "🟢 REVERSAL BUY"
    elif pullback:
        signal = "🟡 PULLBACK WATCH"
    else:
        signal = "🔵 WAIT"

    return dict(
        current=current, buy_low=support, buy_high=support * 1.03, stop=stop,
        t1=t1, t2=t2, potential=25.0, rr=rr,
        base=base_score, pullback=pullback_score, reversal=reversal_score,
        breakout=breakout_score, base_sessions=best_window, base_range=best_range,
        support=support, resistance=resistance, volume_ratio=current_vol_ratio,
        signal=signal
    )

def scan_one(symbol):
    try:
        f = fundamentals(yahoo_info(symbol))
        fs, strong = fundamental_score(f)
        if not strong:
            return None

        tech = technical_setup(yahoo_history(symbol))
        if not tech:
            return None

        total = fs + tech["base"] + tech["pullback"] + tech["reversal"] + tech["breakout"]
        if tech["rr"] < 2:
            return None

        return {
            "Stock": symbol.replace(".NS", ""),
            "Company": f["name"],
            "Current": tech["current"],
            "Buy Zone": f"₹{tech['buy_low']:.2f} – ₹{tech['buy_high']:.2f}",
            "Stop": tech["stop"], "T1": tech["t1"], "T2": tech["t2"],
            "Potential %": tech["potential"], "R:R": tech["rr"],
            "Fundamental": fs, "Base": tech["base"], "Pullback": tech["pullback"],
            "Reversal": tech["reversal"], "Breakout": tech["breakout"],
            "Score": total, "Base Sessions": tech["base_sessions"],
            "Base Range %": tech["base_range"], "Support": tech["support"],
            "Resistance": tech["resistance"], "Volume Ratio": tech["volume_ratio"],
            "Signal": tech["signal"]
        }
    except Exception:
        return None

st.sidebar.header("Scanner controls")
try:
    universe = load_universe()
except Exception as e:
    st.error(f"Could not load bundled stock universe: {e}")
    st.stop()

scan_count = st.sidebar.select_slider(
    "Stocks to scan",
    options=[50, 100, 200, 300, 400, 500],
    value=100
)
workers = st.sidebar.slider("Parallel Yahoo requests", 2, 8, 4)
min_score = st.sidebar.slider("Minimum score", 60, 140, 80, 5)

st.caption(f"Local universe loaded: {len(universe)} symbols. No NSE CSV download is required.")

if st.button("🔄 Scan Setup 3 — Yahoo Fundamentals", type="primary"):
    symbols = universe[:scan_count]
    rows = []
    progress = st.progress(0)
    status = st.empty()

    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as ex:
        futures = {ex.submit(scan_one, s): s for s in symbols}
        total = len(futures)
        done = 0
        for fut in concurrent.futures.as_completed(futures):
            done += 1
            progress.progress(done / total)
            status.write(f"Scanning Yahoo Finance data: {done}/{total}")
            result = fut.result()
            if result:
                rows.append(result)

    progress.empty()
    status.empty()

    if not rows:
        st.warning(
            "No stocks passed the filters. Try 200–500 stocks or a lower minimum score. "
            "Yahoo may also temporarily limit requests."
        )
    else:
        result = pd.DataFrame(rows)
        result = result[result["Score"] >= min_score].sort_values(
            ["Score", "R:R"], ascending=[False, False]
        ).reset_index(drop=True)
        result.insert(0, "Rank", np.arange(1, len(result) + 1))

        st.success(f"Found {len(result)} candidates.")
        cols = [
            "Rank", "Stock", "Current", "Buy Zone", "Stop", "T1", "T2",
            "Potential %", "R:R", "Fundamental", "Base", "Pullback",
            "Reversal", "Breakout", "Score", "Signal"
        ]
        st.subheader("🏆 SETUP 3 — TOP QUALITY CANDIDATES")
        st.dataframe(
            result[cols].style.format({
                "Current": "₹{:.2f}", "Stop": "₹{:.2f}",
                "T1": "₹{:.2f}", "T2": "₹{:.2f}",
                "Potential %": "{:.1f}%", "R:R": "{:.2f}x",
                "Fundamental": "{:.0f}", "Base": "{:.0f}",
                "Pullback": "{:.0f}", "Reversal": "{:.0f}",
                "Breakout": "{:.0f}", "Score": "{:.0f}"
            }),
            use_container_width=True, hide_index=True
        )

        st.subheader("🔎 Details")
        st.dataframe(result, use_container_width=True, hide_index=True)

        st.download_button(
            "⬇️ Download results CSV",
            result.to_csv(index=False).encode("utf-8"),
            "setup3_yahoo_results.csv",
            "text/csv"
        )

st.divider()
st.warning(
    "Research tool only. Yahoo Finance data may be delayed, incomplete or rate-limited. "
    "A 20–30% opportunity estimate is not a guarantee. Backtest before live trading."
)
