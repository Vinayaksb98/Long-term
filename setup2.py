import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from io import StringIO
import requests

st.set_page_config(
    page_title="Setup 2 — Quality Base Reversal NSE",
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

st.title("🎯 SETUP 2 — QUALITY BASE → REVERSAL → BREAKOUT")
st.caption(
    "Independent research scanner • seeks fundamentally strong stocks building 20–45 session bases "
    "with reversal evidence and 20–30% technical opportunity"
)

# ---------------- Technical indicators ----------------

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

def macd(s):
    m = ema(s, 12) - ema(s, 26)
    sig = ema(m, 9)
    return m, sig, m - sig

def atr(df, n=14):
    p = df.Close.shift(1)
    tr = pd.concat([
        df.High - df.Low,
        (df.High - p).abs(),
        (df.Low - p).abs()
    ], axis=1).max(axis=1)
    return tr.ewm(alpha=1/n, adjust=False).mean()

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
    df["EMA21"] = ema(df.Close, 21)
    df["EMA50"] = ema(df.Close, 50)
    df["SMA200"] = df.Close.rolling(200, min_periods=200).mean()
    df["RSI"] = rsi(df.Close, 14)
    df["MACD"], df["MACD_Signal"], df["MACD_Hist"] = macd(df.Close)
    df["ADX"] = adx(df, 14)
    df["ATR"] = atr(df, 14)

    df["VolMA20"] = df.Volume.rolling(20, min_periods=20).mean()
    df["RVOL"] = df.Volume / df.VolMA20

    # 20-day breakout reference, excluding current session.
    df["BOP"] = df.High.rolling(20, min_periods=20).max().shift(1)
    df["DistanceToBO"] = (df["BOP"] - df["Close"]) / df["BOP"] * 100

    df["BB_MID"] = df.Close.rolling(20, min_periods=20).mean()
    df["BB_STD"] = df.Close.rolling(20, min_periods=20).std()
    df["BB_WIDTH"] = (4 * df["BB_STD"]) / df["BB_MID"]

    df["RSI_Slope"] = df.RSI - df.RSI.shift(3)
    df["MACD_Hist_Slope"] = df.MACD_Hist - df.MACD_Hist.shift(3)
    df["ADX_Slope"] = df.ADX - df.ADX.shift(3)

    df["VolMA5"] = df.Volume.rolling(5, min_periods=5).mean()
    df["VolTrend"] = df["VolMA5"] / df["VolMA20"]
    return df

# ---------------- NSE / Yahoo data ----------------

@st.cache_data(ttl=86400, show_spinner=False)
def get_nse_universe():
    urls = [
        "https://archives.nseindia.com/content/equities/EQUITY_L.csv",
        "https://www.nseindia.com/api/equity-master",
    ]
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/151 Safari/537.36",
        "Accept": "text/csv,text/plain,application/json,*/*",
    }
    for url in urls:
        try:
            r = requests.get(url, headers=headers, timeout=15)
            if r.ok and len(r.content) > 1000 and url.endswith(".csv"):
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
            tickers,
            period=period,
            interval="1d",
            auto_adjust=False,
            progress=False,
            threads=True,
            group_by="ticker",
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

# ---------------- Resistance / base / target ----------------

def find_resistances(d):
    x = d.iloc[-1]
    close = float(x.Close)
    levels = []

    if len(d) >= 21:
        levels.append(("20D high", float(d.High.iloc[-21:-1].max()), 3))
    if len(d) >= 51:
        levels.append(("50D high", float(d.High.iloc[-51:-1].max()), 2))

    h = d.High.iloc[:-2].tail(100)
    if len(h) >= 7:
        roll = h.rolling(7, center=True).max()
        peaks = h[(h >= roll) & roll.notna()]
        for level in peaks.dropna().tolist():
            levels.append(("Swing resistance", float(level), 2))

    raw = [
        (name, level, weight)
        for name, level, weight in levels
        if np.isfinite(level) and level > close * 1.005
    ]
    if not raw:
        return []

    raw.sort(key=lambda z: z[1])
    clusters = []
    for item in raw:
        if not clusters or abs(item[1] - clusters[-1]["level"]) / clusters[-1]["level"] > 0.008:
            clusters.append({"level": item[1], "strength": item[2], "sources": [item[0]]})
        else:
            c = clusters[-1]
            c["level"] = (c["level"] + item[1]) / 2
            c["strength"] += item[2]
            c["sources"].append(item[0])
    return sorted(clusters, key=lambda c: c["level"])

