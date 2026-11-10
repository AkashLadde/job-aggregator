"""
Shared scraper functionality: Adzuna API calls with retries + rate limiting,
normalisation, the FRESHER filter, and a consistent error-handling contract
so main.py never crashes because one source is down.

IMPORTANT CHANGE: in live mode, a failed or empty scrape now returns an
empty list. It no longer falls back to mock data, because mock jobs were
being saved and emailed as if they were real openings.
"""
import os
import re
import time
import html
import logging
import datetime
from zoneinfo import ZoneInfo
from collections import Counter
from abc import ABC, abstractmethod

import requests

from scrapers.fresher_filter import judge
from scrapers.job_classifier import classify, CSE, GOVT_SUB

logger = logging.getLogger(__name__)

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-IN,en;q=0.9",
}

REQUEST_TIMEOUT = 20
ADZUNA_BASE = "https://api.adzuna.com/v1/api/jobs/{country}/search/{page}"
# Adzuna free tier: ~25 calls/minute, ~250 calls/day. Stay well under it.
ADZUNA_PAUSE_SECONDS = 3

# Organisations that make a job "Govt / PSU" (India). Matched on company + title.
GOVT_PATTERN = re.compile(
    r"\b(government|govt\.?|ministry|public\s+sector|psu|bharat\s+electronics|\bbel\b|bhel|isro|drdo|"
    r"c-?dac|\bnic\b|national\s+informatics|nielit|ongc|ntpc|iocl|indian\s+oil|\bhal\b|hindustan\s+aeronautics|"
    r"bsnl|mtnl|gail|\bsail\b|ecil|railway|\brrb\b|irctc|\bcris\b|upsc|\bssc\b|nabard|reserve\s+bank|"
    r"\brbi\b|state\s+bank\s+of\s+india|indian\s+(?:army|navy|air\s+force)|\bnats\b|apprenticeship\s+india|"
    r"\biit\b|\bnit\b|\biiit\b|cert-?in|nciipc|stpi|meity)\b",
    re.I,
)


def strip_html(text: str) -> str:
    text = html.unescape(text or "")
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)
    return re.sub(r"\s+([.,;:!?])", r"\1", text).strip()


def format_eligibility(description: str) -> str:
    """
    Turn a raw description into up to 4 bullet points for the PDF.
    Text is HTML-escaped (a stray '<' or '&' used to crash the PDF build);
    only our own <br/> tags are added.
    """
    text = strip_html(description)
    if not text:
        return "• See posting for full eligibility details"
    snippet = text[:450]
    parts = [p.strip() for p in re.split(r"(?<=[.!?])\s+|\s•\s|\s-\s", snippet) if p.strip()]
    bullets = parts[:4] if parts else [snippet]
    return "".join(f"• {html.escape(b.rstrip('.'))}.<br/>" for b in bullets)


def classify_category(company: str, title: str, default: str = "Private") -> str:
    return "Govt" if GOVT_PATTERN.search(f"{company} {title}") else default


SECRET_ENV = ("ADZUNA_APP_KEY", "JSEARCH_API_KEY", "JOOBLE_API_KEY", "ADZUNA_APP_ID")


def redact(text: str) -> str:
    """Never print API keys into (public) GitHub Actions logs."""
    for name in SECRET_ENV:
        val = os.getenv(name)
        if val:
            text = text.replace(val, "***")
    return text


def is_morning_run() -> bool:
    """True for the 7 AM IST run. Quota-limited APIs run only then (see README)."""
    return datetime.datetime.now(ZoneInfo("Asia/Kolkata")).hour < 12


def rotating_pick(items: list, n: int) -> list:
    """Pick n items, rotating daily so every query gets used over a few days."""
    if not items or n <= 0:
        return []
    start = (datetime.date.today().toordinal() * n) % len(items)
    return [items[(start + i) % len(items)] for i in range(min(n, len(items)))]


