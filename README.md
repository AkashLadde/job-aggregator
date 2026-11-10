# Fresher Job & Internship Aggregator

Pipeline: **Fetch (6 sources) → Fresher filter → Dedupe & store → 2 PDFs → Email**,
run free on GitHub Actions at 7 AM and 7 PM IST.

Only **engineering** internships, trainee/apprentice roles and 0-experience jobs, in two streams,
**India only** by default:

| Stream | Sub-streams shown in the email |
|---|---|
| **Cyber Security** | SOC & Monitoring · VAPT & Pentesting · AppSec & Cloud Security |
| **CSE & Allied** (CSE, ISE, IT, AI/ML, AI & DS, Data Science) | Data Science & AI/ML · Software Development · Cloud & DevOps · Testing & QA · Networking · Govt / PSU (CSE/IT) |

### Engineering-only rules (`ENGINEERING_ONLY=true`, default)

| Dropped | Example |
|---|---|
| Non-engineering roles | IT Helpdesk, Technical Support (voice), Data Entry, UI/UX Designer, Content Writer, Business Analyst |
| Ads only for non-engineering degrees | "BCA / B.Sc only", "any graduate", "Diploma / 12th pass" |
| Ads only for other branches | "B.E Mechanical / Electrical", VLSI, PCB, AutoCAD roles |
| Govt posts that name no CSE-family branch | "IOCL Apprentice - Mechanical, Civil" |

Kept: ads that mention B.E/B.Tech/M.Tech, a CSE-family branch, "all branches", or no degree at all
(e.g. "Software Engineer Intern"). An ad open to "CSE, ECE, EEE, Mechanical" is kept.
Set `ENGINEERING_ONLY=false` to switch these rules off.

## Job sources

| # | Source | What it covers | Key? | Free limit | How the pipeline stays inside it |
|---|---|---|---|---|---|
| 1 | Company career boards (Lever / Greenhouse) | Official openings at CRED, Meesho, Paytm, Groww + any you add | No | None | - |
| 2 | Govt RSS (FreeJobAlert) | Govt / PSU / bank notifications | No | None | - |
| 3 | Adzuna | Private + some PSU jobs | Yes | ~250 calls/day | ~10 calls per run |
| 4 | **JSearch** (Google for Jobs) | **LinkedIn, Naukri, Indeed, Glassdoor, Foundit** postings | Yes | ~200 requests/month | 3 per day, morning run only, hard stop at 95/month |
| 5 | Jooble | 1,000s of Indian job boards | Yes | **500 requests per key, total** | 1 per day, morning only, hard stop at 480 |

**Why not LinkedIn / Naukri directly?** LinkedIn's job APIs are only for approved partners,
Naukri has no public API, and scraping either breaks their terms of use (and gets blocked).
Google for Jobs already indexes their public postings, so JSearch is the legitimate free
route. Each job shows where it came from ("via LinkedIn", "via Naukri.com").

API usage is counted in `job_aggregator.db` (table `api_usage`), which the workflow commits
back after every run, so the limits hold across runs.

## Getting the free API keys (step by step)

**Adzuna**
1. Sign up at https://developer.adzuna.com/signup
2. Dashboard → copy **Application ID** and **Application Key** → `ADZUNA_APP_ID`, `ADZUNA_APP_KEY`

**JSearch (LinkedIn / Naukri / Indeed via Google for Jobs)**
1. Create an account at https://rapidapi.com
2. Search **"JSearch"** (by OpenWeb Ninja / letscrape) → **Pricing** → subscribe to the free **Basic** plan
3. Copy your **X-RapidAPI-Key** → `JSEARCH_API_KEY`
4. Don't add a credit card. Some RapidAPI plans charge for requests over the limit, and the
   built-in stop at 95/month keeps you under it anyway.
5. Alternative: get a key at https://www.openwebninja.com and set variable `JSEARCH_PROVIDER=openwebninja`

**Jooble**
1. Go to https://jooble.org/api/about → fill the form (name, email, website: your GitHub repo URL)
2. The key arrives by email → `JOOBLE_API_KEY`

**Gmail App Password**: enable 2-Step Verification → https://myaccount.google.com/apppasswords

## GitHub setup

**Settings → Secrets and variables → Actions → Secrets tab → New repository secret:**