def base_metrics(d):
    # Current session is excluded so the base describes the completed consolidation.
    base = d.iloc[-46:-1].copy() if len(d) >= 47 else d.iloc[:-1].copy()
    days = len(base)
    if days == 0:
        return {}

    high = float(base.High.max())
    low = float(base.Low.min())
    close = float(d.Close.iloc[-1])
    base_range = (high - low) / low * 100 if low > 0 else np.nan

    # Use 20–45 sessions as the preferred consolidation window.
    preferred_days = 20 <= days <= 45

    # Volume/volatility contraction.
    vol_ma5 = float(base.Volume.tail(5).mean())
    vol_ma20 = float(base.Volume.tail(20).mean()) if len(base) >= 20 else float(base.Volume.mean())
    volume_dry = vol_ma20 > 0 and vol_ma5 <= vol_ma20 * 1.05

    bb_cut = d["BB_WIDTH"].rolling(40, min_periods=20).quantile(0.40).iloc[-1]
    bb_compressed = pd.notna(d["BB_WIDTH"].iloc[-1]) and pd.notna(bb_cut) and d["BB_WIDTH"].iloc[-1] <= bb_cut

    resistance = find_resistances(d)
    bop = float(d.BOP.iloc[-1]) if pd.notna(d.BOP.iloc[-1]) else np.nan

    # Price should remain reasonably close to the base's upper boundary.
    near_upper = pd.notna(bop) and 0 <= (bop - close) / bop * 100 <= 5

    # Count recent tests near resistance.
    if pd.notna(bop) and bop > 0:
        touches = int((base.High >= bop * 0.985).sum())
    else:
        touches = 0

    # Support should not have been broken by a large amount.
    recent_low = float(base.Low.tail(20).min()) if len(base) >= 20 else low
    support_holding = recent_low >= low * 0.97

    return {
        "days": days,
        "high": high,
        "low": low,
        "range_pct": base_range,
        "height": high - low,
        "preferred_days": preferred_days,
        "volume_dry": volume_dry,
        "bb_compressed": bb_compressed,
        "near_upper": near_upper,
        "touches": touches,
        "support_holding": support_holding,
        "resistances": resistance,
    }

def calculate_targets(d, bm):
    x = d.iloc[-1]
    close = float(x.Close)
    atrv = float(x.ATR) if pd.notna(x.ATR) else close * 0.02
    resistances = bm.get("resistances", [])

    structural = resistances[0]["level"] if resistances else close + 1.0 * atrv
    measured = float(x.BOP) + bm["height"] if pd.notna(x.BOP) else np.nan

    # Prefer a measured move when it gives the requested 20%+ opportunity.
    candidates = [v for v in [structural, measured] if pd.notna(v) and v > close]
    t1 = structural
    t2 = max(candidates) if candidates else close + atrv
    t3 = close + 3 * atrv

    # Primary "opportunity" target is the larger structurally justified objective.
    opportunity = max(t1, t2)
    potential = (opportunity - close) / close * 100 if close > 0 else np.nan

    # Structural/ATR stop.
    swing_low = float(d.Low.tail(10).min())
    atr_stop = close - 1.25 * atrv
    stop = min(swing_low, atr_stop)
    if stop >= close:
        stop = close - 1.25 * atrv

    risk = close - stop
    reward = opportunity - close
    rr = reward / risk if risk > 0 else np.nan

    return {
        "t1": float(t1),
        "t2": float(t2),
        "t3": float(t3),
        "target": float(opportunity),
        "potential": float(potential),
        "stop": float(stop),
        "rr": float(rr) if pd.notna(rr) else np.nan,
    }

# ---------------- Fundamental score ----------------

