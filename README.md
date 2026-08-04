# 🕵️‍♂️ MrSherlock: Singapore FCF "Ghost Job" Tracker

MrSherlock is a lightweight compliance-auditing tool designed to detect potential "ghost jobs" on Singapore's MyCareersFuture (MCF) portal.

Under the Fair Consideration Framework (FCF), employers are generally required to advertise roles on MyCareersFuture for at least 14 days before applying for an Employment Pass (EP) or S Pass. MrSherlock automatically ingests job listings, checks their posting duration, applies rule-based heuristics, and uses fast LLM inference to flag listings that may have been posted only to satisfy compliance requirements.

---

## 🏗️ Architecture and Data Flow

```text
[ MCF REST API ] ──> [ Python Scraper ] ──> [ 14-Day Heuristic Check ] ──(Suspicious)──> [ Groq LLM ]
                                                       │                                      │
                                                       └────────────> [ SQLite DB ] <──────┘
```

The system follows a simple two-stage pipeline:

1. Direct API ingestion
   - Queries the public MCF API at `https://api.mycareersfuture.gov.sg/v2/jobs`
   - Pulls structured JSON payloads such as title, company name, UEN, salary ranges, posting date, and expiry date

2. Stage 1: 14-day heuristic check
   - Calculates the listing duration as:

   $$
   \text{Duration (days)} = \text{Expiry Date} - \text{Posting Date}
   $$

   - Flags postings configured to remain active for roughly 13–15 days, which closely matches the FCF minimum requirement

3. Stage 2: LLM-based risk review
   - Escalates suspicious listings to Groq's `llama-3.1-8b-instant` model
   - Produces a short, human-readable risk explanation
   - Groq has announced plans to deprecate `llama-3.1-8b-instant` on August 16, 2026; the recommended replacement is `openai/gpt-oss-20b`

4. Local persistence
   - Stores raw jobs and flagged records in a local SQLite database: `mcf_jobs.db`

---

## ⚡ Quickstart

### Prerequisites

- Python 3.11+
- A Groq API key from [console.groq.com](https://console.groq.com/)

### 1. Install dependencies

```bash
pip install requests groq
```

### 2. Initialize the database

```bash
python db_setup.py
```

This creates the SQLite database and required tables for jobs and flags.

### 3. Set your environment variable

```bash
export GROQ_API_KEY="gsk_your_actual_api_key_here"
```

> Never commit API keys to GitHub. Keep them in your local environment or GitHub repository secrets.

If the key is missing, the scraper will still run the heuristic checks and skip LLM review gracefully instead of crashing.

### 4. Run the scraper

```bash
python scraper.py
```

The script fetches recent MCF listings, applies the 14-day heuristic, and sends suspicious postings for LLM review when a valid Groq API key is configured.

### 5. Run the test suite

```bash
python -m unittest discover -s tests -v
```

This validates the core salary parsing and FCF-duration logic.

---

## 📊 Querying Results

You can inspect the results directly from SQLite.

### View all flagged jobs

```bash
python -c "import sqlite3; conn = sqlite3.connect('mcf_jobs.db'); cursor = conn.cursor(); print(cursor.execute('SELECT j.title, j.employer_name, j.employer_uen, f.flag_reason FROM flags f JOIN jobs j ON f.job_id = j.job_id').fetchall()); conn.close()"
```

### Count flagged jobs by employer

```bash
python -c "import sqlite3; conn = sqlite3.connect('mcf_jobs.db'); cursor = conn.cursor(); print(cursor.execute('SELECT j.employer_name, COUNT(*) as flag_count FROM flags f JOIN jobs j ON f.job_id = j.job_id GROUP BY j.employer_name ORDER BY flag_count DESC').fetchall()); conn.close()"
```

---

## 🤖 Daily Automation with GitHub Actions

You can run the audit automatically every day without paying for server hosting.

### 1. Create the workflow

Create `.github/workflows/scrape.yml` with:

```yaml
name: Daily MCF Ghost Job Audit

on:
  schedule:
    - cron: '0 0 * * *'
  workflow_dispatch:

jobs:
  audit:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: pip install requests groq

      - name: Run Scraper & AI Audit
        env:
          GROQ_API_KEY: ${{ secrets.GROQ_API_KEY }}
        run: |
          python db_setup.py
          python scraper.py

      - name: Commit Updated DB
        run: |
          git config --local user.email "action@github.com"
          git config --local user.name "GitHub Action Bot"
          git add mcf_jobs.db
          git commit -m "Automated daily compliance check" || exit 0
          git push
```

### 2. Add the secret

Add `GROQ_API_KEY` under:

- GitHub Repo → Settings → Secrets and variables → Actions → New repository secret

---

## 🚀 Potential Improvements
[](https://github.com/muhammedtaufiq/mrsherlock#-potential-improvements)
This project is intentionally minimal, but it can be extended into a more robust compliance-monitoring platform.

### 1. Stronger ghost-job heuristics
[](https://github.com/muhammedtaufiq/mrsherlock#1-stronger-ghost-job-heuristics)
Add checks such as:

- Recycler check: detecting the same role being deleted and reposted repeatedly
- Salary anomaly detection: unusual salary ranges that appear designed to deter local applicants
- Hyper-tailored requirements: niche skills or language requirements unrelated to the core business
- Zero-applicant or short-lived hiring patterns: matching unusual posting behavior against sudden closures or withdrawals

### 2. Asynchronous multi-page scraping
[](https://github.com/muhammedtaufiq/mrsherlock#2-asynchronous-multi-page-scraping)

- Replace `requests` with `httpx` or `aiohttp`
- Add retry/backoff logic for transient API errors and rate limiting
- Crawl more pages efficiently in parallel

### 3. Entity and business cross-referencing
[](https://github.com/muhammedtaufiq/mrsherlock#3-entity-and-business-cross-referencing)

- Use the employer UEN to enrich records using public business-register or government datasets
- Group flagged listings by sector, company size, or industry to identify broader patterns

### 4. Dashboard and reporting
[](https://github.com/muhammedtaufiq/mrsherlock#4-dashboard-and-reporting)

- Build a lightweight Streamlit or Reflex dashboard for exploring flagged jobs
- Export summaries as CSV or JSON for weekly compliance reporting

---

## ⚖️ Disclaimer

This project is intended for educational, research, and data-analysis purposes. Results generated by heuristic checks and LLM review are risk indicators, not definitive proof of misconduct or legal non-compliance.

---

## 📌 Project Files

- `db_setup.py` — creates the SQLite schema
- `scraper.py` — fetches job data, applies the FCF heuristic, and triggers LLM review when configured
- `tests/test_scraper.py` — regression tests for salary parsing and duration checks
- `mcf_jobs.db` — local database generated by the project
