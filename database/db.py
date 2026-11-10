"""
Lightweight SQLite database helper for the job aggregator.

- init_db(): create the jobs table, and add any new columns to an existing
  job_aggregator.db (safe to run on your old database - nothing is lost).
- bulk_save_new_jobs(jobs): insert only jobs not seen before and return them.

A job counts as "already seen" if ANY of these match an earlier row:
  1. same job_key   (Adzuna's own job id - stable even when the link changes)
  2. same apply_url
  3. same title + company within the last DEDUPE_DAYS days
     (one opening is often posted separately for several cities)
"""
import os
import re
import sqlite3
import datetime
from typing import List, Dict

DEDUPE_DAYS = int((os.getenv("DEDUPE_DAYS") or "21"))


def _db_path() -> str:
    url = (os.getenv("DATABASE_URL") or "").strip()
    if url.startswith("sqlite:///"):
        return url[len("sqlite:///"):]
    return "job_aggregator.db"


DB_PATH = _db_path()

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    apply_url TEXT UNIQUE,
    title TEXT,
    company TEXT,
    category TEXT,
    eligibility TEXT,
    location TEXT,
    deadline TEXT,
    sector TEXT,
    saved_at TEXT
);
"""

# columns added after the first version -> added automatically to old DBs
NEW_COLUMNS = {
    "job_key": "TEXT",
    "dedupe_key": "TEXT",
    "country": "TEXT",
    "posted_date": "TEXT",
    "job_type": "TEXT",
    "fresher_reason": "TEXT",
    "source": "TEXT",
}

# Tracks calls to quota-limited APIs (JSearch monthly, Jooble lifetime) so the
# pipeline never goes over a free plan. Stored in the same DB file, which the
# GitHub workflow commits back after every run.
CREATE_USAGE_SQL = """
CREATE TABLE IF NOT EXISTS api_usage (
    api TEXT,
    period TEXT,
    calls INTEGER DEFAULT 0,
    PRIMARY KEY (api, period)
);
"""


def _dedupe_key(title: str, company: str) -> str:
    """'Software Engineer Intern - Bangalore' @ 'Acme Pvt. Ltd.' -> 'software engineer intern|acme'"""
    t = re.sub(r"\s*[-|,(].*$", "", (title or "").lower())          # drop ' - Bangalore', '(Remote)'
    t = re.sub(r"[^a-z0-9 ]+", " ", t)
    c = re.sub(r"\b(pvt|private|ltd|limited|llp|inc|technologies|technology|solutions|india)\b", "",
               (company or "").lower())
    c = re.sub(r"[^a-z0-9]+", "", c)
    return f"{' '.join(t.split())}|{c}"


def init_db() -> None:
    conn = sqlite3.connect(DB_PATH)
    try:
        cur = conn.cursor()
        cur.execute(CREATE_TABLE_SQL)
        cur.execute(CREATE_USAGE_SQL)
        existing = {row[1] for row in cur.execute("PRAGMA table_info(jobs)")}
        for col, col_type in NEW_COLUMNS.items():
            if col not in existing:
                cur.execute(f"ALTER TABLE jobs ADD COLUMN {col} {col_type}")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_jobs_job_key ON jobs(job_key)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_jobs_dedupe ON jobs(dedupe_key, saved_at)")
        conn.commit()
    finally:
        conn.close()


def bulk_save_new_jobs(jobs: List[Dict]) -> List[Dict]:
    if not jobs:
        return []

    conn = sqlite3.connect(DB_PATH)
    inserted = []
    now = datetime.datetime.now(datetime.timezone.utc)
    cutoff = (now - datetime.timedelta(days=DEDUPE_DAYS)).isoformat()
    try:
        cur = conn.cursor()
        for job in jobs:
            apply_url = job.get("apply_url")
            if not apply_url:
                continue
            job_key = job.get("job_key") or None
            dkey = _dedupe_key(job.get("title", ""), job.get("company", ""))

            cur.execute(
                """SELECT 1 FROM jobs
                   WHERE apply_url = ?
                      OR (job_key IS NOT NULL AND job_key = ?)
                      OR (dedupe_key = ? AND saved_at >= ?)
                   LIMIT 1""",
                (apply_url, job_key, dkey, cutoff),
            )
            if cur.fetchone():
                continue

            cur.execute(
                """INSERT INTO jobs
                   (apply_url, title, company, category, eligibility, location, deadline, sector, saved_at,
                    job_key, dedupe_key, country, posted_date, job_type, fresher_reason, source)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    apply_url,
                    job.get("title", "Untitled Role"),
                    job.get("company", "Unknown"),
                    job.get("category", "Private"),
                    job.get("eligibility", "Not specified"),
                    job.get("location", "India"),
                    job.get("deadline", "Not specified"),
                    job.get("sector", "Engineering"),
                    now.isoformat(),
                    job_key,
                    dkey,
                    job.get("country"),
                    job.get("posted_date"),
                    job.get("job_type"),
                    job.get("fresher_reason"),
                    job.get("source"),
                ),
            )
            conn.commit()
            inserted.append(job)
    finally:
        conn.close()

    return inserted


# ---------------------------------------------------------------- API quota

def api_calls_used(api: str, period: str) -> int:
    init_db()
    conn = sqlite3.connect(DB_PATH)
    try:
        row = conn.execute("SELECT calls FROM api_usage WHERE api = ? AND period = ?", (api, period)).fetchone()
        return row[0] if row else 0
    finally:
        conn.close()


def record_api_calls(api: str, period: str, n: int = 1) -> None:
    init_db()
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute(
            """INSERT INTO api_usage (api, period, calls) VALUES (?, ?, ?)
               ON CONFLICT(api, period) DO UPDATE SET calls = calls + excluded.calls""",
            (api, period, n),
        )
        conn.commit()
    finally:
        conn.close()
