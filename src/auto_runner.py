import subprocess
from apscheduler.schedulers.blocking import BlockingScheduler
from datetime import datetime
import sys
from pathlib import Path
import traceback

# ================= CONFIG =================

BASE_DIR = Path(__file__).resolve().parent
PYTHON = sys.executable  # current venv python

LOG_DIR = BASE_DIR / "logs"
LOG_DIR.mkdir(exist_ok=True)

TIMEZONE = "Asia/Kolkata"

# Scripts execution order (VERY IMPORTANT)
PIPELINE = [
    "fetch_stocks.py",
    "fetch_news.py",
    "sentiment_finbert.py",
    "generate_signals.py"   # 👈 ADD THIS
]


# ================= UTIL =================

def log(msg: str):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    full_msg = f"[{timestamp}] {msg}"
    print(full_msg)

    with open(LOG_DIR / "auto_runner.log", "a") as f:
        f.write(full_msg + "\n")


def run_script(script_name: str) -> bool:
    log(f"🚀 Running {script_name}")

    try:
        subprocess.run(
            [PYTHON, BASE_DIR / script_name],
            check=True
        )
        log(f"✅ {script_name} completed successfully")
        return True

    except subprocess.CalledProcessError as e:
        log(f"❌ ERROR in {script_name}")
        log(str(e))
        log(traceback.format_exc())
        return False


# ================= MAIN JOB =================

def daily_job():
    log("=" * 40)
    log("🤖 TrendMind Daily AI Job START")
    log("=" * 40)

    for script in PIPELINE:
        success = run_script(script)

        if not success:
            log("🛑 Pipeline stopped due to error.")
            break

    log("=" * 40)
    log("✅ TrendMind Daily AI Job DONE")
    log("=" * 40)


# ================= ENTRY =================

if __name__ == "__main__":
    scheduler = BlockingScheduler(timezone=TIMEZONE)

    # 🕘 Daily run at 9:00 AM IST
    scheduler.add_job(
        daily_job,
        trigger="cron",
        hour=10,
        minute=22,
        id="trendmind_daily_job",
        replace_existing=True
    )

    log("🕘 TrendMind automation started (daily 9:00 AM IST)")
    scheduler.start()
