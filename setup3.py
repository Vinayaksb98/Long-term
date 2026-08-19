import streamlit as st
import pandas as pd
import numpy as np
from io import StringIO
import requests

st.set_page_config(
    page_title="Setup 3 — Support Pullback Reversal Breakout",
    page_icon="🎯",
    layout="wide",
)

st.markdown("""
<style>
.block-container {padding-top:1rem;padding-left:.8rem;padding-right:.8rem}
h1 {font-size:1.55rem!important}
@media(max-width:640px){
 h1{font-size:1.25rem!important}
 .stButton button{width:100%}
}
</style>
""", unsafe_allow_html=True)

st.title("🎯 SETUP 3 — SUPPORT → PULLBACK → REVERSAL → BREAKOUT")
st.caption(
    "Research scanner for fundamentally strong NSE stocks that form 20–45 session bases, "
    "pull back toward structural support, show reversal evidence, and have a realistic "
    "20–30% technical opportunity."
)

# ---------------- Indicators ----------------

def ema(s, n):
    return s.ewm(span=n, adjust=False).mean()

def rsi(s, n=14):
    d = s.diff()
    up = d.clip(lower=0)
    dn = -d.clip(upper=0)
    au = up.ewm(alpha=1/n, adjust=False).mean()
    ad = dn.ewm(alpha=1/n, adjust=False).mean()
    rs = au / ad.replace(0, np.nan)
    return 100 - 100 / (1 + rs)

def atr(df, n=14):
    p = df.Close.shift(1)
    tr = pd.concat([
        df.High - df.Low,
        (df.High - p).abs(),
        (df.Low - p).abs()
    ], axis=1).max(axis=1)
    return tr.ewm(alpha=1/n, adjust=False).mean()

def macd(s):
    m = ema(s, 12) - ema(s, 26)
    sig = ema(m, 9)
    return m, sig, m - sig

def adx(df, n=14):
    up = df.High.diff()
    dn = -df.Low.diff()
    plus = np.where((up > dn) & (up > 0), up, 0.0)
    minus = np.where((dn > up) & (dn > 0), dn, 0.0)
    p = df.Close.shift(1)
    tr = pd.concat([
        df.High - df.Low,
        (df.High - p).abs(),
        (df.Low - p).abs()
    ], axis=1).max(axis=1)
    av = tr.ewm(alpha=1/n, adjust=False).mean()
    pi = 100 * pd.Series(plus, index=df.index).ewm(alpha=1/n, adjust=False).mean() / av.replace(0, np.nan)
    mi = 100 * pd.Series(minus, index=df.index).ewm(alpha=1/n, adjust=False).mean() / av.replace(0, np.nan)
    dx = 100 * (pi - mi).abs() / (pi + mi).replace(0, np.nan)
    return dx.ewm(alpha=1/n, adjust=False).mean()

def prepare(df):
    if df is None or df.empty:
        return None
    df = df.copy()
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df.columns = [str(c).strip().title() for c in df.columns]
    if "Date" not in df.columns and isinstance(df.index, pd.DatetimeIndex):
        df = df.reset_index().rename(columns={"index": "Date"})
    need = ["Date", "Open", "High", "Low", "Close", "Volume"]
    if any(c not in df.columns for c in need):
        return None
    df["Date"] = pd.to_datetime(df.Date, errors="coerce")
    for c in need[1:]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df = df.dropna(subset=need).sort_values("Date").drop_duplicates("Date")
    if len(df) < 210:
        return None

    df["EMA9"] = ema(df.Close, 9)
    df["EMA20"] = ema(df.Close, 20)
    df["EMA50"] = ema(df.Close, 50)
    df["SMA200"] = df.Close.rolling(200, min_periods=200).mean()
    df["RSI"] = rsi(df.Close, 14)
    df["MACD"], df["MACD_Signal"], df["MACD_Hist"] = macd(df.Close)
    df["ATR"] = atr(df, 14)
    df["ADX"] = adx(df, 14)
    df["VolMA20"] = df.Volume.rolling(20, min_periods=20).mean()
    df["RVOL"] = df.Volume / df.VolMA20
    df["VolMA5"] = df.Volume.rolling(5, min_periods=5).mean()
    df["VolTrend"] = df["VolMA5"] / df["VolMA20"]

    # Completed 20-session breakout reference.
    df["BreakoutLevel"] = df.High.rolling(20, min_periods=20).max().shift(1)
    df["DistanceToBreakout"] = (df["BreakoutLevel"] - df["Close"]) / df["BreakoutLevel"] * 100

    # Volatility compression.
    df["BBMid"] = df.Close.rolling(20, min_periods=20).mean()
    df["BBStd"] = df.Close.rolling(20, min_periods=20).std()
    df["BBWidth"] = (4 * df["BBStd"]) / df["BBMid"]

    df["RSISlope"] = df.RSI - df.RSI.shift(3)
    df["MACDHistSlope"] = df.MACD_Hist - df.MACD_Hist.shift(3)
    return df

