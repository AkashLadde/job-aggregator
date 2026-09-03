"""
Scraper B: Private-sector CSE & allied-branch (Cyber Security, IS, Data
Science, AI/ML, Software) internships & jobs for FRESHERS, via the Adzuna
Jobs API, searched across India and major global tech/cyber hiring hubs.
"""
import os
import logging
import requests
from scrapers.base_scraper import BaseScraper

logger = logging.getLogger(__name__)

ADZUNA_APP_ID = os.getenv("ADZUNA_APP_ID")
ADZUNA_APP_KEY = os.getenv("ADZUNA_APP_KEY")

COUNTRIES = {
    "in": "India",
    "gb": "United Kingdom",
    "us": "United States",
    "ae": "United Arab Emirates",
    "sg": "Singapore",
}

SEARCH_TERMS = (
    "fresher entry level graduate trainee intern cyber security cybersecurity "
    "SOC analyst penetration tester information security network security "
    "data science artificial intelligence machine learning software developer engineer"
)


def _format_eligibility(description: str) -> str:
    """Turn a raw job description blob into bullet-pointed eligibility text."""
    if not description:
        return "• See posting for full eligibility details"
    snippet = description[:400]
    # split on sentence-ish boundaries to form pseudo-bullets
    parts = [p.strip() for p in snippet.replace("\n", " ").split(". ") if p.strip()]
    bullets = parts[:4] if parts else [snippet]
    return "".join(f"• {b.rstrip('.')}.<br/>" for b in bullets)


class PrivateScraper(BaseScraper):
    source_name = "PrivateScraper"

    def fetch_live(self) -> list[dict]:
        if not ADZUNA_APP_ID or not ADZUNA_APP_KEY:
            logger.error("Adzuna credentials missing, cannot fetch live private jobs.")
            return []

        results = []
        for country_code, country_name in COUNTRIES.items():
            url = f"https://api.adzuna.com/v1/api/jobs/{country_code}/search/1"
            params = {
                "app_id": ADZUNA_APP_ID,
                "app_key": ADZUNA_APP_KEY,
                "results_per_page": 20,
                "what_or": SEARCH_TERMS,
                "max_days_old": 1,
                "sort_by": "date",
                "content-type": "application/json",
            }
            try:
                resp = requests.get(url, params=params, timeout=15)
                resp.raise_for_status()
                data = resp.json()
            except Exception as e:
                logger.warning("Adzuna fetch failed for country=%s: %s", country_code, e)
                continue

            for job in data.get("results", []):
                description = job.get("description", "")
                results.append({
                    "title": job.get("title", "Untitled Role"),
                    "company": job.get("company", {}).get("display_name", "Private Company"),
                    "category": "Private",
                    "eligibility": "[Freshers] " + _format_eligibility(description),
                    "location": job.get("location", {}).get("display_name", country_name),
                    "country": country_name,
                    "posted_date": (job.get("created", "") or "")[:10],  # YYYY-MM-DD
                    "deadline": "See posting",
                    "sector": job.get("category", {}).get("label", "Engineering"),
                    "apply_url": job.get("redirect_url", ""),
                })
        return results

    def mock_data(self) -> list[dict]:
        return [
            {
                "title": "AI/ML Engineering Intern",
                "company": "Razorpay",
                "category": "Private",
                "eligibility": "[Freshers] • B.Tech/B.E CSE/AI/DS, 2026 batch.<br/>• Strong in Python.<br/>• ML fundamentals required.<br/>",
                "location": "Bengaluru",
                "country": "India",
                "posted_date": "2026-08-30",
                "deadline": "See posting",
                "sector": "Fintech",
                "apply_url": "https://unstop.com/internships/razorpay-ai-ml-2026",
            },
            {
                "title": "SOC Analyst - Entry Level",
                "company": "Example Security Ltd",
                "category": "Private",
                "eligibility": "[Freshers] • B.Tech CSE/Cyber Security, 2026 pass out.<br/>• CompTIA Security+ preferred.<br/>",
                "location": "London",
                "country": "United Kingdom",
                "posted_date": "2026-08-29",
                "deadline": "See posting",
                "sector": "Cyber Security",
                "apply_url": "https://example.com/soc-analyst-2026",
            },
        ]
