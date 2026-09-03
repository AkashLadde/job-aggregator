# Automated Engineering Job & Internship Aggregator

Daily pipeline: **Scrape → Dedupe & Store → Build PDF → Email + WhatsApp**, run for free every morning via GitHub Actions.

## Project Structure

```
job_aggregator/
├── scrapers/
│   ├── base_scraper.py      # shared retry/timeout/normalize + mock fallback logic
│   ├── govt_scraper.py      # Scraper A: Govt/PSU/NATS listings
│   └── private_scraper.py   # Scraper B: Private/Unstop/LinkedIn listings
├── database/
│   ├── models.py            # JobOpportunity SQLAlchemy model
│   └── db.py                 # connection + dedup-aware save helpers
├── pdf/
│   └── report_generator.py  # ReportLab styled PDF builder
├── notifications/
│   ├── email_sender.py      # Gmail SMTP with PDF attachment
│   └── whatsapp_sender.py   # Twilio WhatsApp message
├── main.py                  # orchestrator entry point
├── requirements.txt
├── .env.example
└── .github/workflows/daily_digest.yml
```

## 1. Local Setup (test before going live)

```bash
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
playwright install chromium

cp .env.example .env            # fill in real values (or leave blank to test with mocks only)
```

**First run — no credentials needed, uses mock data, no notifications:**
```bash
python main.py --mock --no-notify
```
This creates `job_aggregator.db` and `daily_digest.pdf` locally. Open the PDF to confirm formatting looks right.

**Test email/WhatsApp once `.env` is filled in:**
```bash
python main.py --mock
```

**Run against live targets** (once you've adapted the CSS selectors in `govt_scraper.py` / `private_scraper.py` to the real site structure — see notes in those files):
```bash
python main.py
```

## 2. Gmail App Password Setup
1. Enable 2-Step Verification on your Google account.
2. Go to https://myaccount.google.com/apppasswords
3. Generate a 16-character App Password for "Mail".
4. Use that (not your login password) as `GMAIL_APP_PASSWORD`.

## 3. Twilio WhatsApp Setup
1. Create a free account at twilio.com.
2. Activate the WhatsApp Sandbox (Console → Messaging → Try it out → Send a WhatsApp message).
3. From your phone, send the given join code to the sandbox number to opt in.
4. Copy `Account SID`, `Auth Token`, and the sandbox `From` number into `.env`.
5. For production (not sandbox), apply for a Twilio WhatsApp Business Sender.

> WhatsApp media (the PDF) must be served from a public HTTPS URL — Twilio can't accept a raw file upload. Options: commit the PDF to your repo and use its raw GitHub URL, or host it on S3/Cloudinary. Without a public URL, the pipeline still sends a text summary via WhatsApp and the full PDF via email.

## 4. GitHub Actions Setup (free daily automation)
1. Push this project to a GitHub repository.
2. Go to **Settings → Secrets and variables → Actions → New repository secret** and add:
   - `GMAIL_ADDRESS`, `GMAIL_APP_PASSWORD`, `EMAIL_RECIPIENT`
   - `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_WHATSAPP_FROM`, `WHATSAPP_TO`
   - `DATABASE_URL` (optional — omit to use SQLite committed to the repo)
   - `PDF_PUBLIC_URL` (optional)
3. The workflow at `.github/workflows/daily_digest.yml` runs automatically at **00:30 UTC = 6:00 AM IST** daily, and can also be triggered manually from the **Actions** tab (`workflow_dispatch`).
4. Each run uploads the PDF as a workflow artifact (kept 14 days) and, if `contents: write` permission and a committed SQLite DB are used, commits the updated DB back so dedup state persists across runs.

## 5. Going from Mock → Live Scraping
- `govt_scraper.py` and `private_scraper.py` contain a **Playwright + BeautifulSoup pattern** with placeholder CSS selectors (`.listing-card`, `.opportunity-card`, etc.). Inspect your real target site's HTML (DevTools → right-click element → Inspect) and update the selectors to match.
- Always check the target site's `robots.txt` and Terms of Service before scraping in production. LinkedIn in particular restricts automated scraping — prefer their official Jobs API or a compliant aggregator like Unstop's public pages for that source.
- If a live scrape fails or returns 0 results, the pipeline automatically falls back to mock data and logs a warning — it will never crash your GitHub Actions run.

## 6. Extending
- **Postgres in production:** just set `DATABASE_URL=postgresql+psycopg2://user:pass@host:5432/db` — no code changes needed (SQLAlchemy handles the dialect).
- **More sources:** add a new class in `scrapers/` extending `BaseScraper`, implement `fetch_live()` + `mock_data()`, and add it to the `scrapers` list in `main.py`.
- **Meta Cloud API instead of Twilio:** swap the internals of `whatsapp_sender.py` — the `send_whatsapp_digest()` function signature can stay the same so `main.py` doesn't need to change.
