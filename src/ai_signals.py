import sqlite3
from datetime import datetime
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent / "trendmind.db"


def save_ai_signal(
    symbol: str,
    decision: str,
    reason: str,
    latest_price: float,
    forecast_price: float,
    sentiment: float | None,
    confidence: int
):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO ai_signals
        (symbol, decision, reason, latest_price, forecast_price, sentiment, confidence, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        symbol,
        decision,
        reason,
        latest_price,
        forecast_price,
        sentiment,
        confidence,
        datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    ))

    conn.commit()
    conn.close()

    print(f"✅ AI signal saved for {symbol}: {decision}")
