import sqlite3
import pandas as pd
from prophet import Prophet
import matplotlib.pyplot as plt
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent / "trendmind.db"


def load_stock_data(symbol):
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql(
        f"""
        SELECT date, close
        FROM stocks
        WHERE symbol = '{symbol}'
        ORDER BY date ASC
        """,
        conn,
    )
    conn.close()

    df["ds"] = pd.to_datetime(df["date"])
    df["y"] = df["close"]
    return df[["ds", "y"]]


def forecast_price(symbol, days=15):
    print(f"📈 Training Prophet model for {symbol} ...")

    df = load_stock_data(symbol)

    model = Prophet()
    model.fit(df)

    future = model.make_future_dataframe(periods=days)
    forecast = model.predict(future)

    model.plot(forecast)
    plt.title(f"{symbol} Stock Price Forecast")
    plt.show()

    model.plot_components(forecast)
    plt.show()

    print("✅ Forecast completed successfully")


if __name__ == "__main__":
    forecast_price("AAPL", days=15)
