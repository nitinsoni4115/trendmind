import sqlite3
from datetime import datetime
from collections import defaultdict
from pathlib import Path

from transformers import (
    AutoTokenizer,
    AutoModelForSequenceClassification,
    pipeline
)

# ---------------- CONFIG ----------------
DB_PATH = Path(__file__).resolve().parent / "trendmind.db"
MODEL_NAME = "ProsusAI/finbert"


# ---------------- DB ----------------

def get_connection():
    return sqlite3.connect(DB_PATH)


def load_articles():
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
    for r in rows:
        article_id, ticker, title, desc, pub, collected = r
        if not title and not desc:
            continue

        date_src = pub or collected
        if not date_src:
            continue

        text = ". ".join([t for t in [title, desc] if t])
        date_key = str(date_src)[:10]

        articles.append({
            "id": article_id,
            "ticker": ticker,
            "date": date_key,
            "text": text
        })

    return articles


# ---------------- FINBERT ----------------

def build_finbert():
    print("🔧 Loading FinBERT (SAFE safetensors mode)...")

    tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)

    model = AutoModelForSequenceClassification.from_pretrained(
        MODEL_NAME,
        use_safetensors=True,   # 🔥 IMPORTANT FIX
        torch_dtype=None        # CPU safe
    )

    analyzer = pipeline(
        "sentiment-analysis",
        model=model,
        tokenizer=tokenizer,
        truncation=True
    )

    print("✅ FinBERT ready.")
    return analyzer


# ---------------- SENTIMENT ----------------

def score_articles(articles, analyzer):
    texts = [a["text"] for a in articles]
    print(f"🧠 Running FinBERT on {len(texts)} articles...")

    results = analyzer(texts, batch_size=8)

    scored = []
    for art, res in zip(articles, results):
        label = res["label"].lower()
        score = float(res["score"])

        if label == "negative":
            score = -score
        elif label == "neutral":
            score = 0.0

        art2 = art.copy()
        art2["score"] = score
        scored.append(art2)

    return scored


def aggregate_daily(scored):
    bucket = defaultdict(list)

    for a in scored:
        bucket[(a["ticker"], a["date"])].append(a["score"])

    records = []
    for (sym, date), scores in bucket.items():
        avg = sum(scores) / len(scores)

        label = (
            "positive" if avg > 0.15 else
            "negative" if avg < -0.15 else
            "neutral"
        )

        records.append({
            "symbol": sym,
            "date": date,
            "avg_sentiment": avg,
            "sentiment_label": label,
            "article_count": len(scores)
        })

    return records


def save_daily(records):
    if not records:
        print("⚠️ Nothing to save")
        return

    conn = get_connection()
    cur = conn.cursor()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    for r in records:
        cur.execute("""
            INSERT OR REPLACE INTO daily_sentiment
            (symbol, date, avg_sentiment, sentiment_label, article_count, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            r["symbol"], r["date"], r["avg_sentiment"],
            r["sentiment_label"], r["article_count"], now
        ))

    conn.commit()
    conn.close()
    print(f"✅ Saved {len(records)} FinBERT sentiment rows")


# ---------------- MAIN ----------------

def main():
    articles = load_articles()
    print(f"📄 Loaded {len(articles)} articles.")

    if not articles:
        return

    analyzer = build_finbert()
    scored = score_articles(articles, analyzer)
    daily = aggregate_daily(scored)
    save_daily(daily)


if __name__ == "__main__":
    main()