def india_only() -> bool:
    codes = [c.strip().lower() for c in (os.getenv("JOB_COUNTRIES") or "in").split(",") if c.strip()]
    return codes == ["in"]


INDIA_LOCATION = re.compile(
    r"india|bengaluru|bangalore|hyderabad|pune|mumbai|delhi|noida|gurgaon|gurugram|chennai|kolkata|"
    r"ahmedabad|jaipur|kochi|coimbatore|chandigarh|indore|mysore|mysuru|trivandrum|thiruvananthapuram|"
    r"bhubaneswar|nagpur|lucknow|vizag|visakhapatnam|mangalore|mangaluru|hubli|belgaum|kalaburagi|bidar|"
    r"remote", re.I)


class BaseScraper(ABC):
    source_name = "base"
    source_label = "Adzuna"   # shown in the PDF/email as "via ..."
    domain = "cse"            # "govt" accepts general technical govt posts
    strict = None             # None = use FRESHER_STRICT setting

    def __init__(self, use_mock: bool = False):
        self.use_mock = use_mock
        self.session = requests.Session()
        self.session.headers.update(DEFAULT_HEADERS)
        self.app_id = os.getenv("ADZUNA_APP_ID")
        self.app_key = os.getenv("ADZUNA_APP_KEY")
        self.rejected = Counter()

    def enabled(self) -> bool:
        """Return False (with a log line) when the source's API key isn't configured."""
        if self.app_id and self.app_key:
            return True
        logger.info("[%s] skipped - ADZUNA_APP_ID / ADZUNA_APP_KEY not set.", self.source_name)
        return False

    # ------------------------------------------------------------ HTTP helpers
    def request_json(self, method: str, url: str, **kwargs):
        """GET/POST with one retry. Returns parsed JSON or None. Never raises."""
        kwargs.setdefault("timeout", REQUEST_TIMEOUT)
        for attempt in (1, 2):
            try:
                resp = self.session.request(method, url, **kwargs)
                if resp.status_code in (401, 403):
                    logger.error("[%s] %s -> HTTP %s (check the API key / subscription).",
                                 self.source_name, redact(url.split("?")[0]), resp.status_code)
                    return None
                if resp.status_code == 429:
                    logger.error("[%s] HTTP 429 - API quota/rate limit reached.", self.source_name)
                    return None
                resp.raise_for_status()
                return resp.json()
            except Exception as e:
                logger.warning("[%s] request attempt %d failed: %s", self.source_name, attempt,
                               redact(str(e).split("?")[0]))
                time.sleep(3)
        return None

    # ------------------------------------------------------------ Adzuna
    def adzuna_search(self, country: str, params: dict, pages: int = 1) -> list[dict]:
        """Call Adzuna (with 1 retry per page) and return raw result dicts."""
        if not self.app_id or not self.app_key:
            logger.error("[%s] ADZUNA_APP_ID / ADZUNA_APP_KEY not set.", self.source_name)
            return []

        out = []
        for page in range(1, pages + 1):
            url = ADZUNA_BASE.format(country=country, page=page)
            query = {
                "app_id": self.app_id,
                "app_key": self.app_key,
                "results_per_page": 50,
                "sort_by": "date",
                "content-type": "application/json",
                **params,
            }
            data = None
            for attempt in (1, 2):
                try:
                    resp = self.session.get(url, params=query, timeout=REQUEST_TIMEOUT)
                    resp.raise_for_status()
                    data = resp.json()
                    break
                except Exception as e:  # network error, 429, 5xx ...
                    logger.warning("[%s] Adzuna %s page %d attempt %d failed: %s",
                                   self.source_name, country, page, attempt, redact(str(e)))
                    time.sleep(ADZUNA_PAUSE_SECONDS * 2)
            time.sleep(ADZUNA_PAUSE_SECONDS)
            if not data:
                break
            results = data.get("results", [])
            out.extend(results)
            if len(results) < query["results_per_page"]:
                break  # no more pages
        return out

    def from_adzuna(self, job: dict, country_name: str, default_category: str) -> dict:
        company = (job.get("company") or {}).get("display_name", "") or "Unknown"
        title = job.get("title", "") or "Untitled Role"
        description = job.get("description", "") or ""
        return {
            "job_key": f"adzuna:{job.get('id')}" if job.get("id") else "",
            "title": strip_html(title),
            "company": strip_html(company),
            "category": classify_category(company, title, default_category),
            "description": description,
            "location": (job.get("location") or {}).get("display_name", country_name),
            "country": country_name,
            "posted_date": (job.get("created", "") or "")[:10],
            "deadline": "See posting",
            "sector": (job.get("category") or {}).get("label", "IT Jobs"),
            "apply_url": job.get("redirect_url", ""),
            "source": "Adzuna",
        }

    # ------------------------------------------------------------ contract
    @abstractmethod
    def fetch_live(self) -> list[dict]:
        raise NotImplementedError

    @abstractmethod
    def mock_data(self) -> list[dict]:
        raise NotImplementedError

    def normalize(self, raw: dict) -> dict:
        return {
            "job_key": (raw.get("job_key") or "").strip(),
            "title": (raw.get("title") or "Untitled Role").strip(),
            "company": (raw.get("company") or "Unknown").strip(),
            "category": raw.get("category", "Private"),
            "eligibility": format_eligibility(raw.get("description", "")),
            "location": (raw.get("location") or "India").strip(),
            "country": (raw.get("country") or "India").strip(),
            "posted_date": (raw.get("posted_date") or "").strip(),
            "deadline": (raw.get("deadline") or "See posting").strip(),
            "sector": (raw.get("sector") or "IT Jobs").strip(),
            "apply_url": (raw.get("apply_url") or "").strip(),
            "source": (raw.get("source") or self.source_label).strip(),
        }

    def run(self) -> list[dict]:
        if self.use_mock:
            logger.info("[%s] Using mock data (--mock).", self.source_name)
            raw_jobs = self.mock_data()
        elif not self.enabled():
            return []
        else:
            try:
                raw_jobs = self.fetch_live()
            except Exception as e:
                logger.error("[%s] Live scrape crashed: %s", self.source_name, e)
                raw_jobs = []
            if not raw_jobs:
                logger.warning("[%s] Live scrape returned 0 results (no mock fallback).", self.source_name)

        kept = []
        for raw in raw_jobs:
            verdict = judge(raw.get("title", ""), raw.get("description", ""),
                            domain=self.domain, strict=self.strict)
            if not verdict.accepted:
                # group similar reasons for the log line: "Needs N years", "Only for batch N"
                key = re.sub(r"\d[\d.,+ ]*", "N ", verdict.reason.split(" (")[0]).strip()
                self.rejected[key] += 1
                logger.debug("[%s] Rejected '%s' @ %s: %s", self.source_name,
                             raw.get("title"), raw.get("company"), verdict.reason)
                continue
            job = self.normalize(raw)
            job["stream"], job["sub_stream"] = classify(raw.get("title", ""), raw.get("description", ""))
            if job["category"] == "Govt" and job["stream"] == CSE and job["sub_stream"] == "Software Development":
                job["sub_stream"] = GOVT_SUB
            job["fresher_reason"] = verdict.reason
            job["fresher_tags"] = verdict.tags
            job["job_type"] = "Internship" if "Internship" in verdict.tags else (
                "Apprenticeship" if "Apprenticeship" in verdict.tags else "Job")
            kept.append(job)

        logger.info("[%s] %d fetched -> %d fresher jobs kept, %d rejected %s",
                    self.source_name, len(raw_jobs), len(kept), sum(self.rejected.values()),
                    dict(self.rejected.most_common(6)))
        return kept
