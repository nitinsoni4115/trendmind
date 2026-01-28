import sqlite3
from pathlib import Path
from prophet import Prophet
import pandas as pd

from ai_signals import save_ai_signal

DB_PATH = Path(__file__).resolve().parent / "trendmind.db"
SYMBOLS = ["AAPL", "MSFT", "TSLA"]

def load_price(symbol):
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql("""
        SELECT date, close
        FROM stocks
        WHERE symbol = ?
        ORDER BY date
    """, conn, params=(symbol,))
    conn.close()

    df["date"] = pd.to_datetime(df["date"])
    return df

def load_sentiment(symbol):
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql("""
        SELECT avg_sentiment
        FROM daily_sentiment
        WHERE symbol = ?
        ORDER BY date DESC
        LIMIT 1
    """, conn, params=(symbol,))
    conn.close()

    return None if df.empty else float(df["avg_sentiment"].iloc[0])

def forecast_price(df):
    df = df.rename(columns={"date": "ds", "close": "y"})
    model = Prophet()
    model.fit(df)
    future = model.make_future_dataframe(periods=15)
    forecast = model.predict(future)
    return forecast["yhat"].iloc[-1]

def decide(latest, forecast, sentiment):
    confidence = min(95, 60 + len(df_price) // 3)

    if forecast > latest:
        if sentiment is not None and sentiment < -0.2:
            return "WATCH", "Uptrend but negative sentiment", confidence
        return "BUY", "Forecasted upside with trend support", confidence
    else:
        return "AVOID", "Forecast indicates downside risk", confidence

if __name__ == "__main__":
    print("🤖 Generating AI Signals...")

    for symbol in SYMBOLS:
        df_price = load_price(symbol)
        if df_price.empty:
            continue

        latest_price = df_price["close"].iloc[-1]
        forecast_price_ = forecast_price(df_price)
        sentiment = load_sentiment(symbol)

        decision, reason, confidence = decide(
            latest_price, forecast_price_, sentiment
        )

        save_ai_signal(
            symbol=symbol,
            decision=decision,
            reason=reason,
            latest_price=latest_price,
            forecast_price=forecast_price_,
            sentiment=sentiment,
            confidence=confidence
        )

    print("✅ AI Signals generation complete")
