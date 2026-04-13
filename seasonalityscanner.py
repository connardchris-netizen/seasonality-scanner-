import streamlit as st
import yfinance as yf
import pandas as pd
from datetime import datetime

st.set_page_config(page_title="Monthly Seasonality Ranker", layout="wide")

st.title("Monthly Seasonality Ranker")
st.write("Ranked by historical average return for this month and next month, grouped by asset type.")

# =========================================================
# Asset groups from your list
# =========================================================

ASSET_GROUPS = {
    "Forex": {
        "EURUSD=X": "EUR/USD",
        "JPY=X": "USD/JPY",
        "GBPUSD=X": "GBP/USD",
        "CHF=X": "USD/CHF",
        "AUDUSD=X": "AUD/USD",
        "CAD=X": "USD/CAD",
        "NZDUSD=X": "NZD/USD",
        "EURJPY=X": "EUR/JPY",
        "GBPJPY=X": "GBP/JPY",
        "EURGBP=X": "EUR/GBP",
        "EURCHF=X": "EUR/CHF",
        "AUDJPY=X": "AUD/JPY",
        "DX-Y.NYB": "US Dollar Index (DXY)",
    },
    "Commodities": {
        "GC=F": "Gold",
        "SI=F": "Silver",
        "CL=F": "WTI Crude Oil",
        "BZ=F": "Brent Crude",
        "NG=F": "Natural Gas",
        "HG=F": "Copper",
        "ZC=F": "Corn",
        "ZW=F": "Wheat",
        "ZS=F": "Soybeans",
        "KC=F": "Coffee",
        "SB=F": "Sugar",
        "CT=F": "Cotton",
    },
    "Indices": {
        "^GSPC": "S&P 500",
        "^DJI": "Dow Jones",
        "^IXIC": "Nasdaq Composite",
        "^RUT": "Russell 2000",
        "^VIX": "Volatility Index",
        "^FTSE": "FTSE 100",
        "^GDAXI": "DAX",
        "^FCHI": "CAC 40",
        "^N225": "Nikkei 225",
        "^HSI": "Hang Seng",
        "000001.SS": "Shanghai Composite",
        "^AXJO": "ASX 200",
        "^STOXX50E": "Euro Stoxx 50",
        "^BVSP": "IBOVESPA",
    },
    "Crypto": {
        "BTC-USD": "Bitcoin",
        "ETH-USD": "Ethereum",
    },
    "Rates": {
        "^TNX": "US 10Y Yield",
    },
}

# Flatten for easy lookup
TICKER_INFO = {}
for asset_type, mapping in ASSET_GROUPS.items():
    for ticker, label in mapping.items():
        TICKER_INFO[ticker] = {"Asset Type": asset_type, "Label": label}

ALL_TICKERS = list(TICKER_INFO.keys())

# =========================================================
# Sidebar
# =========================================================

st.sidebar.header("Settings")

start_year = st.sidebar.number_input(
    "Start Year", min_value=1900, max_value=2100, value=2010, step=1
)

end_year = st.sidebar.number_input(
    "End Year", min_value=1900, max_value=2100, value=2025, step=1
)

min_years = st.sidebar.number_input(
    "Minimum years of data", min_value=1, max_value=50, value=5, step=1
)

selected_groups = st.sidebar.multiselect(
    "Asset Groups",
    options=list(ASSET_GROUPS.keys()),
    default=list(ASSET_GROUPS.keys())
)

run = st.sidebar.button("Run Scan")

# =========================================================
# Helpers
# =========================================================

@st.cache_data(show_spinner=False)
def download_data(symbol: str, start: str, end: str):
    return yf.download(symbol, start=start, end=end, auto_adjust=True, progress=False)

def get_close_series(df: pd.DataFrame) -> pd.Series:
    if df.empty:
        return pd.Series(dtype=float)

    if "Close" not in df.columns:
        return pd.Series(dtype=float)

    prices = df["Close"]

    # yfinance can sometimes return a DataFrame here
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

def analyze_ticker(symbol: str, start_year: int, end_year: int, current_month: int, next_month: int, min_years: int):
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
    current_win_rate = None
    next_avg = None
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
        "Label": TICKER_INFO[symbol]["Label"],
        "Asset Type": TICKER_INFO[symbol]["Asset Type"],
        "This Month Avg %": current_avg,
        "This Month Win Rate %": current_win_rate,
        "This Month Years": len(current_month_returns),
        "Next Month Avg %": next_avg,
        "Next Month Win Rate %": next_win_rate,
        "Next Month Years": len(next_month_returns),
    }

def format_table(df: pd.DataFrame, avg_col: str, win_col: str):
    return df.style.format({
        avg_col: "{:.2f}",
        win_col: "{:.1f}",
    })

def show_grouped_tables(source_df: pd.DataFrame, group_order: list[str], avg_col: str, win_col: str, years_col: str):
    for group_name in group_order:
        group_df = source_df[source_df["Asset Type"] == group_name].copy()

        if group_df.empty:
            continue

        group_df = group_df.sort_values(avg_col, ascending=False).reset_index(drop=True)
        group_df.index = group_df.index + 1

        st.markdown(f"### {group_name}")
        st.dataframe(
            group_df[["Ticker", "Label", avg_col, win_col, years_col]].style.format({
                avg_col: "{:.2f}",
                win_col: "{:.1f}",
            }),
            use_container_width=True
        )
        
# =========================================================
# Main
# =========================================================

if run:
    if not selected_groups:
        st.error("Select at least one asset group.")
        st.stop()

    tickers_to_scan = [
        ticker
        for ticker in ALL_TICKERS
        if TICKER_INFO[ticker]["Asset Type"] in selected_groups
    ]

    today = datetime.today()
    current_month = today.month
    next_month = 1 if current_month == 12 else current_month + 1

    month_names = {
        1: "January", 2: "February", 3: "March", 4: "April",
        5: "May", 6: "June", 7: "July", 8: "August",
        9: "September", 10: "October", 11: "November", 12: "December"
    }

    st.subheader(f"{month_names[current_month]} and {month_names[next_month]} seasonal ranking")

    results = []
    progress = st.progress(0)
    status = st.empty()

    total = len(tickers_to_scan)

    for i, ticker in enumerate(tickers_to_scan, start=1):
        status.text(f"Processing {ticker} ({i}/{total})")
        result = analyze_ticker(
            ticker,
            int(start_year),
            int(end_year),
            current_month,
            next_month,
            int(min_years)
        )
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
        .copy()
    )

    next_month_df = (
        results_df.dropna(subset=["Next Month Avg %"])
        .copy()
    )

    col1, col2 = st.columns(2)

    with col1:
        st.subheader(f"Ranked by {month_names[current_month]} Average Return")
        show_grouped_tables(
            this_month_df,
            selected_groups,
            "This Month Avg %",
            "This Month Win Rate %",
            "This Month Years"
        )

    with col2:
        st.subheader(f"Ranked by {month_names[next_month]} Average Return")
        show_grouped_tables(
            next_month_df,
            selected_groups,
            "Next Month Avg %",
            "Next Month Win Rate %",
            "Next Month Years"
        )

else:
    st.info("Choose asset groups and click 'Run Scan'.")
