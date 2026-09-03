"""
Lightweight SQLite database helper for the job aggregator.

Provides:
- init_db(): create the SQLite DB file with a jobs table (if it doesn't exist)
- bulk_save_new_jobs(jobs): insert only jobs whose apply_url hasn't been seen
  before, and return the full dicts of the ones that were newly inserted.

IMPORTANT: job dicts throughout this project use the key "apply_url" (not
"url") for the application link — this dedupe logic must match that exact
key name, or every job silently gets skipped.
"""
import sqlite3
import datetime
from typing import List, Dict

DB_PATH = "job_aggregator.db"

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


def init_db() -> None:
    """Create the database file and jobs table if they don't exist."""
    conn = sqlite3.connect(DB_PATH)
    try:
        cur = conn.cursor()
        cur.execute(CREATE_TABLE_SQL)
        conn.commit()
    finally:
        conn.close()


def bulk_save_new_jobs(jobs: List[Dict]) -> List[Dict]:
    """
    Insert jobs which are not already present (dedupe by apply_url).
    Returns the full dicts of jobs that were newly inserted, so the PDF
    generator has every field (title, company, eligibility, location,
    deadline, sector, apply_url) available.
    """
    if not jobs:
        return []

    conn = sqlite3.connect(DB_PATH)
    inserted = []
    now = datetime.datetime.utcnow().isoformat() + "Z"
    try:
        cur = conn.cursor()
        for job in jobs:
            apply_url = job.get("apply_url")
            if not apply_url:
                # can't dedupe or apply without a URL, skip
                continue

            cur.execute("SELECT 1 FROM jobs WHERE apply_url = ?", (apply_url,))
            if cur.fetchone():
                continue

            cur.execute(
                """INSERT INTO jobs
                   (apply_url, title, company, category, eligibility, location, deadline, sector, saved_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    apply_url,
                    job.get("title", "Untitled Role"),
                    job.get("company", "Unknown"),
                    job.get("category", "Private"),
                    job.get("eligibility", "Not specified"),
                    job.get("location", "India"),
                    job.get("deadline", "Not specified"),
                    job.get("sector", "Engineering"),
                    now,
                ),
            )
            conn.commit()
            inserted.append(job)
    finally:
        conn.close()

    return inserted
