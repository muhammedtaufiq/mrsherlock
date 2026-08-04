import os
import sqlite3
from datetime import datetime

import requests
from groq import Groq

# --- Configuration ---
# The undocumented public API endpoint for MyCareersFuture job searches
API_URL = "https://api.mycareersfuture.gov.sg/v2/jobs"


def get_groq_client():
    """Create the Groq client only when an API key is available."""
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        return None
    return Groq(api_key=api_key)


client = get_groq_client()


def extract_salary_info(job):
    """Normalise salary payloads from the MCF API into min/max floats."""
    raw_salary = job.get("salary")
    salary_info = {}

    if isinstance(raw_salary, list) and raw_salary:
        salary_info = raw_salary[0] if isinstance(raw_salary[0], dict) else {}
    elif isinstance(raw_salary, dict):
        salary_info = raw_salary

    min_salary = salary_info.get("minimum")
    max_salary = salary_info.get("maximum")

    def to_float(value):
        if value in (None, ""):
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    return to_float(min_salary), to_float(max_salary)


def should_flag_duration(duration_days):
    """Return True when a listing sits in the legal minimum FCF window."""
    return 13 <= duration_days <= 15

def fetch_jobs(page=0, limit=20):
    """Fetches a page of jobs from the MCF API."""
    params = {
        "limit": limit,
        "page": page,
        "sortBy": "new_posting_date" # Get the most recent postings
    }
    
    # Adding a User-Agent is good practice to avoid immediate blocks
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }

    try:
        response = requests.get(API_URL, params=params, headers=headers)
        response.raise_for_status()
        return response.json().get('results', [])
    except requests.exceptions.RequestException as e:
        print(f"Error fetching data: {e}")
        return []

def store_jobs_and_analyze(jobs_data):
    """Stores the raw data and sends it to Groq for ghost job analysis."""
    conn = sqlite3.connect('mcf_jobs.db')
    cursor = conn.cursor()

    for job in jobs_data:
        job_id = job.get('uuid')
        title = job.get('title')

        employer_name = job.get('postedCompany', {}).get('name', 'Unknown')
        employer_uen = job.get('postedCompany', {}).get('uen', 'Unknown')

        posted_date = job.get('metadata', {}).get('newPostingDate')
        expires_date = job.get('metadata', {}).get('expiryDate')
        min_salary, max_salary = extract_salary_info(job)

        try:
            cursor.execute('''
                INSERT OR IGNORE INTO jobs
                (job_id, title, employer_name, employer_uen, posted_date, expires_date, min_salary, max_salary)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (job_id, title, employer_name, employer_uen, posted_date, expires_date, min_salary, max_salary))
        except sqlite3.Error as e:
            print(f"Database error for job {job_id}: {e}")
            continue

        if posted_date and expires_date:
            try:
                posted = datetime.fromisoformat(posted_date.replace("Z", "+00:00"))
                expires = datetime.fromisoformat(expires_date.replace("Z", "+00:00"))
                duration_days = (expires - posted).days

                if should_flag_duration(duration_days):
                    analyze_with_groq(cursor, job_id, title, employer_name, employer_uen, duration_days)
            except ValueError:
                pass

    conn.commit()
    conn.close()

def analyze_with_groq(cursor, job_id, title, employer, uen, duration):
    """Uses Groq (Llama 3) to analyze a suspicious job posting."""
    groq_client = get_groq_client()
    if groq_client is None:
        print(f"Skipping Groq analysis for {title}: GROQ_API_KEY is not set.")
        return

    prompt = f"""
    Analyze this job posting from the Singapore job market for signs of a 'ghost job' posted merely to comply with the Fair Consideration Framework (FCF) 14-day requirement.

    Job Title: {title}
    Employer: {employer} (UEN: {uen})
    Posting Duration: {duration} days

    The FCF requires a minimum 14-day posting. This job is posted for exactly {duration} days.
    Given this data, is this highly suspicious? Reply ONLY with a short, 1-sentence reason why it is flagged, or reply 'SAFE' if you need more data (like salary or requirements) to make a call.
    """

    try:
        chat_completion = groq_client.chat.completions.create(
            messages=[
                {"role": "system", "content": "You are a Singapore HR compliance analyst."},
                {"role": "user", "content": prompt}
            ],
            model="llama-3.1-8b-instant",
            temperature=0.1,
        )

        result = chat_completion.choices[0].message.content.strip()

        if result != "SAFE":
            print(f"FLAGGED [{uen}]: {title} - {result}")
            cursor.execute('INSERT INTO flags (job_id, flag_reason) VALUES (?, ?)', (job_id, result))

    except Exception as e:
        print(f"Groq API Error: {e}")

if __name__ == "__main__":
    print("Starting MCF Scrape...")
    # Fetch just the first page (20 jobs) for testing. 
    # In production, loop through pages until you hit your daily limit or exhaust new postings.
    jobs_data = fetch_jobs(page=0, limit=20)
    
    if jobs_data:
        print(f"Fetched {len(jobs_data)} jobs. Analyzing...")
        store_jobs_and_analyze(jobs_data)
        print("Run complete.")
    else:
        print("No jobs found or error fetching.")