# ---------------- NSE / Yahoo ----------------

@st.cache_data(ttl=86400, show_spinner=False)
def get_nse_universe():
    url = "https://archives.nseindia.com/content/equities/EQUITY_L.csv"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/151 Safari/537.36",
        "Accept": "text/csv,text/plain,application/json,*/*",
    }
    try:
        r = requests.get(url, headers=headers, timeout=20)
        if r.ok and len(r.content) > 1000:
            d = pd.read_csv(StringIO(r.text))
            symcol = next((c for c in d.columns if str(c).upper() == "SYMBOL"), None)
            sercol = next((c for c in d.columns if str(c).upper() == "SERIES"), None)
            if symcol:
                if sercol:
                    d = d[d[sercol].astype(str).str.upper().eq("EQ")]
                return sorted(set(d[symcol].astype(str).str.strip().str.upper()))
    except Exception:
        pass
    return []

@st.cache_data(ttl=3600, show_spinner=False)
def download_batch(symbols, period="1y"):
    import yfinance as yf
    tickers = [s + ".NS" for s in symbols]
    try:
        return yf.download(
            tickers, period=period, interval="1d", auto_adjust=False,
            progress=False, threads=True, group_by="ticker"
        )
    except Exception:
        return None

def extract_symbol(raw, sym):
    if raw is None or raw.empty:
        return None
    t = sym + ".NS"
    try:
        if isinstance(raw.columns, pd.MultiIndex):
            if t in raw.columns.get_level_values(0):
                d = raw[t].copy()
            elif t in raw.columns.get_level_values(-1):
                d = raw.xs(t, axis=1, level=-1).copy()
            else:
                return None
        else:
            d = raw.copy()
        return d.reset_index()
    except Exception:
        return None

# ---------------- Permanent fundamentals ----------------

FUNDAMENTAL_COLUMNS = [
    "Symbol", "MarketCapCr", "ROE", "ROCE", "SalesGrowth3Y",
    "ProfitGrowth3Y", "DebtEquity", "CFOPositive"
]

@st.cache_data
def load_fundamentals(path="fundamentals.csv"):
    try:
        f = pd.read_csv(path)
        f.columns = [str(c).strip() for c in f.columns]
        missing = [c for c in FUNDAMENTAL_COLUMNS if c not in f.columns]
        if missing:
            return None, "Missing columns: " + ", ".join(missing)
        f["Symbol"] = f["Symbol"].astype(str).str.upper().str.strip()
        for c in FUNDAMENTAL_COLUMNS[1:-1]:
            f[c] = pd.to_numeric(f[c], errors="coerce")
        f["CFOPositive"] = (
            f["CFOPositive"].astype(str).str.strip().str.lower()
            .map({
                "true": True, "yes": True, "1": True, "y": True,
                "false": False, "no": False, "0": False, "n": False
            })
        )
        return f.drop_duplicates("Symbol"), None
    except FileNotFoundError:
        return None, "fundamentals.csv not found."
    except Exception as e:
        return None, f"Could not read fundamentals.csv: {e}"

