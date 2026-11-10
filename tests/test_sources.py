"""
Offline tests for the job sources: parsers, fresher filtering per source,
API budget guards and key redaction. No network, no API keys needed.
Run:  python -m tests.test_sources
"""
import os
import sys
import tempfile

os.environ.setdefault("FRESHER_BATCH_YEARS", "2025,2026,2027")
os.environ["DATABASE_URL"] = "sqlite:///" + os.path.join(tempfile.mkdtemp(), "test.db")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scrapers import jsearch_scraper, jooble_scraper, company_boards_scraper, govt_rss_scraper  # noqa: E402
from scrapers.jsearch_scraper import JSearchScraper  # noqa: E402
from scrapers.jooble_scraper import JoobleScraper  # noqa: E402
from scrapers.company_boards_scraper import CompanyBoardsScraper, parse_boards  # noqa: E402
from scrapers.govt_rss_scraper import GovtRssScraper, org_from_title  # noqa: E402
from scrapers.base_scraper import redact  # noqa: E402
from database.db import init_db, api_calls_used, record_api_calls  # noqa: E402


def titles(jobs):
    return sorted(j["title"] for j in jobs)


def test_jsearch():
    jobs = JSearchScraper(use_mock=True).run()
    assert titles(jobs) == ["Associate Software Engineer - 2026 Batch", "Data Analyst Intern"], titles(jobs)
    by = {j["title"]: j for j in jobs}
    assert by["Data Analyst Intern"]["source"] == "Naukri.com"
    assert by["Data Analyst Intern"]["job_type"] == "Internship"
    assert by["Associate Software Engineer - 2026 Batch"]["location"] == "Bengaluru, Karnataka"
    print("JSearch: kept", titles(jobs), "- dropped 'Backend Developer' (4+ yrs)")


def test_jooble():
    jobs = JoobleScraper(use_mock=True).run()
    assert titles(jobs) == ["Cyber Security Intern", "Fresher Java Developer"], titles(jobs)
    java = [j for j in jobs if "Java" in j["title"]][0]
    assert java["source"] == "Jooble (foundit.in)" and "<b>" not in java["title"]
    print("Jooble: kept", titles(jobs))


def test_company_boards():
    assert parse_boards("lever:cred:CRED, greenhouse:groww, bogus:x, lever") == [
        ("lever", "cred", "CRED"), ("greenhouse", "groww", "Groww")]
    jobs = CompanyBoardsScraper(use_mock=True).run()
    assert titles(jobs) == ["Graduate Engineer Trainee - Security", "SDE Intern (2026 Graduates)"], titles(jobs)
    lever = CompanyBoardsScraper.parse_lever(company_boards_scraper.SAMPLE_LEVER[0], "X")
    assert lever["posted_date"] == "2025-11-09" and "DSA & Java" in lever["description"]
    gh = CompanyBoardsScraper.parse_greenhouse(company_boards_scraper.SAMPLE_GREENHOUSE["jobs"][0], "Y")
    assert "<p>" not in gh["description"] and gh["location"] == "Bengaluru, India"
    print("Company boards: kept", titles(jobs))


def test_govt_rss():
    assert org_from_title("ISRO Recruitment 2026 – Apply Online for 100 Posts") == "ISRO"
    jobs = GovtRssScraper(use_mock=True).run()
    t = titles(jobs)
    assert t == ["ECIL Graduate Engineer Trainee Recruitment 2026 - Apply for 40 Posts",
                 "NIELIT Scientist B Recruitment 2026 - Apply Online for 50 Posts"], t
    assert all(j["category"] == "Govt" for j in jobs)
    print("Govt RSS: kept", t, "- dropped Director & Peon posts")


def test_budget_guard():
    init_db()
    record_api_calls("jsearch", "2026-11", 2)
    record_api_calls("jsearch", "2026-11", 3)
    assert api_calls_used("jsearch", "2026-11") == 5
    assert api_calls_used("jooble", "lifetime") == 0
    # budget exhausted -> fetch_live must not call the API
    os.environ.update(JSEARCH_API_KEY="k", JSEARCH_MONTHLY_LIMIT="0", JOOBLE_API_KEY="k2", JOOBLE_TOTAL_LIMIT="0")
    s = JSearchScraper()
    s.request_json = lambda *a, **k: (_ for _ in ()).throw(AssertionError("API called over budget"))
    assert s.fetch_live() == []
    j = JoobleScraper()
    j.request_json = s.request_json
    assert j.fetch_live() == []
    print("Budget guards: OK")


def test_budget_counts_calls():
    import datetime
    os.environ.update(JSEARCH_API_KEY="k", JSEARCH_MONTHLY_LIMIT="95", JSEARCH_REQUESTS_PER_RUN="3")
    month = datetime.date.today().strftime("%Y-%m")
    before = api_calls_used("jsearch", month)
    s = JSearchScraper()
    s.request_json = lambda *a, **k: jsearch_scraper.SAMPLE_RESPONSE
    jobs = s.fetch_live()
    assert api_calls_used("jsearch", month) == before + 3 and len(jobs) == 9
    print("Budget counting: 3 calls recorded")


def test_redact():
    os.environ["JOOBLE_API_KEY"] = "secret-123"
    assert redact("POST https://jooble.org/api/secret-123 failed") == "POST https://jooble.org/api/*** failed"
    print("Key redaction: OK")


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
    print("\nAll source tests passed.")
