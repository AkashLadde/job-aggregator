"""
Entry point: Scrape -> Save to DB (dedupe) -> Classify -> Build 2 PDFs -> Email.
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
from scrapers.job_classifier import is_cyber_security
from pdf.report_generator import generate_pdf_report
from notifications.email_sender import send_email_with_pdfs

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("main")

CYBER_PDF_PATH = "cybersecurity_digest.pdf"
GENERAL_PDF_PATH = "general_cse_digest.pdf"


def run_scrapers(use_mock: bool) -> list[dict]:
    scrapers = [GovtScraper(use_mock=use_mock), PrivateScraper(use_mock=use_mock)]
    all_jobs = []
    for scraper in scrapers:
        try:
            jobs = scraper.run()
            logger.info("%s collected %d listings.", scraper.source_name, len(jobs))
            all_jobs.extend(jobs)
        except Exception as e:
            logger.error("%s failed entirely: %s", scraper.source_name, e)
    return all_jobs


def main():
    parser = argparse.ArgumentParser(description="Engineering Job & Internship Aggregator")
    parser.add_argument("--mock", action="store_true", help="Force mock data, skip live scraping")
    parser.add_argument("--no-notify", action="store_true", help="Skip email sending")
    args = parser.parse_args()

    use_mock = args.mock or os.getenv("FORCE_MOCK", "false").lower() == "true"

    logger.info("=== Job Aggregator Pipeline Started ===")
    init_db()

    scraped_jobs = run_scrapers(use_mock=use_mock)
    logger.info("Total scraped (pre-dedup): %d", len(scraped_jobs))

    new_jobs = bulk_save_new_jobs(scraped_jobs)
    logger.info("New jobs after dedup: %d", len(new_jobs))

    cyber_jobs = [j for j in new_jobs if is_cyber_security(j)]
    general_jobs = [j for j in new_jobs if not is_cyber_security(j)]
    logger.info("Classified: %d Cyber Security, %d General CSE.", len(cyber_jobs), len(general_jobs))

    generate_pdf_report(cyber_jobs, CYBER_PDF_PATH, report_title="Cyber Security — Daily Digest")
    generate_pdf_report(general_jobs, GENERAL_PDF_PATH, report_title="General CSE / Allied Branch — Daily Digest")

    if args.no_notify:
        logger.info("--no-notify set, skipping email.")
    elif len(new_jobs) == 0:
        logger.info("No new jobs found this run — skipping email to avoid spam.")
    else:
        email_ok = send_email_with_pdfs([CYBER_PDF_PATH, GENERAL_PDF_PATH], total_job_count=len(new_jobs))
        if not email_ok:
            logger.warning("Email delivery failed — check logs above.")

    logger.info("=== Job Aggregator Pipeline Finished ===")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logger.exception("Fatal error in pipeline: %s", e)
        sys.exit(1)
