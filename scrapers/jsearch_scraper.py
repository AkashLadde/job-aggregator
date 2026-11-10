"""
Source: JSearch API (Google for Jobs) -> listings published on LinkedIn,
Naukri, Indeed, Glassdoor, Foundit, company career pages, etc.

Why JSearch: LinkedIn and Naukri have NO free public job-search API (LinkedIn's
jobs APIs are partner-only; Naukri publishes none), and scraping them breaks
their terms. Google for Jobs already indexes their public postings, and
JSearch exposes that legally through a free plan.

Free plan ~200 requests/month (100 on some RapidAPI plans), each request = 10 jobs.
Budget guard (defaults):
  * runs only on the morning (7 AM IST) run      -> JSEARCH_EVENING=false
  * JSEARCH_REQUESTS_PER_RUN=3                    -> ~90 requests/month
  * JSEARCH_MONTHLY_LIMIT=95 hard stop, counted in job_aggregator.db

Settings:
  JSEARCH_API_KEY    your key (secret)
  JSEARCH_PROVIDER   "rapidapi" (default, key from rapidapi.com)
                     or "openwebninja" (key from openwebninja.com)
"""
import os
import datetime
import logging

from scrapers.base_scraper import BaseScraper, is_morning_run, rotating_pick
from database.db import api_calls_used, record_api_calls

logger = logging.getLogger(__name__)

ENDPOINTS = {
    "rapidapi": "https://jsearch.p.rapidapi.com/search",
    "openwebninja": "https://api.openwebninja.com/jsearch/search",
}

# (query, extra filters). Rotated daily so all are covered every couple of days.
QUERIES = [
    ("software developer fresher", {"job_requirements": "no_experience"}),
    ("software engineer intern", {"employment_types": "INTERN"}),
    ("cyber security fresher", {"job_requirements": "no_experience"}),
    ("data analyst fresher", {"job_requirements": "no_experience"}),
    ("machine learning AI intern", {"employment_types": "INTERN"}),
    ("graduate engineer trainee IT", {}),
    ("SOC analyst fresher", {}),
    ("python developer fresher", {"job_requirements": "no_experience"}),
    ("cloud devops intern", {"employment_types": "INTERN"}),
]


