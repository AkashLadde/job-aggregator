"""
Source: Jooble REST API - aggregates 1,000s of Indian job boards and career sites.

Free key: request at https://jooble.org/api/about (emailed to you).
IMPORTANT: the free key has a LIFETIME limit of 500 requests (not per month).
Budget guard (defaults):
  * morning run only, JOOBLE_REQUESTS_PER_RUN=1   -> ~30 requests/month
  * JOOBLE_TOTAL_LIMIT=480 hard stop, counted in job_aggregator.db
  -> lasts well over a year. Ask Jooble for a higher limit if you need more.

Settings: JOOBLE_API_KEY (secret)
"""
import os
import logging

from scrapers.base_scraper import BaseScraper, is_morning_run, rotating_pick, strip_html
from database.db import api_calls_used, record_api_calls

logger = logging.getLogger(__name__)

KEYWORDS = [
    "fresher software engineer btech",
    "internship computer science engineering",
    "graduate engineer trainee CSE",
    "cyber security fresher",
    "data science fresher btech",
    "SOC analyst fresher",
    "machine learning engineer intern",
]


class JoobleScraper(BaseScraper):
    source_name = "Jooble"
    source_label = "Jooble"

    def __init__(self, use_mock: bool = False):
        super().__init__(use_mock)
        self.api_key = os.getenv("JOOBLE_API_KEY")

    def enabled(self) -> bool:
        if not self.api_key:
            logger.info("[%s] skipped - JOOBLE_API_KEY not set.", self.source_name)
            return False
        if (os.getenv("JOOBLE_EVENING") or "false").lower() != "true" and not is_morning_run():
            logger.info("[%s] skipped - runs on the morning run only (500-request lifetime key).",
                        self.source_name)
            return False
        return True

    def fetch_live(self) -> list[dict]:
        limit = int((os.getenv("JOOBLE_TOTAL_LIMIT") or "480"))
        used = api_calls_used("jooble", "lifetime")
        n = min(int((os.getenv("JOOBLE_REQUESTS_PER_RUN") or "1")), max(0, limit - used))
        if n <= 0:
            logger.warning("[%s] key budget used (%d/%d). Request a new/raised key from Jooble.",
                           self.source_name, used, limit)
            return []

        results = []
        for kw in rotating_pick(KEYWORDS, n):
            body = {"keywords": kw, "location": "India", "page": 1, "ResultOnPage": 50}
            data = self.request_json("POST", f"https://jooble.org/api/{self.api_key}", json=body,
                                     headers={"Content-Type": "application/json"})
            record_api_calls("jooble", "lifetime", 1)
            if not data:
                continue
            batch = [self.parse(j) for j in data.get("jobs") or []]
            logger.info("[%s] '%s' -> %d results", self.source_name, kw, len(batch))
            results.extend(batch)
        logger.info("[%s] budget: %d/%d lifetime requests used.", self.source_name,
                    api_calls_used("jooble", "lifetime"), limit)
        return results

    @staticmethod
    def parse(j: dict) -> dict:
        job_type = j.get("type") or ""
        description = strip_html(j.get("snippet") or "")
        if "intern" in job_type.lower():
            description = "Internship. " + description
        return {
            "job_key": f"jooble:{j.get('id')}" if j.get("id") else "",
            "title": strip_html(j.get("title") or "Untitled Role"),
            "company": strip_html(j.get("company") or "Unknown"),
            "category": "Private",
            "description": description,
            "location": j.get("location") or "India",
            "country": "India",
            "posted_date": (j.get("updated") or "")[:10],
            "deadline": "See posting",
            "sector": "IT Jobs",
            "apply_url": j.get("link") or "",
            "source": f"Jooble ({j['source']})" if j.get("source") else "Jooble",
        }

    def mock_data(self) -> list[dict]:
        return [self.parse(j) for j in SAMPLE_RESPONSE["jobs"]]


# Shape of a real Jooble response (trimmed) - used by --mock and the tests.
SAMPLE_RESPONSE = {
    "totalCount": 2,
    "jobs": [
        {
            "id": 111, "title": "<b>Fresher</b> Java Developer", "company": "Mock Tech Solutions",
            "location": "Chennai, Tamil Nadu", "snippet": "Freshers &amp; 2025 pass outs. Core Java, OOPs, SQL.",
            "salary": "", "source": "foundit.in", "type": "Full-time",
            "link": "https://example.com/mock/jooble-java", "updated": "2026-11-09T00:00:00.0000000",
        },
        {
            "id": 112, "title": "Cyber Security Intern", "company": "Mock SecureNet",
            "location": "Bengaluru, Karnataka", "snippet": "Learn VAPT and SOC monitoring. Final year students can apply.",
            "salary": "", "source": "company site", "type": "Internship",
            "link": "https://example.com/mock/jooble-cyber-intern", "updated": "2026-11-08T00:00:00.0000000",
        },
    ],
}
