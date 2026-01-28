import sqlite3
from datetime import datetime
from pathlib import Path

# ✅ SAME DB AS ALL OTHER SCRIPTS
DB_PATH = Path(__file__).resolve().parent / "trendmind.db"

def get_connection():
    return sqlite3.connect(DB_PATH)

def create_tables():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS articles (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ticker TEXT,
        title TEXT NOT NULL,
        description TEXT,
        content TEXT,
        url TEXT UNIQUE,
        source TEXT,
        published_at TEXT,
        collected_at TEXT NOT NULL
    )
    """)

    cursor.execute("""
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
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS daily_sentiment (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        symbol TEXT NOT NULL,
        date TEXT NOT NULL,
        avg_sentiment REAL NOT NULL,
        sentiment_label TEXT NOT NULL,
        article_count INTEGER NOT NULL,
        created_at TEXT NOT NULL,
        UNIQUE(symbol, date)
    )
    """)

    # 🧠 SINGLE STORE FOR AI SIGNALS
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS ai_signals (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        symbol TEXT NOT NULL,
        decision TEXT NOT NULL,
        reason TEXT,
        latest_price REAL,
        forecast_price REAL,
        sentiment REAL,
        confidence INTEGER,
        created_at TEXT NOT NULL
    )
    """)

    conn.commit()
    conn.close()

    print("✅ Tables created INSIDE src/trendmind.db")
    print("• articles")
    print("• stocks")
    print("• daily_sentiment")
    print("• ai_signals")

if __name__ == "__main__":
    create_tables()