FUNDAMENTAL_COLUMNS = [
    "Symbol", "MarketCapCr", "ROE", "ROCE", "SalesGrowth3Y",
    "ProfitGrowth3Y", "DebtEquity", "CFOPositive"
]

def normalize_fundamentals(uploaded):
    if uploaded is None:
        return None, "No fundamental CSV uploaded."

    try:
        f = pd.read_csv(uploaded)
        f.columns = [str(c).strip() for c in f.columns]
        missing = [c for c in FUNDAMENTAL_COLUMNS if c not in f.columns]
        if missing:
            return None, "Missing columns: " + ", ".join(missing)

        f["Symbol"] = f["Symbol"].astype(str).str.upper().str.strip()
        for c in FUNDAMENTAL_COLUMNS[1:-1]:
            f[c] = pd.to_numeric(f[c], errors="coerce")

        f["CFOPositive"] = (
            f["CFOPositive"].astype(str).str.strip().str.lower()
            .map({"true": True, "yes": True, "1": True, "y": True,
                  "false": False, "no": False, "0": False, "n": False})
        )
        return f.drop_duplicates("Symbol"), None
    except Exception as e:
        return None, f"Could not read fundamentals CSV: {e}"

def fundamental_score(row):
    if row is None:
        return {"score": np.nan, "checks": []}

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
    return {
        "score": sum(p for _, ok, p in checks if ok),
        "checks": checks,
    }

# ---------------- 100-point strategy ----------------

def strategy_score(d, fund_row=None):
    x = d.iloc[-1]
    bm = base_metrics(d)
    ft = fundamental_score(fund_row)

    # Base = 20
    base_checks = [
        ("20–45 session consolidation", bm.get("preferred_days", False), 4),
        ("Base range ≤20%", pd.notna(bm.get("range_pct")) and bm["range_pct"] <= 20, 3),
        ("Volume drying/compressed", bm.get("volume_dry", False), 3),
        ("Volatility compressed", bm.get("bb_compressed", False), 3),
        ("Resistance tested ≥2 times", bm.get("touches", 0) >= 2, 3),
        ("Support holding", bm.get("support_holding", False), 2),
        ("Near upper base boundary", bm.get("near_upper", False), 2),
    ]
    base_points = sum(p for _, ok, p in base_checks if ok)

    # Reversal = 20
    lows = d.Low.tail(12).to_numpy()
    higher_low = len(lows) >= 6 and lows[-1] >= np.min(lows[:-3])
    ema_cross = pd.notna(x.EMA9) and pd.notna(x.EMA21) and x.EMA9 > x.EMA21
    rsi_turn = pd.notna(x.RSI) and x.RSI > 50 and pd.notna(x.RSI_Slope) and x.RSI_Slope > 0
    macd_turn = pd.notna(x.MACD_Hist) and pd.notna(x.MACD_Hist_Slope) and x.MACD_Hist_Slope > 0
    volume_turn = pd.notna(x.VolTrend) and x.VolTrend >= 1.0
    adx_turn = pd.notna(x.ADX_Slope) and x.ADX_Slope > 0

    reversal_checks = [
        ("Higher-low / no fresh lower low", higher_low, 4),
        ("EMA9 > EMA21", ema_cross, 3),
        ("RSI >50 and rising", rsi_turn, 3),
        ("MACD histogram improving", macd_turn, 2),
        ("Up-volume participation", volume_turn, 2),
        ("ADX improving", adx_turn, 2),
        ("Price ≥ EMA20", pd.notna(x.EMA20) and x.Close >= x.EMA20, 2),
        ("Price ≥ EMA50", pd.notna(x.EMA50) and x.Close >= x.EMA50, 2),
    ]
    reversal_points = sum(p for _, ok, p in reversal_checks if ok)

    # Breakout readiness = 20
    dist = float(x.DistanceToBO) if pd.notna(x.DistanceToBO) else np.inf
    bb_cut = d["BB_WIDTH"].rolling(40, min_periods=20).quantile(0.40).iloc[-1]
    breakout_checks = [
        ("0–5% below breakout resistance", 0 <= dist <= 5, 4),
        ("Resistance structure exists", len(bm.get("resistances", [])) >= 1, 3),
        ("Bollinger compression", pd.notna(x.BB_WIDTH) and pd.notna(bb_cut) and x.BB_WIDTH <= bb_cut, 3),
        ("EMA20 turning upward", len(d) >= 5 and x.EMA20 > d.EMA20.iloc[-5], 3),
        ("ADX ≥18", pd.notna(x.ADX) and x.ADX >= 18, 2),
        ("RVOL ≥0.9", pd.notna(x.RVOL) and x.RVOL >= 0.9, 2),
        ("MACD histogram above 0", pd.notna(x.MACD_Hist) and x.MACD_Hist > 0, 1),
        ("RSI 50–68", pd.notna(x.RSI) and 50 <= x.RSI <= 68, 2),
    ]
    breakout_points = sum(p for _, ok, p in breakout_checks if ok)

    targets = calculate_targets(d, bm)

    # Opportunity / risk-reward = 15
    opp_checks = [
        ("Potential ≥20%", targets["potential"] >= 20, 5),
        ("Potential ≥25%", targets["potential"] >= 25, 3),
        ("R:R ≥1.5", pd.notna(targets["rr"]) and targets["rr"] >= 1.5, 4),
        ("R:R ≥2.0", pd.notna(targets["rr"]) and targets["rr"] >= 2.0, 3),
    ]
    opportunity_points = sum(p for _, ok, p in opp_checks if ok)

    # Full score is 100 only when fundamentals are supplied.
    if pd.notna(ft["score"]):
        total = ft["score"] + base_points + reversal_points + breakout_points + opportunity_points
    else:
        total = base_points + reversal_points + breakout_points + opportunity_points

    fundamentals_ok = pd.notna(ft["score"]) and ft["score"] >= 18
    opportunity_ok = targets["potential"] >= 20 and pd.notna(targets["rr"]) and targets["rr"] >= 1.5
    technical_ok = base_points >= 13 and reversal_points >= 13 and breakout_points >= 13

    if fundamentals_ok and opportunity_ok and technical_ok and total >= 75:
        signal = "🟢 A+ CANDIDATE"
    elif fundamentals_ok and opportunity_ok and total >= 65:
        signal = "🟢 BUY CANDIDATE"
    elif total >= 55:
        signal = "🟡 WATCH"
    else:
        signal = "⚪ AVOID"

    return {
        "total": float(total),
        "fundamental": ft["score"],
        "base": base_points,
        "reversal": reversal_points,
        "breakout": breakout_points,
        "opportunity": opportunity_points,
        "signal": signal,
        "base_checks": base_checks,
        "reversal_checks": reversal_checks,
        "breakout_checks": breakout_checks,
        "opportunity_checks": opp_checks,
        "fund_checks": ft["checks"],
        "base": base_points,
        "base_metrics": bm,
        "targets": targets,
    }

