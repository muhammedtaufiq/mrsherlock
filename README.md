# 🕵️‍♂️ MrSherlock: Singapore FCF "Ghost Job" Tracker

MrSherlock is a lightweight Python-based compliance audit tool for Singapore’s MyCareersFuture (MCF) portal. It is designed to surface potential “ghost jobs” that may be posted only to satisfy the Fair Consideration Framework (FCF) requirement, which generally requires employers to advertise a role for at least 14 days before hiring foreign talent under an Employment Pass or S Pass.

---

## 🔍 What it does

*   Queries the public MCF API for recent job listings
*   Extracts key fields such as title, employer, UEN, salary, posting date, and expiry date
*   Anonymizes employer names using SHA-256 hashing to protect corporate identities
*   Calculates job duration from posting date to expiry date
*   Applies a 14-Day heuristic to flag listings in the 13–15 day range (aligning with FCF minimums)
*   Applies a Recycler heuristic to catch employers repeatedly posting the exact same role
*   Uses Groq’s LLM for a second-stage risk assessment when a valid API key is configured
*   Stores raw jobs and flagged results in a local SQLite database
*   Visualizes flagged jobs via an interactive Streamlit web dashboard

---

## 🏗️ Architecture and Data Flow

```text
[ MCF REST API ] ──> [ Python Scraper ] ──> [ Heuristics Engine ] ──(Suspicious)──> [ Groq LLM ]
                                                      │                                   │
                                                      └────────> [ SQLite DB ] <──────────┘
                                                                       │
                                                                       v
                                                           [ Streamlit Dashboard ]
✅ Current implementation status
The scraper logic has been hardened to avoid crashing when GROQ_API_KEY is missing

Groq client initialization is now lazy and safe

Salary parsing was normalized to handle different API payload structures reliably

The FCF duration logic has been isolated into testable helper functions

Recycler check implemented via SQL COUNT queries to track identical job titles by UEN

GitHub Actions workflow configured to run the scraper daily at midnight UTC

Streamlit dashboard integrated for interactive data exploration and deployed to the web

📂 Files
scraper.py: main scraper, heuristic engine, and AI analysis logic

db_setup.py: SQLite schema setup

test_scraper.py: unit/regression tests

app.py: Streamlit dashboard UI

requirements.txt: Python package dependencies for deployment

mcf_jobs.db: generated local database

.github/workflows/scrape.yml: CI/CD pipeline for daily automation

README.md: project documentation and setup notes

🧪 Verified
Test command run successfully:

Plaintext
Result: 4 tests passed
Regression tests validate:

salary extraction across nested and dict payloads

missing-value handling

14-day compliance window detection

⚡ Quickstart
Prerequisites
Python 3.11+

A Groq API key from console.groq.com

1. Install dependencies
Bash
pip install -r requirements.txt
2. Initialize the database
Bash
python db_setup.py
3. Run the scraper
Set your environment variable (never commit this to GitHub) and run the script:

Bash
export GROQ_API_KEY="gsk_your_actual_api_key_here"
python scraper.py
4. Run the dashboard locally
Bash
streamlit run app.py
☁️ Deployment & Automation
Web Dashboard (Streamlit Community Cloud):

Ensure your repository is pushed to GitHub.

Go to share.streamlit.io and log in with your GitHub account.

Click New app, select this repository, point it to app.py, and deploy.

Daily Automation (GitHub Actions):
The repository includes a workflow (scrape.yml) that runs every day at midnight UTC. To enable it:

Go to your GitHub Repository -> Settings -> Secrets and variables -> Actions.

Add a new repository secret named GROQ_API_KEY with your actual Groq key.

🚀 Potential Improvements
Salary Anomaly Detection: Add heuristics to catch unusual salary ranges that appear designed to deter local applicants or that are suspiciously narrow.

Hyper-tailored requirements: Parse job requirement text for niche skills or language requirements unrelated to the core business.

Asynchronous multi-page scraping: Replace requests with httpx to crawl multiple API pages in parallel.

⚖️ Current project posture (Disclaimer)
This is a minimal, functional prototype for compliance monitoring and research. It is not a definitive legal or compliance judgment engine; instead, it acts as a heuristic-driven signal generator and data-collection tool that can be expanded with stronger fraud-detection rules, broader scraping, and dashboard reporting.


---

### Terminal Commands (Git Push)

Run these commands in your Codespaces terminal to stage, commit, and push this updated README to your repository:

```bash
git add README.md
git commit -m "Update README to include detailed project posture, Streamlit, and Actions"
git push