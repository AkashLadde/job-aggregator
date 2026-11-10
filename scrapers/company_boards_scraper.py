"""
Source: companies' OWN career boards via the free public Lever and Greenhouse
job-board APIs. No key, no quota, and the link goes straight to the official
company application page (no job-board middleman).

Configure with COMPANY_BOARDS (comma separated "platform:slug" or
"platform:slug:Display Name"):

  COMPANY_BOARDS=lever:cred:CRED,lever:meesho:Meesho,lever:paytm:Paytm,greenhouse:groww:Groww

Finding a company's slug: open its careers page and click a job.
  jobs.lever.co/<slug>/...            -> lever:<slug>
  boards.greenhouse.io/<slug>/...     -> greenhouse:<slug>
  job-boards.greenhouse.io/<slug>/... -> greenhouse:<slug>
Test it in a browser first:
  https://api.lever.co/v0/postings/<slug>?mode=json
  https://boards-api.greenhouse.io/v1/boards/<slug>/jobs
"""
import os
import time
import logging
import datetime

from scrapers.base_scraper import BaseScraper, strip_html, india_only, INDIA_LOCATION

logger = logging.getLogger(__name__)

# Verified working on 2026-11-10. Add more via the COMPANY_BOARDS variable.
DEFAULT_BOARDS = "lever:cred:CRED,lever:meesho:Meesho,lever:paytm:Paytm,greenhouse:groww:Groww"


def parse_boards(raw: str) -> list[tuple[str, str, str]]:
    boards = []
    for item in (raw or "").split(","):
        parts = [p.strip() for p in item.strip().split(":") if p.strip()]
        if len(parts) < 2 or parts[0].lower() not in ("lever", "greenhouse"):
            if item.strip():
                logger.warning("Ignoring bad COMPANY_BOARDS entry '%s' (use lever:slug or greenhouse:slug)", item)
            continue
        name = parts[2] if len(parts) > 2 else parts[1].replace("-", " ").title()
        boards.append((parts[0].lower(), parts[1], name))
    return boards


class CompanyBoardsScraper(BaseScraper):
    source_name = "CompanyBoards"
    source_label = "Company careers page"

    def enabled(self) -> bool:
        return bool(parse_boards(os.getenv("COMPANY_BOARDS") or DEFAULT_BOARDS))

    def fetch_live(self) -> list[dict]:
        max_age = int((os.getenv("COMPANY_MAX_DAYS_OLD") or "30"))
        results = []
        for platform, slug, name in parse_boards(os.getenv("COMPANY_BOARDS") or DEFAULT_BOARDS):
            if platform == "lever":
                data = self.request_json("GET", f"https://api.lever.co/v0/postings/{slug}",
                                         params={"mode": "json"})
                jobs = [self.parse_lever(j, name) for j in (data or [])] if isinstance(data, list) else []
            else:
                data = self.request_json("GET", f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs",
                                         params={"content": "true"})
                jobs = [self.parse_greenhouse(j, name) for j in (data or {}).get("jobs", [])]
            if data is None:
                logger.warning("[%s] %s:%s not reachable (network error, or wrong slug).", self.source_name, platform, slug)
            jobs = self.keep_recent(jobs, max_age)
            if india_only():
                jobs = [j for j in jobs if INDIA_LOCATION.search(j["location"] or "")]
            logger.info("[%s] %s: %d recent postings to check", self.source_name, name, len(jobs))
            results.extend(jobs)
            time.sleep(1)
        return results

    @staticmethod
    def keep_recent(jobs: list[dict], max_days: int) -> list[dict]:
        cutoff = (datetime.date.today() - datetime.timedelta(days=max_days)).isoformat()
        return [j for j in jobs if not j["posted_date"] or j["posted_date"] >= cutoff]

    @staticmethod
    def parse_lever(j: dict, company: str) -> dict:
        cats = j.get("categories") or {}
        lists = " ".join(f"{l.get('text', '')}: {strip_html(l.get('content', ''))}" for l in j.get("lists") or [])
        commitment = cats.get("commitment") or ""
        description = " ".join(filter(None, [
            "Internship." if "intern" in commitment.lower() else "",
            j.get("descriptionPlain") or strip_html(j.get("description") or ""),
            lists,
            j.get("additionalPlain") or "",
        ]))
        created = j.get("createdAt")
        posted = (datetime.datetime.fromtimestamp(created / 1000, datetime.timezone.utc).date().isoformat()
                  if isinstance(created, (int, float)) else "")
        return {
            "job_key": f"lever:{j.get('id')}" if j.get("id") else "",
            "title": j.get("text") or "Untitled Role",
            "company": company,
            "category": "Private",
            "description": description,
            "location": cats.get("location") or "",
            "country": "India",
            "posted_date": posted,
            "deadline": "See posting",
            "sector": cats.get("team") or "IT Jobs",
            "apply_url": j.get("hostedUrl") or j.get("applyUrl") or "",
            "source": f"{company} careers",
        }

    @staticmethod
    def parse_greenhouse(j: dict, company: str) -> dict:
        return {
            "job_key": f"greenhouse:{j.get('id')}" if j.get("id") else "",
            "title": j.get("title") or "Untitled Role",
            "company": company,
            "category": "Private",
            "description": strip_html(j.get("content") or ""),  # content is HTML-escaped HTML
            "location": (j.get("location") or {}).get("name", ""),
            "country": "India",
            "posted_date": (j.get("first_published") or j.get("updated_at") or "")[:10],
            "deadline": "See posting",
            "sector": "IT Jobs",
            "apply_url": j.get("absolute_url") or "",
            "source": f"{company} careers",
        }

    def mock_data(self) -> list[dict]:
        today = datetime.date.today().isoformat()
        lever = self.parse_lever(SAMPLE_LEVER[0], "MockCo")
        gh = self.parse_greenhouse(SAMPLE_GREENHOUSE["jobs"][0], "MockPay")
        lever["posted_date"] = gh["posted_date"] = today
        return [lever, gh]


# Shapes of real Lever / Greenhouse responses (trimmed) - used by --mock and tests.
SAMPLE_LEVER = [{
    "id": "mock-lever-1", "text": "SDE Intern (2026 Graduates)",
    "categories": {"location": "Bangalore, Karnataka", "commitment": "Intern", "team": "Engineering"},
    "descriptionPlain": "Six month internship with the payments platform team.",
    "lists": [{"text": "Requirements", "content": "<li>B.Tech CSE 2026</li><li>DSA &amp; Java</li>"}],
    "additionalPlain": "", "hostedUrl": "https://example.com/mock/lever-sde-intern",
    "createdAt": 1762700000000,
}]
SAMPLE_GREENHOUSE = {"jobs": [{
    "id": 9001, "title": "Graduate Engineer Trainee - Security",
    "location": {"name": "Bengaluru, India"},
    "content": "&lt;p&gt;Entry level role for 2025/2026 B.E graduates in our SOC.&lt;/p&gt;",
    "absolute_url": "https://example.com/mock/gh-get-security", "updated_at": "2026-11-09T10:00:00-04:00",
}]}
