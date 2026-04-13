import streamlit as st
import yfinance as yf
import pandas as pd
from datetime import datetime

st.set_page_config(page_title="Monthly Seasonality Ranker", layout="wide")

st.title("Monthly Seasonality Ranker")

st.write("Ranks tickers by historical average return for this month and next month.")

# -----------------------------
# Sidebar
# -----------------------------
st.sidebar.header("Settings")

default_tickers = """SPY
QQQ
IWM
TLT
^GSPC
^DJI
^IXIC
^RUT
^VIX
^FTSE
^GDAXI
^FCHI
^N225
^HSI
000001.SS
^AXJO
^STOXX50E
^BVSP
EURUSD=X
USDJPY=X
GBPUSD=X
USDCHF=X
AUDUSD=X
USDCAD=X
NZDUSD=X
EURJPY=X
GBPJPY=X
EURGBP=X
EURCHF=X
AUDJPY=X
GC=F
SI=F
CL=F
BZ=F
NG=F
HG=F
ZC=F
ZW=F
ZS=F
KC=F
SB=F
CT=F
BTC-USD
ETH-USD
^TNX
DX-Y.NYB
"""

tickers_text = st.sidebar.text_area(
    "Tickers (one per line)",
    value=default_tickers,
    height=250
)

start_year = st.sidebar.number_input(
    "Start Year", min_value=1900, max_value=2100, value=2010, step=1
)

end_year = st.sidebar.number_input(
    "End Year", min_value=1900, max_value=2100, value=2025, step=1
)

min_years = st.sidebar.number_input(
    "Minimum years of data", min_value=1, max_value=50, value=5, step=1
)

run = st.sidebar.button("Run Scan")

# -----------------------------
# Helpers
# -----------------------------
def parse_tickers(text: str) -> list[str]:
    tickers = [line.strip().upper() for line in text.splitlines() if line.strip()]
    seen = set()
    result = []
    for t in tickers:
        if t not in seen:
            seen.add(t)
            result.append(t)
    return result


@st.cache_data(show_spinner=False)
def download_data(symbol: str, start: str, end: str):
    return yf.download(symbol, start=start, end=end, auto_adjust=True, progress=False)


def get_close_series(df: pd.DataFrame) -> pd.Series:
    if df.empty:
        return pd.Series(dtype=float)

    if "Close" not in df.columns:
        return pd.Series(dtype=float)

    prices = df["Close"]

    if isinstance(prices, pd.DataFrame):
        prices = prices.iloc[:, 0]

    prices = pd.to_numeric(prices, errors="coerce").dropna()
    return prices


def monthly_return(prices: pd.Series, year: int, month: int):
    try:
        month_start = pd.Timestamp(year=year, month=month, day=1)

        if month == 12:
            next_month_start = pd.Timestamp(year=year + 1, month=1, day=1)
        else:
            next_month_start = pd.Timestamp(year=year, month=month + 1, day=1)

        month_end = next_month_start - pd.Timedelta(days=1)

        if month_start > prices.index[-1]:
            return None

        start_idx = prices.index.get_indexer([month_start], method="nearest")[0]
        end_idx = prices.index.get_indexer([month_end], method="nearest")[0]

        if end_idx <= start_idx:
            return None

        start_price = float(prices.iloc[start_idx])
        end_price = float(prices.iloc[end_idx])

        return (end_price - start_price) / start_price * 100.0

    except Exception:
        return None


def analyze_ticker(symbol: str, start_year: int, end_year: int, current_month: int, next_month: int):
    download_start = f"{start_year}-01-01"
    download_end = f"{end_year}-12-31"

    try:
        df = download_data(symbol, download_start, download_end)
    except Exception:
        return None

    prices = get_close_series(df)
    if prices.empty:
        return None

    current_month_returns = []
    next_month_returns = []

    for year in range(start_year, end_year + 1):
        r1 = monthly_return(prices, year, current_month)
        if r1 is not None:
            current_month_returns.append(r1)

        r2 = monthly_return(prices, year, next_month)
        if r2 is not None:
            next_month_returns.append(r2)

    current_avg = None
    next_avg = None
    current_win_rate = None
    next_win_rate = None

    if len(current_month_returns) >= min_years:
        cur = pd.Series(current_month_returns, dtype=float)
        current_avg = cur.mean()
        current_win_rate = (cur > 0).mean() * 100

    if len(next_month_returns) >= min_years:
        nxt = pd.Series(next_month_returns, dtype=float)
        next_avg = nxt.mean()
        next_win_rate = (nxt > 0).mean() * 100

    if current_avg is None and next_avg is None:
        return None

    return {
        "Ticker": symbol,
        "This Month Avg %": current_avg,
        "This Month Win Rate %": current_win_rate,
        "This Month Years": len(current_month_returns),
        "Next Month Avg %": next_avg,
        "Next Month Win Rate %": next_win_rate,
        "Next Month Years": len(next_month_returns),
    }


# -----------------------------
# Main
# -----------------------------
if run:
    tickers = parse_tickers(tickers_text)

    if not tickers:
        st.error("Please enter at least one ticker.")
        st.stop()

    today = datetime.today()
    current_month = today.month
    next_month = 1 if current_month == 12 else current_month + 1

    month_names = {
        1: "January", 2: "February", 3: "March", 4: "April",
        5: "May", 6: "June", 7: "July", 8: "August",
        9: "September", 10: "October", 11: "November", 12: "December"
    }

    st.subheader(f"This Month: {month_names[current_month]}")
    st.subheader(f"Next Month: {month_names[next_month]}")

    results = []
    progress = st.progress(0)
    status = st.empty()

    total = len(tickers)

    for i, ticker in enumerate(tickers, start=1):
        status.text(f"Processing {ticker} ({i}/{total})")
        result = analyze_ticker(ticker, int(start_year), int(end_year), current_month, next_month)
        if result is not None:
            results.append(result)
        progress.progress(i / total)

    status.empty()
    progress.empty()

    if not results:
        st.warning("No valid results found.")
        st.stop()

    results_df = pd.DataFrame(results)

    this_month_df = (
        results_df.dropna(subset=["This Month Avg %"])
        .sort_values("This Month Avg %", ascending=False)
        [["Ticker", "This Month Avg %", "This Month Win Rate %", "This Month Years"]]
        .reset_index(drop=True)
    )

    next_month_df = (
        results_df.dropna(subset=["Next Month Avg %"])
        .sort_values("Next Month Avg %", ascending=False)
        [["Ticker", "Next Month Avg %", "Next Month Win Rate %", "Next Month Years"]]
        .reset_index(drop=True)
    )

    col1, col2 = st.columns(2)

    with col1:
        st.subheader(f"Ranked by {month_names[current_month]} Average Return")
        st.dataframe(
            this_month_df.style.format({
                "This Month Avg %": "{:.2f}",
                "This Month Win Rate %": "{:.1f}"
            }),
            use_container_width=True
        )

    with col2:
        st.subheader(f"Ranked by {month_names[next_month]} Average Return")
        st.dataframe(
            next_month_df.style.format({
                "Next Month Avg %": "{:.2f}",
                "Next Month Win Rate %": "{:.1f}"
            }),
            use_container_width=True
        )

else:
    st.info("Enter your tickers and click 'Run Scan'.")
