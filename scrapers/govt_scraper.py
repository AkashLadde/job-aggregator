"""
Scraper A: Government / PSU engineering apprenticeships & jobs for FRESHERS
(India-only, since "PSU/Government" is a category specific to India), via
the Adzuna Jobs API, focused on CSE-allied branches.
"""
import os
import logging
import requests
from scrapers.base_scraper import BaseScraper

logger = logging.getLogger(__name__)

ADZUNA_APP_ID = os.getenv("ADZUNA_APP_ID")
ADZUNA_APP_KEY = os.getenv("ADZUNA_APP_KEY")
ADZUNA_URL = "https://api.adzuna.com/v1/api/jobs/in/search/1"

SEARCH_TERMS = (
    "government fresher graduate trainee apprentice cyber security cybersecurity "
    "information security network security data scientist AI ML machine "
    "learning software engineer"
)


def _format_eligibility(description: str) -> str:
    if not description:
        return "• See official posting for full eligibility criteria"
    snippet = description[:400]
    parts = [p.strip() for p in snippet.replace("\n", " ").split(". ") if p.strip()]
    bullets = parts[:4] if parts else [snippet]
    return "".join(f"• {b.rstrip('.')}.<br/>" for b in bullets)


class GovtScraper(BaseScraper):
    source_name = "GovtScraper"

    def fetch_live(self) -> list[dict]:
        if not ADZUNA_APP_ID or not ADZUNA_APP_KEY:
            logger.error("Adzuna credentials missing, cannot fetch live govt jobs.")
            return []

        params = {
            "app_id": ADZUNA_APP_ID,
            "app_key": ADZUNA_APP_KEY,
            "results_per_page": 40,
            "what_or": SEARCH_TERMS,
            "max_days_old": 1,
            "sort_by": "date",
            "content-type": "application/json",
        }
        resp = requests.get(ADZUNA_URL, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()

        results = []
        for job in data.get("results", []):
            description = job.get("description", "")
            results.append({
                "title": job.get("title", "Untitled Role"),
                "company": job.get("company", {}).get("display_name", "Govt/PSU"),
                "category": "Govt",
                "eligibility": "[Freshers] " + _format_eligibility(description),
                "location": job.get("location", {}).get("display_name", "India"),
                "country": "India",
                "posted_date": (job.get("created", "") or "")[:10],
                "deadline": "See posting",
                "sector": job.get("category", {}).get("label", "Engineering"),
                "apply_url": job.get("redirect_url", ""),
            })
        return results

    def mock_data(self) -> list[dict]:
        return [
            {
                "title": "Cyber Security Apprentice",
                "company": "Bharat Electronics Limited (BEL)",
                "category": "Govt",
                "eligibility": "[Freshers] • B.Tech/B.E CSE/IT/Cyber Security.<br/>• 2023-2025 pass out.<br/>• Min 60% aggregate.<br/>",
                "location": "Bengaluru, Karnataka",
                "country": "India",
                "posted_date": "2026-08-30",
                "deadline": "2026-09-15",
                "sector": "Defence / Electronics",
                "apply_url": "https://apprenticeshipindia.gov.in/vacancy/bel-cyber-2026",
            },
        ]
