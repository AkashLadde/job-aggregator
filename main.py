"""
Entry point: Scrape -> Fresher filter -> Save to DB (dedupe) -> Classify
-> Build 2 PDFs -> Email.

Usage:
  python main.py                       # live run (needs ADZUNA + GMAIL secrets)
  python main.py --mock --no-notify    # offline test with sample data, no email
  python main.py --mock --preview      # also writes email_preview.html to open in a browser
"""
import os
import sys
import logging
import argparse

from dotenv import load_dotenv
load_dotenv()

from database.db import init_db, bulk_save_new_jobs
from scrapers.govt_scraper import GovtScraper
from scrapers.private_scraper import PrivateScraper
from scrapers.jsearch_scraper import JSearchScraper
from scrapers.jooble_scraper import JoobleScraper
from scrapers.company_boards_scraper import CompanyBoardsScraper
from scrapers.govt_rss_scraper import GovtRssScraper
from scrapers.job_classifier import is_cyber_security, CSE_SUB, GOVT_SUB
from pdf.report_generator import generate_pdf_report, sort_jobs
from notifications.email_sender import send_email_with_pdfs, build_html

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("main")

CYBER_PDF_PATH = "cybersecurity_digest.pdf"
GENERAL_PDF_PATH = "general_cse_digest.pdf"


# Order matters for dedupe: when the same job comes from two sources, the first
# one wins. Company boards (official links) go first, aggregators last.
SCRAPERS = [
    CompanyBoardsScraper,   # official company career pages (Lever/Greenhouse) - no key
    GovtRssScraper,         # Govt/PSU notifications (RSS) - no key
    GovtScraper,            # Adzuna, India public-sector search
    PrivateScraper,         # Adzuna, private sector
    JSearchScraper,         # Google for Jobs: LinkedIn, Naukri, Indeed ... (free quota)
    JoobleScraper,          # Jooble aggregator (500-request lifetime key)
]


def run_scrapers(use_mock: bool) -> list[dict]:
    all_jobs, summary = [], []
    for cls in SCRAPERS:
        scraper = cls(use_mock=use_mock)
        try:
            jobs = scraper.run()
            all_jobs.extend(jobs)
            summary.append(f"{scraper.source_name}={len(jobs)}")
        except Exception as e:
            logger.error("%s failed entirely: %s", scraper.source_name, e)
            summary.append(f"{scraper.source_name}=ERROR")
    logger.info("Fresher jobs per source: %s", ", ".join(summary))
    return all_jobs


def main():
    parser = argparse.ArgumentParser(description="Fresher Job & Internship Aggregator")
    parser.add_argument("--mock", action="store_true", help="Use sample data, skip live API calls")
    parser.add_argument("--no-notify", action="store_true", help="Skip email sending")
    parser.add_argument("--preview", action="store_true", help="Write email_preview.html (no email sent)")
    args = parser.parse_args()

    use_mock = args.mock or (os.getenv("FORCE_MOCK") or "false").lower() == "true"
    if use_mock and not (args.no_notify or args.preview):
        logger.warning("Mock mode: emails will contain SAMPLE jobs, not real ones.")

    logger.info("=== Fresher Job Aggregator Pipeline Started ===")
    init_db()

    fresher_jobs = run_scrapers(use_mock=use_mock)
    logger.info("Fresher jobs after filter (pre-dedup): %d", len(fresher_jobs))

    new_jobs = bulk_save_new_jobs(fresher_jobs)
    logger.info("New jobs after dedup: %d", len(new_jobs))

    cyber_jobs = sort_jobs([j for j in new_jobs if is_cyber_security(j)])
    general_jobs = sort_jobs([j for j in new_jobs if not is_cyber_security(j)])
    logger.info("Streams: %d Cyber Security, %d CSE & Allied.", len(cyber_jobs), len(general_jobs))

    generate_pdf_report(cyber_jobs, CYBER_PDF_PATH,
                        report_title="Cyber Security — Fresher Engineering Internships & Jobs")
    generate_pdf_report(general_jobs, GENERAL_PDF_PATH,
                        report_title="CSE & Allied (CSE, ISE, IT, AI/ML, Data Science) — Fresher Engineering Jobs")

    # Email: Cyber Security first, then one section per CSE & Allied sub-stream
    sections = [("Cyber Security", cyber_jobs)]
    for sub in [name for name, _ in CSE_SUB] + ["Software Development", GOVT_SUB]:
        sections.append((f"CSE & Allied · {sub}", [j for j in general_jobs if j.get("sub_stream") == sub]))
    sections = [(t, js) for t, js in sections if js]

    if args.preview:
        with open("email_preview.html", "w", encoding="utf-8") as f:
            f.write(build_html(sections))
        logger.info("Wrote email_preview.html - open it in a browser.")

    if args.no_notify or args.preview:
        logger.info("Email skipped (--no-notify / --preview).")
    elif not new_jobs:
        logger.info("No new fresher jobs this run — skipping email to avoid spam.")
    else:
        pdfs = [p for p, js in ((CYBER_PDF_PATH, cyber_jobs), (GENERAL_PDF_PATH, general_jobs)) if js]
        if not send_email_with_pdfs(pdfs, total_job_count=len(new_jobs), sections=sections):
            logger.warning("Email delivery failed — check logs above.")

    logger.info("=== Pipeline Finished ===")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logger.exception("Fatal error in pipeline: %s", e)
        sys.exit(1)