| Secret | Required? |
|---|---|
| `GMAIL_ADDRESS`, `GMAIL_APP_PASSWORD`, `EMAIL_RECIPIENT` | yes |
| `ADZUNA_APP_ID`, `ADZUNA_APP_KEY` | recommended |
| `JSEARCH_API_KEY` | optional (LinkedIn/Naukri coverage) |
| `JOOBLE_API_KEY` | optional |

**Variables tab** (all optional):

| Variable | Default | Meaning |
|---|---|---|
| `JOB_COUNTRIES` | `in` | Adzuna countries, e.g. `in,ae,sg` |
| `FRESHER_BATCH_YEARS` | last/this/next year | e.g. `2025,2026,2027` |
| `FRESHER_STRICT` | `true` | `false` also includes jobs that never mention experience |
| `COMPANY_BOARDS` | CRED, Meesho, Paytm, Groww | see below |
| `RSS_FEEDS` | FreeJobAlert feed | comma-separated RSS URLs |
| `JSEARCH_PROVIDER` | `rapidapi` | or `openwebninja` |
| `ENGINEERING_ONLY` | `true` | `false` turns off the engineering-only rules |

### Adding more companies

Open a company's careers page and click any job:

- URL like `jobs.lever.co/<slug>/...` → add `lever:<slug>:Name`
- URL like `boards.greenhouse.io/<slug>/...` or `job-boards.greenhouse.io/<slug>/...` → add `greenhouse:<slug>:Name`

Check the slug in your browser first: `https://api.lever.co/v0/postings/<slug>?mode=json`
or `https://boards-api.greenhouse.io/v1/boards/<slug>/jobs` should show JSON.
Example: `COMPANY_BOARDS=lever:cred:CRED,lever:meesho:Meesho,lever:paytm:Paytm,greenhouse:groww:Groww,lever:<new>:<Name>`

## How the fresher filter decides

| Check | Example | Result |
|---|---|---|
| Not a CSE/IT role | Security Guard, Telesales, Mechanical, Peon | dropped |
| Senior title | Senior, Lead, Manager, Architect, Engineer II, Director, Professor | dropped |
| Ad excludes freshers | "experienced candidates only" | dropped |
| Asks for 1+ years | "minimum 3 years of experience" | dropped (unless "freshers can also apply") |
| Only old batches | "2021 and 2022 batch only" | dropped |
| Fresher signal | Intern, Trainee, Fresher, Entry level, Junior, "0-1 years", "2026 batch" | **kept** |
| No signal either way | "Full Stack Developer" with no experience info | dropped (strict mode) |

Govt notifications use a relaxed mode: technical posts (Engineer, Apprentice, Scientist, IT)
that aren't senior and don't ask for experience are kept and marked "Check eligibility".

Each kept job shows **why** it was kept, so you can spot mistakes and tune
`scrapers/fresher_filter.py`.

## Local testing

```bash
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env              # fill in your values

python -m tests.test_fresher_filter      # 22 sample ads
python -m tests.test_streams             # engineering-only rules + stream labels
python -m tests.test_sources             # all 6 sources, offline, no keys needed
python main.py --mock --preview          # sample data -> PDFs + email_preview.html, no email
python main.py --no-notify               # REAL data, no email - check the PDFs
python main.py                           # real data + email
```

- `--mock` writes sample jobs into `job_aggregator.db`. Delete the file after mock testing,
  or back up your real one first.
- JSearch and Jooble only run before 12:00 IST (the morning run). To test them in the evening,
  set `JSEARCH_EVENING=true` / `JOOBLE_EVENING=true` in `.env` for that one run. Every
  Jooble call uses up one of its 500 lifetime requests.

## Project structure

```
scrapers/
  fresher_filter.py          is it for freshers? is it CSE/IT?
  base_scraper.py            shared: HTTP, retries, filter, key redaction in logs
  company_boards_scraper.py  Lever + Greenhouse career boards
  govt_rss_scraper.py        Govt notifications (RSS)
  govt_scraper.py            Adzuna - India public sector
  private_scraper.py         Adzuna - private sector
  jsearch_scraper.py         Google for Jobs (LinkedIn, Naukri, Indeed ...)
  jooble_scraper.py          Jooble
  job_classifier.py          stream + sub-stream labels
database/db.py               SQLite, dedupe, API usage counters
pdf/report_generator.py      PDFs
notifications/email_sender.py
tests/                       offline tests (run by the workflow before every run)
```
