import sqlite3
from datetime import datetime
from collections import defaultdict

from transformers import pipeline

from pathlib import Path
import sqlite3

DB_PATH = Path(__file__).resolve().parent / "trendmind.db"

def get_connection():
    return sqlite3.connect(DB_PATH)



def load_articles():
    """
    Articles table se sentiment ke liye required fields load karega.
    """
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, ticker, title, description, published_at, collected_at
        FROM articles
        WHERE ticker IS NOT NULL
    """)

    rows = cursor.fetchall()
    conn.close()

    articles = []
    for row in rows:
        article_id, ticker, title, description, published_at, collected_at = row

        if not title and not description:
            # bilkul empty article skip
            continue

        # date_key banayenge
        # published_at: e.g. "2025-11-22T10:00:00Z"
        date_source = published_at or collected_at
        if not date_source:
            # date hi nahi mila to skip
            continue

        date_key = str(date_source)[:10]  # "YYYY-MM-DD"

        text_parts = []
        if title:
            text_parts.append(title)
        if description:
            text_parts.append(description)

        text = ". ".join(text_parts)

        articles.append({
            "id": article_id,
            "ticker": ticker,
            "date": date_key,
            "text": text,
        })

    return articles


def build_sentiment_analyzer():
    """
    HuggingFace transformers sentiment pipeline use karega.
    Model: distilbert-base-uncased-finetuned-sst-2-english
    """
    print("🔧 Loading sentiment model (first time thoda time lag sakta hai)...")
    analyzer = pipeline(
        "sentiment-analysis",
        model="distilbert-base-uncased-finetuned-sst-2-english"
    )
    print("✅ Sentiment model ready.")
    return analyzer


def compute_article_scores(articles, analyzer):
    """
    Har article ke text ka sentiment score nikalta hai.
    Returns: list with added 'score' field
    """
    texts = [a["text"] for a in articles]

    print(f"🧠 Running sentiment on {len(texts)} articles...")
    results = analyzer(texts, batch_size=16, truncation=True)

    scored_articles = []
    for article, res in zip(articles, results):
        label = res["label"]  # POSITIVE / NEGATIVE
        score = float(res["score"])

        if label.upper().startswith("NEG"):
            numeric = -score
        else:
            numeric = +score

        article_with_score = article.copy()
        article_with_score["score"] = numeric
        scored_articles.append(article_with_score)

    return scored_articles


def aggregate_daily_sentiment(scored_articles):
    """
    Articles → daily sentiment aggregate per (symbol, date).
    Returns: list of dicts {symbol, date, avg_sentiment, sentiment_label, article_count}
    """
    grouped_scores = defaultdict(list)

    for a in scored_articles:
        key = (a["ticker"], a["date"])
        grouped_scores[key].append(a["score"])

    daily_records = []

    for (symbol, date), scores in grouped_scores.items():
        if not scores:
            continue

        avg = sum(scores) / len(scores)

        # label based on threshold
        if avg > 0.2:
            label = "positive"
        elif avg < -0.2:
            label = "negative"
        else:
            label = "neutral"

        daily_records.append({
            "symbol": symbol,
            "date": date,
            "avg_sentiment": avg,
            "sentiment_label": label,
            "article_count": len(scores),
        })

    return daily_records


def save_daily_sentiment(records):
    """
    daily_sentiment table me records INSERT OR REPLACE karega.
    """
    if not records:
        print("⚠️ No daily sentiment records to save.")
        return

    conn = get_connection()
    cursor = conn.cursor()

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    for r in records:
        cursor.execute("""
            INSERT OR REPLACE INTO daily_sentiment
            (symbol, date, avg_sentiment, sentiment_label, article_count, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            r["symbol"],
            r["date"],
            r["avg_sentiment"],
            r["sentiment_label"],
            r["article_count"],
            now
        ))

    conn.commit()
    conn.close()

    print(f"✅ Saved {len(records)} daily sentiment rows into daily_sentiment table.")


def main():
    articles = load_articles()
    if not articles:
        print("⚠️ No articles found in DB (ticker not NULL). Run fetch_news.py first.")
        return

    print(f"📄 Loaded {len(articles)} articles from DB.")

    analyzer = build_sentiment_analyzer()
    scored_articles = compute_article_scores(articles, analyzer)

    daily_records = aggregate_daily_sentiment(scored_articles)

    print(f"📅 Aggregated into {len(daily_records)} (symbol, date) records.")
    save_daily_sentiment(daily_records)


if __name__ == "__main__":
    main()