# ---------------- Sidebar ----------------

with st.sidebar:
    st.header("SETUP 2 Settings")
    minimum = st.slider("Minimum total score", 0, 100, 65)
    universe = st.selectbox(
        "Stock universe",
        ["All NSE Equity (automatic)", "NSE liquid scan (faster)", "My reference stocks"]
    )
    batch_size = st.slider("Batch size", 10, 100, 40, step=10)
    max_symbols = st.slider("Maximum stocks to scan", 50, 2000, 500, step=50)
    st.divider()

    st.write("🎯 Strategy: Quality Base → Reversal → Breakout")
    st.write("Base: 20–45 sessions")
    st.write("Market-cap target: ≥₹10,000 Cr")
    st.write("Potential target: ≥20% preferred")
    st.write("Risk/reward: ≥1.5 preferred, ≥2 strong")
    st.warning(
        "Fundamental scoring is activated only when you upload a verified fundamentals CSV. "
        "The app will not invent fundamental data."
    )
    st.warning("Yahoo Finance data can be delayed/rate-limited. This is not a live NSE feed.")

st.subheader("📁 Fundamental data (optional but required for full A+ ranking)")
uploaded_fund = st.file_uploader(
    "Upload fundamentals CSV",
    type=["csv"],
    help="Required columns are documented in SETUP2_README.md."
)
fund_df, fund_error = normalize_fundamentals(uploaded_fund)
if fund_error:
    st.info(fund_error)

