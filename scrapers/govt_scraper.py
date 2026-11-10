"""
Scraper A: Government / PSU / apprenticeship openings for FRESHERS in India,
via the Adzuna Jobs API.

Honest note: Adzuna is a private job board, so it carries only a few real
government postings. A job is labelled "Govt" ONLY if the company/title
matches a known government body or PSU (see GOVT_PATTERN in base_scraper.py);
everything else this search finds is labelled "Private". Previously every
result from this scraper was labelled Govt, which was wrong.

For full government coverage, add a dedicated source later (see README,
"Next steps").
"""
import os
import logging
from scrapers.base_scraper import BaseScraper

logger = logging.getLogger(__name__)

GOVT_TERMS = (
    "government govt PSU apprentice apprenticeship NATS ISRO DRDO BEL BHEL CDAC NIC NIELIT "
    "ONGC NTPC ECIL railway"
)
# keep the search to tech roles; the fresher filter does the rest
TECH_TERMS = "computer software IT cyber data engineer"


class GovtScraper(BaseScraper):
    source_name = "GovtScraper"

    def fetch_live(self) -> list[dict]:
        raw = self.adzuna_search("in", {
            "what_or": GOVT_TERMS,
            "what_exclude": "telecaller bpo guard driver nurse",
            "max_days_old": int((os.getenv("MAX_DAYS_OLD_GOVT") or "7")),
        }, pages=1)
        jobs = [self.from_adzuna(j, "India", "Private") for j in raw]
        # Only keep tech-flavoured results from this broad search; fresher filter runs later
        text_ok = [j for j in jobs if any(t.lower() in f"{j['title']} {j['description']}".lower()
                                          for t in TECH_TERMS.split())]
        govt = sum(1 for j in text_ok if j["category"] == "Govt")
        logger.info("[%s] %d raw, %d tech-related, %d recognised as Govt/PSU.",
                    self.source_name, len(jobs), len(text_ok), govt)
        return text_ok

    def mock_data(self) -> list[dict]:
        return [
            {
                "job_key": "mock:g1", "title": "Cyber Security Apprentice",
                "company": "Bharat Electronics Limited (BEL)", "category": "Govt",
                "location": "Bengaluru, Karnataka", "country": "India", "posted_date": "2026-11-08",
                "description": "Apprenticeship under NATS. B.Tech/B.E CSE/IT/Cyber Security, 2025 & 2026 pass outs. Min 60% aggregate.",
                "deadline": "2026-11-30", "sector": "Defence / Electronics",
                "apply_url": "https://example.com/mock/bel-cyber-apprentice",
            },
            {
                "job_key": "mock:g2", "title": "Project Engineer (Software)", "company": "C-DAC",
                "category": "Govt", "location": "Pune", "country": "India", "posted_date": "2026-11-08",
                "description": "Minimum 2 years of experience in software development. B.E/B.Tech CSE.",
                "deadline": "2026-11-25", "sector": "R&D",
                "apply_url": "https://example.com/mock/cdac-project-engineer",
            },
        ]
