import sqlite3
from datetime import datetime
from pathlib import Path

import requests

# Always use the DB inside src folder
DB_PATH = Path(__file__).resolve().parent / "trendmind.db"


def get_connection():
    """SQLite database connection return karega."""
    return sqlite3.connect(DB_PATH)


def save_articles(symbol: str, news_list: list):
    """
    Yahoo Finance search API se aayi news list ko 'articles' table me save karega.

    search API item example:
    {
      "title": "...",
      "summary": "...",
      "publisher": "Motley Fool",
      "link": "https://finance.yahoo.com/...",
      "pubDate": "2025-11-22T10:00:00Z",
      ...
    }
    """
    if not news_list:
        print(f"⚠️ No news to save for {symbol} (empty list)")
        return

    conn = get_connection()
    cursor = conn.cursor()

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    inserted = 0
    skipped_dup = 0
    skipped_no_title = 0

    for item in news_list:
        # --- TITLE (directly on item) ---
        title = item.get("title") or ""
        if not title:
            skipped_no_title += 1
            continue

        # --- DESCRIPTION / SUMMARY ---
        description = (
            item.get("summary")
            or item.get("description")
            or ""
        )

        # --- URL ---
        url = item.get("link") or None

        # --- SOURCE / PROVIDER ---
        source = item.get("publisher") or "Unknown"

        # --- FULL CONTENT ---
        full_content = None  # abhi nahi milta, future ke liye placeholder

        # --- PUBLISHED AT ---
        published_at = item.get("pubDate") or None
        if published_at:
            published_at = str(published_at)

        try:
            cursor.execute(
                """
                INSERT OR IGNORE INTO articles
                (ticker, title, description, content, url, source, published_at, collected_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (symbol, title, description, full_content, url, source, published_at, now),
            )

            if cursor.rowcount == 1:
                inserted += 1
            else:
                skipped_dup += 1

        except sqlite3.Error as e:
            print(f"❌ Error saving article for {symbol}: {e}")

    conn.commit()
    conn.close()

    print(
        f"✅ {symbol}: {inserted} articles saved, "
        f"{skipped_dup} duplicates skipped, {skipped_no_title} skipped (no title)."
    )


def fetch_news_history(symbol: str, pages: int = 5):
    """
    Yahoo Finance search API se multiple pages fetch karega (thodi history).

    pages = 5 → ~100 news per symbol (approx).
    """
    print(f"\n📰 Fetching historical news for {symbol} ...")

    all_news = []

    for page in range(pages):
        print(f"📄 Loading page {page + 1}/{pages} ...")

        url = (
            "https://query2.finance.yahoo.com/v1/finance/search?"
            f"q={symbol}&newsCount=20&start={page * 20}"
        )

        try:
            resp = requests.get(
                url,
                headers={"User-Agent": "Mozilla/5.0"},
                timeout=10,
            )
        except Exception as e:
            print(f"⚠️ Request failed on page {page}: {e}")
            continue

        if resp.status_code != 200:
            print(f"⚠️ HTTP {resp.status_code} on page {page}")
            continue

        try:
            data = resp.json()
        except Exception as e:
            print(f"⚠️ JSON parse error on page {page}: {e}")
            continue

        news_items = data.get("news", [])
        print(f"   ↳ got {len(news_items)} items")
        all_news.extend(news_items)

    print(f"📦 Total collected news items for {symbol}: {len(all_news)}")
    save_articles(symbol, all_news)


if __name__ == "__main__":
    symbols = ["AAPL", "MSFT", "TSLA"]

    for sym in symbols:
        fetch_news_history(sym, pages=5)