if fund_df is not None:
    st.success(f"Loaded fundamentals for {len(fund_df):,} symbols.")

if "scan_results_2" not in st.session_state:
    st.session_state.scan_results_2 = None
if "scan_details_2" not in st.session_state:
    st.session_state.scan_details_2 = {}
if "scan_universe_2" not in st.session_state:
    st.session_state.scan_universe_2 = []

# ---------------- Scan ----------------

if st.button("🔄 Scan Setup 2 — Quality Base / Reversal"):
    if universe == "My reference stocks":
        symbols = ["VOLTAMP", "WELCORP", "GVT&D", "PARAS", "CPPLUS", "EXICOM", "EBGNG"]
    else:
        symbols = get_nse_universe()
        if not symbols:
            st.error("Could not download the NSE equity master right now. Try again later.")
            symbols = []
        if universe == "NSE liquid scan (faster)" and symbols:
            symbols = symbols[:min(len(symbols), 1000)]

    symbols = symbols[:max_symbols]
    st.session_state.scan_universe_2 = symbols

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
                    if fund_df is not None:
                        matches = fund_df[fund_df.Symbol.eq(sym)]
                        if not matches.empty:
                            fund_row = matches.iloc[0]

                    a = strategy_score(d, fund_row)
                    x = d.iloc[-1]

                    # Require a meaningful base / breakout neighborhood for the ranked list.
                    bm = a["base_metrics"]
                    if bm.get("days", 0) < 20:
                        continue
                    if pd.isna(x.BOP) or pd.isna(x.RVOL):
                        continue

                    t = a["targets"]
                    rec = {
                        "Stock": sym,
                        "Date": x.Date.date(),
                        "Current": float(x.Close),
                        "Buy Zone": float(x.Close),
                        "Stop": t["stop"],
                        "T1": t["t1"],
                        "T2": t["t2"],
                        "T3": t["t3"],
                        "Potential %": t["potential"],
                        "R:R": t["rr"],
                        "Score": a["total"],
                        "Signal": a["signal"],
                        "Fundamental": a["fundamental"],
                        "Base": a["base"],
                        "Reversal": a["reversal"],
                        "Breakout": a["breakout"],
                        "Opportunity": a["opportunity"],
                        "Base Days": bm["days"],
                        "Base Range %": bm["range_pct"],
                        "Base Height": bm["height"],
                        "BOP": float(x.BOP),
                        "Distance %": float(x.DistanceToBO),
                        "RSI": float(x.RSI),
                        "ADX": float(x.ADX),
                        "RVOL": float(x.RVOL),
                        "EMA20": float(x.EMA20),
                        "EMA50": float(x.EMA50),
                        "ATR": float(x.ATR),
                    }
                    results.append(rec)
                    details[sym] = (a, d, rec)
                except Exception:
                    continue

            progress.progress(
                (bi + 1) / total_batches,
                text=f"Scanned {min((bi + 1) * batch_size, len(symbols))}/{len(symbols)}"
            )

        if results:
            st.session_state.scan_results_2 = (
                pd.DataFrame(results)
                .sort_values(["Score", "Potential %", "R:R"], ascending=False)
                .head(25)
            )
        else:
            st.session_state.scan_results_2 = pd.DataFrame()

        st.session_state.scan_details_2 = details
        progress.empty()

# ---------------- Results ----------------

