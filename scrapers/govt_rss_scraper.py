"""
Source: Government / PSU / bank job notifications from RSS feeds. No key needed.

Default feed: FreeJobAlert (https://www.freejobalert.com/feed/) - a widely used
PRIVATE aggregator of official Indian govt notifications. Links open its
article page, which links to the official notification PDF. Always confirm on
the official site (the PDF has a "Verify Official Site" link for this).

Why not the NATS / apprenticeship portals directly? They have no public API
and show vacancies only after login.

Filter mode: domain="govt", strict=False -> keeps technical posts (Engineer,
Apprentice, Scientist, IT, Computer ...) that are not senior and don't ask
for experience. Professor/Director/Dean etc. are dropped.

Settings:
  RSS_FEEDS        comma-separated feed URLs (default: FreeJobAlert)
  RSS_PAGES        pages per feed to read (default 3; WordPress "?paged=N")
  RSS_MAX_DAYS_OLD default 3
"""
import os
import re
import logging
import datetime
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime

from scrapers.base_scraper import BaseScraper, strip_html

logger = logging.getLogger(__name__)

DEFAULT_FEEDS = "https://www.freejobalert.com/feed/"


def org_from_title(title: str) -> str:
    """'ISRO Recruitment 2026 – Apply Online for 100 Posts' -> 'ISRO'"""
    org = re.split(r"\s+(?:recruitment|notification|vacancy|jobs?)\b", title, maxsplit=1, flags=re.I)[0]
    # 'ECIL Graduate Engineer Trainee' -> 'ECIL', 'NIELIT Scientist B' -> 'NIELIT'
    org = re.split(
        r"\s+(?:graduate|scientist|engineer|engineering|apprentice|trainee|junior|senior|assistant|"
        r"officer|director|dean|professor|technician|clerk|manager|project|research|it|computer|"
        r"programmer|teacher|peon|driver|staff|executive|analyst|consultant|post|posts)\b",
        org, maxsplit=1, flags=re.I)[0]
    return org.strip(" -–:")[:80] or "Govt / PSU"


class GovtRssScraper(BaseScraper):
    source_name = "GovtRSS"
    source_label = "FreeJobAlert"
    domain = "govt"
    strict = False

    def enabled(self) -> bool:
        return bool((os.getenv("RSS_FEEDS") or DEFAULT_FEEDS).strip())

    def fetch_live(self) -> list[dict]:
        feeds = [f.strip() for f in (os.getenv("RSS_FEEDS") or DEFAULT_FEEDS).split(",") if f.strip()]
        pages = int((os.getenv("RSS_PAGES") or "3"))
        max_age = int((os.getenv("RSS_MAX_DAYS_OLD") or "3"))
        cutoff = (datetime.date.today() - datetime.timedelta(days=max_age)).isoformat()

        results, seen = [], set()
        for feed in feeds:
            for page in range(1, pages + 1):
                url = feed if page == 1 else f"{feed}{'&' if '?' in feed else '?'}paged={page}"
                try:
                    resp = self.session.get(url, timeout=20)
                    resp.raise_for_status()
                    items = self.parse_feed(resp.content, feed)
                except Exception as e:
                    logger.warning("[%s] feed %s page %d failed: %s", self.source_name, feed, page, e)
                    break
                fresh = [i for i in items if i["apply_url"] not in seen]
                seen.update(i["apply_url"] for i in fresh)
                results.extend(i for i in fresh if not i["posted_date"] or i["posted_date"] >= cutoff)
                if not fresh or all(i["posted_date"] and i["posted_date"] < cutoff for i in fresh):
                    break  # no new items / reached old items
        logger.info("[%s] %d recent notifications to check", self.source_name, len(results))
        return results

    @staticmethod
    def parse_feed(xml_bytes: bytes, feed_url: str = "") -> list[dict]:
        root = ET.fromstring(xml_bytes)
        host = re.sub(r"^https?://(www\.)?", "", feed_url).split("/")[0] or "RSS"
        label = "FreeJobAlert" if "freejobalert" in host else host
        out = []
        for item in root.iter("item"):
            title = (item.findtext("title") or "").strip()
            link = (item.findtext("link") or item.findtext("guid") or "").strip()
            desc = strip_html(item.findtext("description") or "")
            posted = ""
            if item.findtext("pubDate"):
                try:
                    posted = parsedate_to_datetime(item.findtext("pubDate")).date().isoformat()
                except Exception:
                    pass
            out.append({
                "job_key": f"rss:{link}",
                "title": title,
                "company": org_from_title(title),
                "category": "Govt",
                "description": desc,
                "location": "India",
                "country": "India",
                "posted_date": posted,
                "deadline": "See notification",
                "sector": "Government",
                "apply_url": link,
                "source": label,
            })
        return out

    def mock_data(self) -> list[dict]:
        items = self.parse_feed(SAMPLE_RSS, DEFAULT_FEEDS)
        today = datetime.date.today().isoformat()
        for i in items:
            i["posted_date"] = today
        return items


SAMPLE_RSS = b"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel><title>FreeJobAlert</title>
<item><title>NIELIT Scientist B Recruitment 2026 - Apply Online for 50 Posts</title>
<link>https://example.com/mock/nielit-scientist-b</link>
<description>B.E/B.Tech in Computer Science / IT with GATE score. Age limit 30 years.</description>
<pubDate>Mon, 09 Nov 2026 05:30:00 GMT</pubDate></item>
<item><title>ECIL Graduate Engineer Trainee Recruitment 2026 - Apply for 40 Posts</title>
<link>https://example.com/mock/ecil-get</link>
<description>B.E/B.Tech ECE, CSE, EEE, Mechanical. 2025 and 2026 pass outs eligible.</description>
<pubDate>Mon, 09 Nov 2026 04:00:00 GMT</pubDate></item>
<item><title>Bharathiar University Director Recruitment 2026 - Apply Offline</title>
<link>https://example.com/mock/bu-director</link>
<description>Ph.D with 10 years of experience.</description>
<pubDate>Mon, 09 Nov 2026 03:00:00 GMT</pubDate></item>
<item><title>District Court Peon Recruitment 2026 - Apply Offline</title>
<link>https://example.com/mock/court-peon</link>
<description>8th pass candidates.</description>
<pubDate>Mon, 09 Nov 2026 02:00:00 GMT</pubDate></item>
</channel></rss>"""
