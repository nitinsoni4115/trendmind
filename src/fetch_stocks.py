import sqlite3
from datetime import datetime
from pathlib import Path

import pandas as pd
import yfinance as yf

# Always use the DB inside src folder
DB_PATH = Path(__file__).resolve().parent / "trendmind.db"


def get_connection():
    return sqlite3.connect(DB_PATH)


def ensure_stocks_table():
    """
    Agar stocks table nahi hogi to bana dega.
    """
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS stocks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT NOT NULL,
            date TEXT NOT NULL,
            open REAL,
            high REAL,
            low REAL,
            close REAL,
            adj_close REAL,
            volume INTEGER,
            collected_at TEXT NOT NULL,
            UNIQUE(symbol, date)
        )
        """
    )
    conn.commit()
    conn.close()


def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
    yfinance download ke baad kabhi-kabhi MultiIndex columns aate hain:
       ('open', 'aapl'), ('high', 'aapl') ...
    Is function me hum sirf first level (field name) le kar
    sab ko lowercase kar dete hain: open, high, low, close, volume, date
    """
    new_cols = []
    for c in df.columns:
        if isinstance(c, tuple):
            # ('open', 'aapl') -> 'open'
            new_cols.append(str(c[0]).lower())
        else:
            new_cols.append(str(c).lower())
    df.columns = new_cols
    return df


def fetch_stock_history(symbol: str, period: str = "6mo", interval: str = "1d"):
    """
    yfinance se historical OHLCV data fetch karta hai
    (default: last 6 months, 1-day candles).
    """
    print(f"\n📥 Fetching {period} {interval} history for {symbol} ...")

    df = yf.download(symbol, period=period, interval=interval)

    if df.empty:
        print(f"⚠️ No data returned for {symbol}")
        return

    # Index ko column banao
    df = df.reset_index()

    # 👉 Normalize columns (tuple -> first element, lowercase)
    df = normalize_columns(df)

    # Ab ham 'open','high','low','close','date' expect karenge
    required_cols = ["date", "open", "high", "low", "close"]
    missing = [c for c in required_cols if c not in df.columns]
    if missing:
        print(f"⚠️ Missing expected columns for {symbol}: {missing}")
        print("   Available columns:", list(df.columns))
        return

    # Kabhi-kabhi missing prices hote hain → un rows ko drop kar do
    df = df.dropna(subset=["open", "high", "low", "close"])

    print(f"   ↳ received {len(df)} rows after cleaning")

    save_stock_history(symbol, df)


def save_stock_history(symbol: str, df: pd.DataFrame):
    """
    Cleaned dataframe ko SQLite 'stocks' table me save karega.
    Duplicate (symbol+date) rows IGNORE ho jayengi.
    """
    conn = get_connection()
    cur = conn.cursor()

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    inserted = 0
    skipped = 0

    for _, row in df.iterrows():
        ds = row.get("date")
        if pd.isna(ds):
            skipped += 1
            continue

        date_str = pd.to_datetime(ds).strftime("%Y-%m-%d")

        try:
            open_p = float(row["open"])
            high_p = float(row["high"])
            low_p = float(row["low"])
            close_p = float(row["close"])
        except (TypeError, ValueError, KeyError):
            skipped += 1
            continue

        # Adj close optional
        adj_close = row.get("adj close", None)
        if pd.isna(adj_close):
            adj_close = None
        else:
            adj_close = float(adj_close)

        volume = row.get("volume", None)
        if pd.isna(volume):
            volume = None
        else:
            volume = int(volume)

        try:
            cur.execute(
                """
                INSERT OR IGNORE INTO stocks
                (symbol, date, open, high, low, close, adj_close, volume, collected_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    symbol,
                    date_str,
                    open_p,
                    high_p,
                    low_p,
                    close_p,
                    adj_close,
                    volume,
                    now,
                ),
            )

            if cur.rowcount == 1:
                inserted += 1
            else:
                skipped += 1

        except sqlite3.Error as e:
            print(f"❌ DB error for {symbol} {date_str}: {e}")
            skipped += 1

    conn.commit()
    conn.close()

    print(
        f"✅ {symbol}: {inserted} rows inserted, {skipped} rows skipped "
        f"(duplicates / bad)."
    )


def main():
    ensure_stocks_table()

    symbols = ["AAPL", "MSFT", "TSLA"]

    for sym in symbols:
        fetch_stock_history(sym, period="6mo", interval="1d")


if __name__ == "__main__":
    main()