def fundamental_score(row):
    if row is None:
        return np.nan, []

    checks = [
        ("Market cap ≥ ₹10,000 Cr", pd.notna(row.MarketCapCr) and row.MarketCapCr >= 10000, 4),
        ("ROCE ≥15%", pd.notna(row.ROCE) and row.ROCE >= 15, 4),
        ("ROE ≥15%", pd.notna(row.ROE) and row.ROE >= 15, 3),
        ("3Y sales growth >0%", pd.notna(row.SalesGrowth3Y) and row.SalesGrowth3Y > 0, 3),
        ("3Y profit growth >0%", pd.notna(row.ProfitGrowth3Y) and row.ProfitGrowth3Y > 0, 4),
        ("Debt/Equity ≤1", pd.notna(row.DebtEquity) and row.DebtEquity <= 1, 3),
        ("Operating cash flow positive", bool(row.CFOPositive) if pd.notna(row.CFOPositive) else False, 2),
        ("Profit growth ≥10%", pd.notna(row.ProfitGrowth3Y) and row.ProfitGrowth3Y >= 10, 2),
    ]
    return sum(p for _, ok, p in checks if ok), checks

# ---------------- Setup 3 structure ----------------

def structure(d):
    """
    Defines:
    - 20–45 completed-session base
    - structural support from the lower part of the base
    - pullback zone around support
    - breakout resistance
    """
    completed = d.iloc[:-1].tail(45).copy()
    if len(completed) < 20:
        return None

    # Use the most recent 20–45 completed sessions as the candidate base.
    high = float(completed.High.max())
    low = float(completed.Low.min())
    close = float(d.Close.iloc[-1])
    base_range_pct = (high - low) / low * 100 if low > 0 else np.nan

    # Support is a robust lower-zone estimate rather than the absolute lowest tick.
    lows = completed.Low.nsmallest(max(3, min(7, len(completed)//5)))
    support = float(lows.median())

    atrv = float(d.ATR.iloc[-1]) if pd.notna(d.ATR.iloc[-1]) else close * 0.02
    support_zone_low = support - 0.35 * atrv
    support_zone_high = support + 0.60 * atrv

    breakout = float(completed.High.max())

    # A second resistance estimate using recent completed highs.
    recent20 = completed.tail(20)
    breakout20 = float(recent20.High.max())
    breakout = max(breakout20, breakout)

    return {
        "days": len(completed),
        "base_high": high,
        "base_low": low,
        "base_range_pct": base_range_pct,
        "support": support,
        "support_low": support_zone_low,
        "support_high": support_zone_high,
        "breakout": breakout,
        "height": high - low,
        "atr": atrv,
    }

def base_quality(d, s):
    x = d.iloc[-1]
    points = 0
    checks = []

    ok = 20 <= s["days"] <= 45
    checks.append(("20–45 completed-session base", ok, 4))
    points += 4 if ok else 0

    ok = s["base_range_pct"] <= 20
    checks.append(("Base range ≤20%", ok, 3))
    points += 3 if ok else 0

    vol5 = float(d.Volume.tail(5).mean())
    vol20 = float(d.Volume.tail(20).mean())
    ok = vol20 > 0 and vol5 <= vol20 * 1.05
    checks.append(("Recent volume drying", ok, 3))
    points += 3 if ok else 0

    bb_cut = d.BBWidth.rolling(40, min_periods=20).quantile(0.40).iloc[-1]
    ok = pd.notna(x.BBWidth) and pd.notna(bb_cut) and x.BBWidth <= bb_cut
    checks.append(("Volatility compressed", ok, 3))
    points += 3 if ok else 0

    # Count completed sessions that tested the upper 15% of the base.
    test_level = s["base_high"] - 0.15 * s["height"]
    tests = int((d.iloc[:-1].tail(s["days"]).High >= test_level).sum())
    ok = tests >= 2
    checks.append(("Upper-base resistance tested ≥2 times", ok, 3))
    points += 3 if ok else 0

    ok = s["base_range_pct"] <= 25
    checks.append(("Base not excessively wide", ok, 2))
    points += 2 if ok else 0

    ok = s["support"] > 0 and s["base_high"] > s["support"]
    checks.append(("Clear structural support", ok, 2))
    points += 2 if ok else 0

    return points, checks

def pullback_state(d, s):
    x = d.iloc[-1]
    close = float(x.Close)
    atrv = s["atr"]

    # Pullback is defined relative to structural support.
    in_support = s["support_low"] <= close <= s["support_high"]
    near_support = (
        not in_support and
        abs(close - s["support"]) <= 1.75 * atrv
    )

    # Reversal confirmation: price turns up after the pullback.
    bullish_candle = x.Close > x.Open and x.Close > d.Close.iloc[-2]
    higher_low = len(d) >= 6 and float(d.Low.iloc[-1]) >= float(d.Low.iloc[-4:-1].min())
    rsi_turn = pd.notna(x.RSI) and x.RSI >= 45 and pd.notna(x.RSISlope) and x.RSISlope > 0
    ema_turn = pd.notna(x.EMA9) and pd.notna(x.EMA20) and x.EMA9 > x.EMA20
    macd_turn = pd.notna(x.MACDHistSlope) and x.MACDHistSlope > 0
    volume_confirm = pd.notna(x.RVOL) and x.RVOL >= 1.05

    reversal_points = sum([
        4 if bullish_candle else 0,
        4 if higher_low else 0,
        3 if rsi_turn else 0,
        3 if ema_turn else 0,
        2 if macd_turn else 0,
        2 if volume_confirm else 0,
        2 if pd.notna(x.Close) and x.Close >= x.EMA20 else 0,
    ])

    reversal_confirmed = (
        reversal_points >= 13 and
        bullish_candle and
        higher_low and
        rsi_turn
    )

    # Breakout confirmation is deliberately separate from reversal.
    breakout_level = s["breakout"]
    distance = (breakout_level - close) / breakout_level * 100 if breakout_level > 0 else np.inf
    breakout_confirmed = close > breakout_level and pd.notna(x.RVOL) and x.RVOL >= 1.20

    if breakout_confirmed:
        state = "🚀 BREAKOUT BUY"
    elif reversal_confirmed and in_support:
        state = "🟢 REVERSAL BUY"
    elif in_support or near_support:
        state = "🟡 PULLBACK WATCH"
    elif close > breakout_level:
        state = "🟠 BREAKOUT — CONFIRM"
    else:
        state = "🔵 WAIT FOR PULLBACK"

    return {
        "state": state,
        "in_support": in_support,
        "near_support": near_support,
        "reversal_confirmed": reversal_confirmed,
        "reversal_points": reversal_points,
        "breakout_confirmed": breakout_confirmed,
        "distance_to_breakout": distance,
        "breakout_level": breakout_level,
        "checks": [
            ("Bullish reversal candle", bullish_candle, 4),
            ("Higher-low / no fresh breakdown", higher_low, 4),
            ("RSI ≥45 and rising", rsi_turn, 3),
            ("EMA9 > EMA20", ema_turn, 3),
            ("MACD histogram improving", macd_turn, 2),
            ("RVOL ≥1.05", volume_confirm, 2),
            ("Price ≥ EMA20", pd.notna(x.Close) and x.Close >= x.EMA20, 2),
        ],
    }

def trade_levels(d, s, pb):
    x = d.iloc[-1]
    close = float(x.Close)
    atrv = s["atr"]

    # Entry is not automatically current price.
    # For a pullback setup, define a confirmation entry inside/above support.
    support_entry = min(
        s["support_high"] + 0.25 * atrv,
        s["support"] + 1.00 * atrv
    )

    if pb["state"] == "🟢 REVERSAL BUY":
        entry = max(close, support_entry)
    elif pb["state"] == "🚀 BREAKOUT BUY":
        entry = close
    else:
        # This is a planned entry, not a current buy signal.
        entry = support_entry

    stop = min(
        s["support_low"] - 0.35 * atrv,
        float(d.Low.tail(10).min()) - 0.15 * atrv
    )
    if stop >= entry:
        stop = entry - 1.25 * atrv

    # Measured move from the base; use 20–30% as the preferred target band.
    measured = s["breakout"] + s["height"]
    t1 = max(s["breakout"], entry * 1.10)
    candidates = [
        measured,
        entry * 1.20,
        entry * 1.25,
        entry * 1.30,
    ]
    # T2 favors a 20–30% target when structurally plausible.
    above20 = [v for v in candidates if v >= entry * 1.20]
    t2 = min(above20, key=lambda v: abs(v - entry * 1.25)) if above20 else measured
    t2 = max(t2, t1)

    risk = entry - stop
    reward = t2 - entry
    rr = reward / risk if risk > 0 else np.nan
    potential = reward / entry * 100 if entry > 0 else np.nan

    return {
        "entry": float(entry),
        "stop": float(stop),
        "t1": float(t1),
        "t2": float(t2),
        "potential": float(potential),
        "rr": float(rr) if pd.notna(rr) else np.nan,
    }

def score_setup(d, fund_row):
    s = structure(d)
    if s is None:
        return None

    base_points, base_checks = base_quality(d, s)
    pb = pullback_state(d, s)
    levels = trade_levels(d, s, pb)

    fund_points, fund_checks = fundamental_score(fund_row)

    # Opportunity score /15.
    opp_checks = [
        ("Potential 20–30%", 20 <= levels["potential"] <= 35, 5),
        ("Potential ≥20%", levels["potential"] >= 20, 3),
        ("R:R ≥2.0", pd.notna(levels["rr"]) and levels["rr"] >= 2.0, 4),
        ("R:R ≥1.5", pd.notna(levels["rr"]) and levels["rr"] >= 1.5, 3),
    ]
    opp_points = sum(p for _, ok, p in opp_checks if ok)

    # Reversal max 20.
    reversal_points = pb["reversal_points"]

    # Breakout readiness max 20.
    x = d.iloc[-1]
    breakout_checks = [
        ("Within 5% of breakout level", 0 <= pb["distance_to_breakout"] <= 5, 4),
        ("Breakout resistance exists", s["breakout"] > 0, 3),
        ("Price above EMA20", pd.notna(x.EMA20) and x.Close >= x.EMA20, 3),
        ("EMA20 rising", len(d) >= 5 and x.EMA20 > d.EMA20.iloc[-5], 3),
        ("RSI 50–70", pd.notna(x.RSI) and 50 <= x.RSI <= 70, 2),
        ("RVOL ≥0.9", pd.notna(x.RVOL) and x.RVOL >= 0.9, 2),
        ("MACD histogram ≥0", pd.notna(x.MACD_Hist) and x.MACD_Hist >= 0, 1),
        ("ADX ≥18", pd.notna(x.ADX) and x.ADX >= 18, 2),
    ]
    breakout_points = sum(p for _, ok, p in breakout_checks if ok)

    # A full score requires verified fundamentals. No technical-only A+.
    if pd.notna(fund_points):
        total = fund_points + base_points + reversal_points + breakout_points + opp_points
    else:
        total = np.nan

    fundamentals_ok = pd.notna(fund_points) and fund_points >= 18
    market_cap_ok = (
        fund_row is not None and
        pd.notna(fund_row.MarketCapCr) and
        fund_row.MarketCapCr >= 10000
    )
    base_ok = base_points >= 13
    opportunity_ok = levels["potential"] >= 20 and pd.notna(levels["rr"]) and levels["rr"] >= 1.5

    # Signals are intentionally entry-aware.
    if not fundamentals_ok or not market_cap_ok:
        signal = "⚪ FUNDAMENTAL FILTER"
    elif pb["state"] == "🚀 BREAKOUT BUY" and total >= 75 and opportunity_ok:
        signal = "🚀 BREAKOUT BUY"
    elif pb["state"] == "🟢 REVERSAL BUY" and total >= 70 and opportunity_ok and base_ok:
        signal = "🟢 REVERSAL BUY"
    elif (pb["in_support"] or pb["near_support"]) and total >= 65:
        signal = "🟡 PULLBACK WATCH"
    elif base_ok and opportunity_ok and total >= 65:
        signal = "🔵 WAIT FOR PULLBACK"
    else:
        signal = "⚪ AVOID"

    return {
        "total": total,
        "fundamental": fund_points,
        "base": base_points,
        "reversal": reversal_points,
        "breakout": breakout_points,
        "opportunity": opp_points,
        "signal": signal,
        "structure": s,
        "pullback": pb,
        "levels": levels,
        "base_checks": base_checks,
        "reversal_checks": pb["checks"],
        "breakout_checks": breakout_checks,
        "opportunity_checks": opp_checks,
        "fund_checks": fund_checks,
    }

# ---------------- UI ----------------

with st.sidebar:
    st.header("SETUP 3 Settings")
    minimum = st.slider("Minimum score", 0, 100, 65)
    batch_size = st.slider("Batch size", 10, 100, 40, step=10)
    max_symbols = st.slider("Maximum stocks to scan", 50, 2000, 500, step=50)
    st.divider()
    st.write("🎯 20–45 session consolidation")
    st.write("🎯 Market cap ≥ ₹10,000 Cr")
    st.write("🎯 Pullback to structural support")
    st.write("🎯 Reversal confirmation before entry")
    st.write("🎯 Breakout confirmation separately")
    st.write("🎯 Preferred target: 20–30%")
    st.write("🎯 Preferred R:R: ≥2")
    st.info(
        "The app does not buy simply because a stock falls to support. "
        "It waits for reversal confirmation."
    )
    st.warning("Yahoo Finance data can be delayed or rate-limited. Research tool only.")

st.subheader("📁 Permanent fundamental database")
fund_df, fund_error = load_fundamentals()

if fund_error:
    st.error(fund_error)
    st.info(
        "The included fundamentals.csv is a template. Populate it with verified data "
        "before expecting A+ fundamental filtering."
    )
elif fund_df is not None and not fund_df.empty:
    st.success(f"Loaded fundamentals for {len(fund_df):,} symbols.")
else:
    st.warning("fundamentals.csv is empty. No stock can pass the fundamental filter.")

if "results3" not in st.session_state:
    st.session_state.results3 = None
if "details3" not in st.session_state:
    st.session_state.details3 = {}
if "universe3" not in st.session_state:
    st.session_state.universe3 = []

if st.button("🔄 Scan Setup 3 — Support / Pullback / Reversal"):
    symbols = get_nse_universe()
    if not symbols:
        st.error("Could not download the NSE equity master. Try again later.")
        symbols = []

    symbols = symbols[:max_symbols]
    st.session_state.universe3 = symbols

    if symbols:
        progress = st.progress(0, text=f"Scanning {len(symbols)} NSE symbols...")
        results = []
        details = {}
        total_batches = (len(symbols) + batch_size - 1) // batch_size

        for bi in range(total_batches):
            batch = symbols[bi * batch_size:(bi + 1) * batch_size]
            raw = download_batch(batch)

            for sym in batch:
                try:
                    d = prepare(extract_symbol(raw, sym))
                    if d is None:
                        continue

                    fund_row = None
                    if fund_df is not None and not fund_df.empty:
                        m = fund_df[fund_df.Symbol.eq(sym)]
                        if not m.empty:
                            fund_row = m.iloc[0]

                    # Strict fundamental gate: this is your stated strategy requirement.
                    if fund_row is None:
                        continue
                    if pd.isna(fund_row.MarketCapCr) or fund_row.MarketCapCr < 10000:
                        continue

                    a = score_setup(d, fund_row)
                    if a is None or pd.isna(a["total"]):
                        continue

                    s = a["structure"]
                    pb = a["pullback"]
                    lv = a["levels"]
                    x = d.iloc[-1]

                    # Keep only genuine base candidates and reasonable opportunity.
                    if not (20 <= s["days"] <= 45):
                        continue
                    if s["base_range_pct"] > 25:
                        continue
                    if lv["potential"] < 15:
                        continue

                    rec = {
                        "Stock": sym,
                        "Date": x.Date.date(),
                        "Current": float(x.Close),
                        "Support Zone": f"₹{s['support_low']:,.2f}–₹{s['support_high']:,.2f}",
                        "Support": s["support"],
                        "Planned Buy": lv["entry"],
                        "Stop": lv["stop"],
                        "Breakout": s["breakout"],
                        "T1": lv["t1"],
                        "T2": lv["t2"],
                        "Potential %": lv["potential"],
                        "R:R": lv["rr"],
                        "Fundamental": a["fundamental"],
                        "Base": a["base"],
                        "Reversal": a["reversal"],
                        "Breakout Score": a["breakout"],
                        "Opportunity": a["opportunity"],
                        "Score": a["total"],
                        "Signal": a["signal"],
                        "Base Days": s["days"],
                        "Base Range %": s["base_range_pct"],
                        "Distance to BO %": pb["distance_to_breakout"],
                        "RSI": float(x.RSI),
                        "RVOL": float(x.RVOL),
                        "ADX": float(x.ADX),
                    }
                    results.append(rec)
                    details[sym] = (a, d, rec)
                except Exception:
                    continue

            progress.progress(
                (bi + 1) / total_batches,
                text=f"Scanned {min((bi + 1) * batch_size, len(symbols))}/{len(symbols)}"
            )

        st.session_state.results3 = (
            pd.DataFrame(results).sort_values(
                ["Score", "Signal", "R:R"], ascending=[False, True, False]
            ).head(30)
            if results else pd.DataFrame()
        )
        st.session_state.details3 = details
        progress.empty()

r = st.session_state.results3

if r is not None and not r.empty:
    view = r[r.Score >= minimum].copy()
    view.insert(0, "Rank", range(1, len(view) + 1))

    st.subheader("🏆 SETUP 3 — SUPPORT / PULLBACK / REVERSAL CANDIDATES")

    main = view[
        [
            "Rank", "Stock", "Current", "Support Zone", "Planned Buy", "Stop",
            "Breakout", "T1", "T2", "Potential %", "R:R",
            "Fundamental", "Base", "Reversal", "Breakout Score",
            "Score", "Signal"
        ]
    ].copy()

    st.dataframe(
        main.style.format({
            "Current": "₹{:,.2f}",
            "Planned Buy": "₹{:,.2f}",
            "Stop": "₹{:,.2f}",
            "Breakout": "₹{:,.2f}",
            "T1": "₹{:,.2f}",
            "T2": "₹{:,.2f}",
            "Potential %": "{:.1f}%",
            "R:R": "{:.2f}x",
        }),
        use_container_width=True,
        hide_index=True,
    )

    st.caption(
        f"Universe scanned: {len(st.session_state.universe3)} symbols • "
        f"Fundamental gate: ₹10,000 Cr+ • Results ≥ {minimum}: {len(view)}"
    )

    sym = st.selectbox("Select a stock for detailed analysis", view.Stock.tolist())
    a, d, rec = st.session_state.details3[sym]
    s = a["structure"]
    pb = a["pullback"]
    lv = a["levels"]
    x = d.iloc[-1]

    c = st.columns(8)
    c[0].metric("Current", f"₹{x.Close:,.2f}")
    c[1].metric("Support", f"₹{s['support']:,.2f}")
    c[2].metric("Planned Buy", f"₹{lv['entry']:,.2f}")
    c[3].metric("Stop", f"₹{lv['stop']:,.2f}")
    c[4].metric("Breakout", f"₹{s['breakout']:,.2f}")
    c[5].metric("T2", f"₹{lv['t2']:,.2f}")
    c[6].metric("Potential", f"{lv['potential']:.1f}%")
    c[7].metric("R:R", f"{lv['rr']:.2f}x")

    st.info(
        f"**State: {pb['state']}** — Support zone ₹{s['support_low']:,.2f}–₹{s['support_high']:,.2f}. "
        "A support touch alone is not a buy signal; reversal confirmation is required."
    )

    st.write(
        f"**Score:** Fundamental {a['fundamental']}/25 • Base {a['base']}/20 • "
        f"Reversal {a['reversal']}/20 • Breakout {a['breakout']}/20 • "
        f"Opportunity {a['opportunity']}/15 • **Total {a['total']:.0f}/100**"
    )

    with st.expander("🧩 Why this stock scored this way", expanded=True):
        rows = []
        for section, checks in [
            ("Fundamental", a["fund_checks"]),
            ("Base", a["base_checks"]),
            ("Reversal", a["reversal_checks"]),
            ("Breakout", a["breakout_checks"]),
            ("Opportunity", a["opportunity_checks"]),
        ]:
            for name, ok, pts in checks:
                rows.append({
                    "Section": section,
                    "Condition": name,
                    "Result": "✓" if ok else "✗",
                    "Points": pts if ok else 0,
                })
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    chart = d.set_index("Date")[["Close", "EMA20", "EMA50", "BreakoutLevel"]].copy()
    st.line_chart(chart, height=500)

    st.write(
        f"**Trade plan:** Support ₹{s['support']:,.2f} • "
        f"Planned buy ₹{lv['entry']:,.2f} • Stop ₹{lv['stop']:,.2f} • "
        f"Breakout ₹{s['breakout']:,.2f} • T1 ₹{lv['t1']:,.2f} • T2 ₹{lv['t2']:,.2f}"
    )
else:
    st.info(
        "Click **Scan Setup 3** after populating fundamentals.csv. "
        "The scanner will only rank stocks that pass the ₹10,000 Cr+ market-cap gate."
    )

st.divider()
st.warning(
    "Research tool only. A 20–30% target is an opportunity estimate, not a guarantee. "
    "The scanner is heuristic and must be validated with historical backtesting before live use."
)