class JSearchScraper(BaseScraper):
    source_name = "JSearch"
    source_label = "Google Jobs"

    def __init__(self, use_mock: bool = False):
        super().__init__(use_mock)
        self.api_key = os.getenv("JSEARCH_API_KEY")
        self.provider = (os.getenv("JSEARCH_PROVIDER") or "rapidapi").strip().lower()

    def enabled(self) -> bool:
        if not self.api_key:
            logger.info("[%s] skipped - JSEARCH_API_KEY not set.", self.source_name)
            return False
        if (os.getenv("JSEARCH_EVENING") or "false").lower() != "true" and not is_morning_run():
            logger.info("[%s] skipped - runs on the morning run only (saves free quota).", self.source_name)
            return False
        return True

    def _headers(self) -> dict:
        if self.provider == "openwebninja":
            return {"x-api-key": self.api_key}
        return {"X-RapidAPI-Key": self.api_key, "X-RapidAPI-Host": "jsearch.p.rapidapi.com"}

    def fetch_live(self) -> list[dict]:
        month = datetime.date.today().strftime("%Y-%m")
        limit = int((os.getenv("JSEARCH_MONTHLY_LIMIT") or "95"))
        used = api_calls_used("jsearch", month)
        n = min(int((os.getenv("JSEARCH_REQUESTS_PER_RUN") or "3")), max(0, limit - used))
        if n <= 0:
            logger.warning("[%s] monthly budget used (%d/%d) - skipping until next month.",
                           self.source_name, used, limit)
            return []

        url = ENDPOINTS.get(self.provider, ENDPOINTS["rapidapi"])
        results = []
        for query, filters in rotating_pick(QUERIES, n):
            params = {
                "query": f"{query} in India",
                "country": "in",
                "page": 1,
                "num_pages": 1,          # >1 page costs extra requests
                "date_posted": (os.getenv("JSEARCH_DATE_POSTED") or "3days"),
                **filters,
            }
            data = self.request_json("GET", url, params=params, headers=self._headers())
            record_api_calls("jsearch", month, 1)
            if not data:
                continue
            batch = [self.parse(j) for j in data.get("data") or []]
            logger.info("[%s] '%s' -> %d results", self.source_name, query, len(batch))
            results.extend(batch)
        logger.info("[%s] budget: %d/%d requests used this month.", self.source_name,
                    api_calls_used("jsearch", month), limit)
        return results

    @staticmethod
    def parse(j: dict) -> dict:
        """Convert one JSearch result into our raw job dict."""
        quals = ((j.get("job_highlights") or {}).get("Qualifications") or [])
        exp = j.get("job_required_experience") or {}
        markers = []
        if exp.get("no_experience_required"):
            markers.append("No experience required.")
        if (j.get("job_employment_type") or "").upper() in ("INTERN", "INTERNSHIP"):
            markers.append("Internship.")
        description = " ".join(markers + [". ".join(quals), j.get("job_description") or ""])

        city = ", ".join(x for x in (j.get("job_city"), j.get("job_state")) if x)
        publisher = (j.get("job_publisher") or "").strip()
        return {
            "job_key": f"jsearch:{j.get('job_id')}" if j.get("job_id") else "",
            "title": j.get("job_title") or "Untitled Role",
            "company": j.get("employer_name") or "Unknown",
            "category": "Private",
            "description": description,
            "location": city or ("Remote" if j.get("job_is_remote") else "India"),
            "country": "India",
            "posted_date": (j.get("job_posted_at_datetime_utc") or "")[:10],
            "deadline": "See posting",
            "sector": "IT Jobs",
            "apply_url": j.get("job_apply_link") or "",
            "source": publisher or "Google Jobs",
        }

    def mock_data(self) -> list[dict]:
        return [self.parse(j) for j in SAMPLE_RESPONSE["data"]]


# Shape of a real JSearch response (trimmed) - used by --mock and the tests.
SAMPLE_RESPONSE = {
    "status": "OK",
    "data": [
        {
            "job_id": "mock-js-1", "job_title": "Associate Software Engineer - 2026 Batch",
            "employer_name": "Mock Infotech", "job_publisher": "LinkedIn",
            "job_employment_type": "FULLTIME", "job_apply_link": "https://example.com/mock/linkedin-ase",
            "job_description": "We are hiring 2026 graduates (B.E/B.Tech CSE/IT/ECE). Training provided. Java, SQL basics.",
            "job_city": "Bengaluru", "job_state": "Karnataka", "job_country": "IN",
            "job_posted_at_datetime_utc": "2026-11-09T06:00:00.000Z",
            "job_highlights": {"Qualifications": ["B.E/B.Tech 2026 pass out", "No backlogs"]},
            "job_required_experience": {"no_experience_required": True},
        },
        {
            "job_id": "mock-js-2", "job_title": "Data Analyst Intern",
            "employer_name": "Mock Analytics", "job_publisher": "Naukri.com",
            "job_employment_type": "INTERN", "job_apply_link": "https://example.com/mock/naukri-da-intern",
            "job_description": "3-month paid internship. SQL, Excel, Power BI.",
            "job_city": "Hyderabad", "job_state": "Telangana", "job_country": "IN",
            "job_posted_at_datetime_utc": "2026-11-08T10:00:00.000Z",
        },
        {
            "job_id": "mock-js-3", "job_title": "Backend Developer",
            "employer_name": "Mock Fintech", "job_publisher": "Indeed",
            "job_employment_type": "FULLTIME", "job_apply_link": "https://example.com/mock/indeed-backend",
            "job_description": "4+ years of experience with Node.js and AWS required.",
            "job_city": "Pune", "job_country": "IN",
            "job_posted_at_datetime_utc": "2026-11-09T08:00:00.000Z",
        },
    ],
}
