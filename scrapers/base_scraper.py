"""
Shared scraper functionality: HTTP session with retries, normalization,
and a consistent error-handling contract so main.py never crashes because
one site changed its HTML or is temporarily down.
"""
import logging
import requests
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-IN,en;q=0.9",
}

REQUEST_TIMEOUT = 15


class BaseScraper(ABC):
    source_name = "base"

    def __init__(self, use_mock: bool = False):
        self.use_mock = use_mock
        self.session = requests.Session()
        self.session.headers.update(DEFAULT_HEADERS)

    def get(self, url: str):
        try:
            resp = self.session.get(url, timeout=REQUEST_TIMEOUT)
            resp.raise_for_status()
            return resp
        except requests.RequestException as e:
            logger.warning("[%s] Request failed for %s: %s", self.source_name, url, e)
            return None

    @abstractmethod
    def fetch_live(self) -> list[dict]:
        raise NotImplementedError

    @abstractmethod
    def mock_data(self) -> list[dict]:
        raise NotImplementedError

    def normalize(self, raw: dict) -> dict:
        return {
            "title": (raw.get("title") or "Untitled Role").strip(),
            "company": (raw.get("company") or "Unknown").strip(),
            "category": raw.get("category", "Private"),
            "eligibility": (raw.get("eligibility") or "Not specified").strip(),
            "location": (raw.get("location") or "India").strip(),
            "deadline": (raw.get("deadline") or "Not specified").strip(),
            "sector": (raw.get("sector") or "Engineering").strip(),
            "apply_url": (raw.get("apply_url") or "").strip(),
        }

    def run(self) -> list[dict]:
        if self.use_mock:
            logger.info("[%s] Using mock data (use_mock=True).", self.source_name)
            results = self.mock_data()
        else:
            try:
                results = self.fetch_live()
                if not results:
                    logger.warning("[%s] Live scrape returned 0 results, falling back to mock.", self.source_name)
                    results = self.mock_data()
            except Exception as e:
                logger.error("[%s] Live scrape crashed (%s), falling back to mock.", self.source_name, e)
                results = self.mock_data()

        return [self.normalize(r) for r in results]
