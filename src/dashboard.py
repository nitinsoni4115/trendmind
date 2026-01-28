import sqlite3
from pathlib import Path
from datetime import datetime

import pandas as pd
import streamlit as st
from prophet import Prophet
from streamlit_autorefresh import st_autorefresh

# ================= CONFIG =================

DB_PATH = Path(__file__).resolve().parent / "trendmind.db"
REFRESH_SECONDS = 120

st.set_page_config(
    page_title="TrendMind Dashboard",
    layout="wide"
)

st_autorefresh(interval=REFRESH_SECONDS * 1000, key="trendmind_refresh")

# ================= DB =================

def get_conn():
    return sqlite3.connect(DB_PATH)

# ================= LOADERS =================

def load_stock_price(symbol):
    conn = get_conn()
    df = pd.read_sql(
        """SELECT date, close FROM stocks
           WHERE symbol = ?
           ORDER BY date""",
        conn,
        params=(symbol,),
    )
    conn.close()

    if df.empty:
        return df

    df["date"] = pd.to_datetime(df["date"])
    return df.sort_values("date")


def load_sentiment(symbol):
    conn = get_conn()
    df = pd.read_sql(
        """SELECT date, avg_sentiment FROM daily_sentiment
           WHERE symbol = ?
           ORDER BY date""",
        conn,
        params=(symbol,),
    )
    conn.close()

    if df.empty:
        return df

    df["date"] = pd.to_datetime(df["date"])
    return df.sort_values("date")


def load_signal_history(symbol):
    conn = get_conn()
    df = pd.read_sql(
        """SELECT decision, reason, latest_price, forecast_price,
                  sentiment, confidence, created_at
           FROM ai_signals
           WHERE symbol = ?
           ORDER BY created_at DESC
           LIMIT 10""",
        conn,
        params=(symbol,),
    )
    conn.close()
    return df


# ================= FORECAST =================

def run_forecast(price_df, sentiment_df=None, use_sentiment=False, days=15):
    df = price_df.rename(columns={"date": "ds", "close": "y"})
    model = Prophet()

    if use_sentiment and sentiment_df is not None and len(sentiment_df) >= 5:
        merged = pd.merge(
            df,
            sentiment_df.rename(columns={"date": "ds", "avg_sentiment": "sentiment"}),
            on="ds",
            how="left"
        )
        merged["sentiment"] = merged["sentiment"].ffill()
        merged = merged.dropna()

        model.add_regressor("sentiment")
        model.fit(merged)

        future = model.make_future_dataframe(periods=days)
        future["sentiment"] = merged["sentiment"].iloc[-1]
    else:
        model.fit(df)
        future = model.make_future_dataframe(periods=days)

    forecast = model.predict(future)
    return model, forecast


# ================= AI LOGIC =================

def generate_ai_explanation(price_df, forecast, sentiment_df, use_sentiment):
    trend_start = forecast["trend"].iloc[-5]
    trend_end = forecast["trend"].iloc[-1]

    if trend_end > trend_start:
        bias = "Bullish"
        trend_line = "📈 Price trend is upward."
    else:
        bias = "Bearish"
        trend_line = "📉 Price trend is downward."

    sentiment_value = None
    sentiment_line = "📰 Sentiment not used."

    if use_sentiment and not sentiment_df.empty:
        sentiment_value = sentiment_df["avg_sentiment"].iloc[-1]
        if sentiment_value > 0.2:
            sentiment_line = "📰 Sentiment is positive."
        elif sentiment_value < -0.2:
            sentiment_line = "📰 Sentiment is negative."
        else:
            sentiment_line = "📰 Sentiment is neutral."

    confidence = min(95, 60 + len(price_df) // 3)

    explanation = f"""
{trend_line}  
{sentiment_line}  
🎯 Confidence ~ **{confidence}%**
"""

    return bias, sentiment_value, confidence, explanation


def generate_ai_decision(bias, sentiment):
    if bias == "Bullish":
        if sentiment is not None and sentiment < -0.2:
            return "WATCH", "Uptrend exists but sentiment is negative."
        return "BUY", "Uptrend with acceptable risk."
    elif bias == "Bearish":
        return "AVOID", "Downtrend detected."
    return "HOLD", "Market direction unclear."


def save_ai_signal(symbol, decision, reason, latest, forecast, sentiment, confidence):
    conn = get_conn()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO ai_signals
        (symbol, decision, reason, latest_price, forecast_price,
         sentiment, confidence, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        symbol,
        decision,
        reason,
        latest,
        forecast,
        sentiment,
        confidence,
        datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    ))

    conn.commit()
    conn.close()


# ================= UI =================

st.title("📊 TrendMind — AI Market Intelligence Dashboard")

symbol = st.sidebar.selectbox("Select Stock", ["AAPL", "MSFT", "TSLA"])
use_sentiment = st.sidebar.checkbox("Include Sentiment")

price_df = load_stock_price(symbol)
sentiment_df = load_sentiment(symbol)

if price_df.empty:
    st.error("No price data available.")
    st.stop()

# -------- Charts --------

col1, col2 = st.columns(2)

with col1:
    st.subheader("📈 Price History")
    st.line_chart(price_df.set_index("date")[["close"]])

with col2:
    st.subheader("🧠 Market Sentiment")
    if sentiment_df.empty:
        st.warning("No sentiment data yet.")
    else:
        st.line_chart(sentiment_df.set_index("date")[["avg_sentiment"]])

# -------- Forecast --------

st.subheader("🔮 Price Forecast (15 Days)")
model, forecast = run_forecast(price_df, sentiment_df, use_sentiment)
st.pyplot(model.plot(forecast))

# -------- AI Explanation --------

bias, sentiment_value, confidence, explanation = generate_ai_explanation(
    price_df, forecast, sentiment_df, use_sentiment
)

st.subheader("🧠 Why this forecast?")
st.markdown(explanation)

# -------- AI Decision --------

decision, reason = generate_ai_decision(bias, sentiment_value)

latest_price = price_df["close"].iloc[-1]
future_price = forecast["yhat"].iloc[-1]

save_ai_signal(
    symbol,
    decision,
    reason,
    latest_price,
    future_price,
    sentiment_value,
    confidence
)

st.subheader("🤖 AI Decision")
st.success(
    f"""
**Decision:** {decision}  
**Reason:** {reason}

Latest Price: {latest_price:.2f}  
Forecast (15d): {future_price:.2f}
"""
)

# -------- Signal History --------

st.subheader("📜 Signal History")
history_df = load_signal_history(symbol)

if history_df.empty:
    st.info("No signals saved yet.")
else:
    st.dataframe(history_df, use_container_width=True)
