"""
Scraper B: Private-sector CSE & allied-branch (Software, Cyber Security,
Data Science, AI/ML, Cloud) internships & jobs for FRESHERS via the Adzuna
Jobs API.

Two searches per country:
  1. "fresher words"  (intern, trainee, fresher, graduate, entry level ...)
  2. "domain words"   (software developer, cyber security, data analyst ...)
Every result then goes through scrapers/fresher_filter.py, which keeps only
real fresher + CSE roles. API cost: 2 calls x countries x pages per run.

Countries: JOB_COUNTRIES (default "in" = India only), e.g. "in,ae,sg".
Codes: in=India gb=UK us=USA ae=UAE sg=Singapore au=Australia ca=Canada de=Germany
"""
import os
import logging
from scrapers.base_scraper import BaseScraper

logger = logging.getLogger(__name__)

COUNTRY_NAMES = {
    "in": "India", "gb": "United Kingdom", "us": "United States", "ae": "United Arab Emirates",
    "sg": "Singapore", "au": "Australia", "ca": "Canada", "de": "Germany", "nl": "Netherlands",
}

FRESHER_TERMS = "intern internship fresher freshers trainee graduate entry-level junior apprentice"
DOMAIN_TERMS = (
    "software developer programmer python java cybersecurity SOC "
    "data analyst data scientist machine learning AI cloud devops tester"
)
# Words that are almost never in a CSE fresher ad - saves API results for useful jobs.
EXCLUDE_TERMS = "telecaller bpo guard driver nurse"


def _countries() -> dict[str, str]:
    raw = (os.getenv("JOB_COUNTRIES") or "in") or "in"
    codes = [c.strip().lower() for c in raw.split(",") if c.strip()]
    return {c: COUNTRY_NAMES.get(c, c.upper()) for c in codes}


class PrivateScraper(BaseScraper):
    source_name = "PrivateScraper"

    def fetch_live(self) -> list[dict]:
        pages_india = int((os.getenv("ADZUNA_PAGES_INDIA") or "2"))
        results = []
        for code, name in _countries().items():
            pages = pages_india if code == "in" else 1
            for terms in (FRESHER_TERMS, DOMAIN_TERMS):
                raw = self.adzuna_search(code, {
                    "what_or": terms,
                    "what_exclude": EXCLUDE_TERMS,
                    "max_days_old": int((os.getenv("MAX_DAYS_OLD") or "2")),
                }, pages=pages)
                results.extend(self.from_adzuna(j, name, "Private") for j in raw)
        return results

    def mock_data(self) -> list[dict]:
        """Sample ads for testing (--mock). Includes jobs the filter must REJECT."""
        return [
            {
                "job_key": "mock:p1", "title": "AI/ML Engineering Intern", "company": "Razorpay",
                "category": "Private", "location": "Bengaluru", "country": "India", "posted_date": "2026-11-09",
                "description": "6-month internship. B.Tech/B.E CSE/AI/DS, 2026 batch. Strong in Python & ML fundamentals.",
                "sector": "Fintech", "apply_url": "https://example.com/mock/razorpay-ai-ml-intern",
            },
            {
                "job_key": "mock:p2", "title": "SOC Analyst - Entry Level", "company": "Example Security Ltd",
                "category": "Private", "location": "Pune", "country": "India", "posted_date": "2026-11-09",
                "description": "Freshers welcome. B.Tech CSE/Cyber Security, 2025 or 2026 pass out. Security+ preferred <optional>.",
                "sector": "Cyber Security", "apply_url": "https://example.com/mock/soc-analyst",
            },
            {
                "job_key": "mock:p3", "title": "Python Developer", "company": "Acme Software",
                "category": "Private", "location": "Hyderabad", "country": "India", "posted_date": "2026-11-09",
                "description": "Experience: 0-1 years. Django, REST APIs, SQL. Freshers can apply.",
                "sector": "IT Jobs", "apply_url": "https://example.com/mock/python-dev",
            },
            # --- these must be filtered out
            {
                "job_key": "mock:p4", "title": "Senior Software Engineer", "company": "BigCorp",
                "category": "Private", "location": "Bengaluru", "country": "India", "posted_date": "2026-11-09",
                "description": "8+ years of experience in Java & microservices.",
                "sector": "IT Jobs", "apply_url": "https://example.com/mock/senior-swe",
            },
            {
                "job_key": "mock:p5", "title": "Software Engineer", "company": "MidCorp",
                "category": "Private", "location": "Chennai", "country": "India", "posted_date": "2026-11-09",
                "description": "Minimum 3 years of experience with React & Node.js.",
                "sector": "IT Jobs", "apply_url": "https://example.com/mock/swe-3yrs",
            },
            {
                "job_key": "mock:p6", "title": "Telesales Executive", "company": "CallHub",
                "category": "Private", "location": "Noida", "country": "India", "posted_date": "2026-11-09",
                "description": "Freshers can apply. Sell software subscriptions over phone.",
                "sector": "Sales", "apply_url": "https://example.com/mock/telesales",
            },
        ]