r = st.session_state.scan_results_2
if r is not None and not r.empty:
    view = r[r.Score >= minimum].copy()
    view.insert(0, "Rank", range(1, len(view) + 1))

    st.subheader("🏆 SETUP 2 — TOP QUALITY BASE / REVERSAL CANDIDATES")

    main = view[
        ["Rank", "Stock", "Current", "Buy Zone", "Stop", "T1", "T2",
         "Potential %", "R:R", "Fundamental", "Base", "Reversal",
         "Breakout", "Score", "Signal"]
    ].copy()

    st.dataframe(
        main.style.format({
            "Current": "₹{:,.2f}",
            "Buy Zone": "₹{:,.2f}",
            "Stop": "₹{:,.2f}",
            "T1": "₹{:,.2f}",
            "T2": "₹{:,.2f}",
            "Potential %": "{:.1f}%",
            "R:R": "{:.2f}x",
        }),
        use_container_width=True,
        hide_index=True,
    )

    st.caption(
        f"Universe scanned: {len(st.session_state.scan_universe_2)} symbols • "
        f"Results meeting score ≥ {minimum}: {len(view)}"
    )

    with st.expander("📊 Full score / setup details", expanded=False):
        cols = [
            "Rank", "Stock", "Date", "Current", "Stop", "T1", "T2", "T3",
            "Potential %", "R:R", "Score", "Fundamental", "Base", "Reversal",
            "Breakout", "Opportunity", "Base Days", "Base Range %",
            "Base Height", "BOP", "Distance %", "RSI", "ADX", "RVOL",
        ]
        st.dataframe(
            view[cols].style.format({
                "Current": "₹{:,.2f}",
                "Stop": "₹{:,.2f}",
                "T1": "₹{:,.2f}",
                "T2": "₹{:,.2f}",
                "T3": "₹{:,.2f}",
                "Potential %": "{:.1f}%",
                "R:R": "{:.2f}x",
                "Base Range %": "{:.1f}%",
                "Base Height": "₹{:,.2f}",
                "BOP": "₹{:,.2f}",
                "Distance %": "{:.2f}%",
                "RSI": "{:.1f}",
                "ADX": "{:.1f}",
                "RVOL": "{:.2f}x",
            }),
            use_container_width=True,
            hide_index=True,
        )

    sym = st.selectbox("Select a stock for detailed analysis", view.Stock.tolist())
    a, d, rec = st.session_state.scan_details_2[sym]
    x = d.iloc[-1]

    c = st.columns(8)
    c[0].metric("Current", f"₹{x.Close:,.2f}")
    c[1].metric("Buy Zone", f"₹{rec['Buy Zone']:,.2f}")
    c[2].metric("Stop", f"₹{rec['Stop']:,.2f}")
    c[3].metric("T1", f"₹{rec['T1']:,.2f}")
    c[4].metric("T2", f"₹{rec['T2']:,.2f}")
    c[5].metric("Potential", f"{rec['Potential %']:.1f}%")
    c[6].metric("R:R", f"{rec['R:R']:.2f}x")
    c[7].metric("Score", f"{rec['Score']:.0f}/100")

    st.write(
        f"**Components:** Fundamental {rec['Fundamental'] if pd.notna(rec['Fundamental']) else 'N/A'}/25 • "
        f"Base {rec['Base']}/20 • Reversal {rec['Reversal']}/20 • "
        f"Breakout {rec['Breakout']}/20 • Opportunity {rec['Opportunity']}/15"
    )

    if pd.isna(rec["Fundamental"]):
        st.warning(
            "Fundamental score is N/A. Upload the fundamentals CSV to activate the "
            "₹10,000 Cr + quality filters."
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

    fig = go.Figure()
    fig.add_trace(go.Candlestick(
        x=d.Date, open=d.Open, high=d.High, low=d.Low, close=d.Close, name="Price"
    ))
    for col in ["EMA20", "EMA50", "SMA200", "BOP"]:
        fig.add_trace(go.Scatter(x=d.Date, y=d[col], name=col))
    fig.add_hline(y=rec["Stop"], line_dash="dot", annotation_text="Stop")
    fig.add_hline(y=rec["T1"], line_dash="dash", annotation_text="T1")
    fig.add_hline(y=rec["T2"], line_dash="dash", annotation_text="T2")
    fig.update_layout(height=600, xaxis_rangeslider_visible=False)
    st.plotly_chart(fig, use_container_width=True)

else:
    st.info(
        "Upload a fundamentals CSV if available, choose a universe, and press "
        "**Scan Setup 2 — Quality Base / Reversal**."
    )

st.divider()
st.warning(
    "Research tool only. This is a custom heuristic, not a prediction engine. "
    "20–30% is an opportunity target, not a guaranteed return. "
    "The full fundamental score requires a verified fundamentals CSV. "
    "Yahoo Finance data is not a live NSE feed."
)
