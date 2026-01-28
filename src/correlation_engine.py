import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

# IMPORTANT:
# Yeh ab src folder ke andar waali trendmind.db use karega:
# /Users/nitinsoni/Documents/trendmind/src/trendmind.db
DB_PATH = Path(__file__).resolve().parent / "trendmind.db"


def load_data():
    """SQLite se stocks aur daily_sentiment tables load karega."""
    conn = sqlite3.connect(DB_PATH)

    # stocks table
    stocks = pd.read_sql(
        """
        SELECT symbol, date, close
        FROM stocks
        """,
        conn,
    )

    # daily_sentiment table
    sentiment = pd.read_sql(
        """
        SELECT symbol, date, avg_sentiment
        FROM daily_sentiment
        """,
        conn,
    )

    conn.close()

    # dates ko normalize karo (YYYY-MM-DD) & types
    stocks["date"] = pd.to_datetime(stocks["date"]).dt.date
    sentiment["date"] = pd.to_datetime(sentiment["date"]).dt.date

    stocks["close"] = stocks["close"].astype(float)
    sentiment["avg_sentiment"] = sentiment["avg_sentiment"].astype(float)

    return stocks, sentiment


def prepare_returns(stocks: pd.DataFrame) -> pd.DataFrame:
    """
    Har symbol ke liye:
      - same-day return (return_1d)
      - next-day return (return_next_1d)
    compute karega.
    """
    df = stocks.copy()
    df = df.sort_values(["symbol", "date"])

    # group by symbol and compute returns
    # aaj vs kal ka % change
    df["return_1d"] = df.groupby("symbol")["close"].pct_change()

    # next-day return: kal ka return, aaj ke row ke saath align
    df["return_next_1d"] = df.groupby("symbol")["close"].pct_change().shift(-1)

    return df


def merge_price_sentiment(stocks_ret: pd.DataFrame, sent: pd.DataFrame) -> pd.DataFrame:
    """
    Stocks + sentiment ko symbol + date par merge karega.
    """
    merged = pd.merge(
        stocks_ret,
        sent,
        on=["symbol", "date"],
        how="inner",
        suffixes=("_price", "_sent"),
    )

    # sirf woh rows jahan sab values present hain
    merged = merged.dropna(subset=["avg_sentiment", "return_1d", "return_next_1d"])

    return merged


def compute_correlations(merged: pd.DataFrame) -> pd.DataFrame:
    """
    Har symbol ke liye:
      - sentiment vs same-day return
      - sentiment vs next-day return
    ka Pearson correlation compute karta hai.
    """

    def corr_for_group(g: pd.DataFrame) -> pd.Series:
        if len(g) < 3:
            # bahut kam rows, correlation meaningless
            return pd.Series(
                {
                    "rows": len(g),
                    "corr_sent_vs_return": np.nan,
                    "corr_sent_vs_next_return": np.nan,
                }
            )

        return pd.Series(
            {
                "rows": len(g),
                "corr_sent_vs_return": g["avg_sentiment"].corr(g["return_1d"]),
                "corr_sent_vs_next_return": g["avg_sentiment"].corr(
                    g["return_next_1d"]
                ),
            }
        )

    summary = merged.groupby("symbol").apply(corr_for_group).reset_index()
    return summary


def print_insights(summary: pd.DataFrame):
    """
    Correlation summary ko human-readable form me print karega.
    """
    if summary.empty:
        print("⚠️ No correlation data available.")
        return

    print("\n📊 Per-symbol correlation summary (sentiment vs returns):\n")
    print(
        summary.to_string(
            index=False,
            formatters={
                "corr_sent_vs_return": lambda x: f"{x:.3f}" if pd.notna(x) else "NaN",
                "corr_sent_vs_next_return": lambda x: f"{x:.3f}" if pd.notna(x) else "NaN",
            },
        )
    )

    print("\n🧠 Interpretation (rule of thumb):")
    print("  +1.0  → Strong positive relation (sentiment ↑ ⇒ price ↑)")
    print("  0.5+  → Medium positive relation")
    print("  ~0   → No clear relation")
    print("  -0.5 → Medium negative relation")
    print("  -1.0 → Strong opposite relation (sentiment ↑ ⇒ price ↓)")

    # Sort by next-day correlation strength
    ranked = summary.sort_values("corr_sent_vs_next_return", ascending=False)

    print("\n⭐ Stocks where positive sentiment tends to lead to next-day gains:")
    print(
        ranked.head(5)[["symbol", "rows", "corr_sent_vs_next_return"]].to_string(
            index=False,
            formatters={"corr_sent_vs_next_return": lambda x: f"{x:.3f}" if pd.notna(x) else "NaN"},
        )
    )

    print("\n⚠️ Stocks where positive sentiment often precedes next-day drops:")
    print(
        ranked.tail(5)[["symbol", "rows", "corr_sent_vs_next_return"]].to_string(
            index=False,
            formatters={"corr_sent_vs_next_return": lambda x: f"{x:.3f}" if pd.notna(x) else "NaN"},
        )
    )


def plot_symbol_scatter(merged: pd.DataFrame, symbol: str):
    """
    Emotion vs next-day return ka scatter chart ek symbol ke liye show karega.
    """
    data = merged[merged["symbol"] == symbol].copy()
    if data.empty:
        print(f"⚠️ No data found for symbol: {symbol}")
        return

    plt.figure(figsize=(7, 5))
    plt.scatter(data["avg_sentiment"], data["return_next_1d"])
    plt.axhline(0, linestyle="--")
    plt.axvline(0, linestyle="--")
    plt.title(f"{symbol}: sentiment vs next-day return")
    plt.xlabel("avg_sentiment (today)")
    plt.ylabel("next-day return")
    plt.grid(True)
    plt.tight_layout()
    plt.show()


def main():
    print("📥 Loading data from SQLite...")
    print(f"Using DB: {DB_PATH}")
    stocks, sent = load_data()

    if stocks.empty:
        print("⚠️ No rows in stocks table.")
        return
    if sent.empty:
        print("⚠️ No rows in daily_sentiment table.")
        return

    print(f"✅ Loaded {len(stocks)} stock rows & {len(sent)} sentiment rows.")

    print("📈 Computing daily returns...")
    stocks_ret = prepare_returns(stocks)

    print("🔗 Merging price and sentiment data...")
    merged = merge_price_sentiment(stocks_ret, sent)
    print(f"✅ Merged data rows: {len(merged)}")

    if merged.empty:
        print("⚠️ No overlapping dates between stocks and sentiment.")
        return

    print("📊 Computing correlations...")
    summary = compute_correlations(merged)
    print_insights(summary)

    # Optional: ek symbol ka scatter plot dikhana
    # jiska next-day correlation sabse strong hai
    valid = summary.dropna(subset=["corr_sent_vs_next_return"])
    if not valid.empty:
        example_symbol = valid.sort_values(
            "corr_sent_vs_next_return", ascending=False
        )["symbol"].iloc[0]
        print(f"\n📈 Plotting scatter for symbol: {example_symbol}")
        plot_symbol_scatter(merged, example_symbol)
    else:
        print("\n⚠️ No valid symbols for plotting (all correlations NaN).")


if __name__ == "__main__":
    main()
