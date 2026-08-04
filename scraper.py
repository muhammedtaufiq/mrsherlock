import os
import sqlite3
import hashlib
from datetime import datetime
import requests
from groq import Groq

# --- Configuration ---
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

def is_target_sector(job, title, employer_name):
    """Filters jobs to only include IT roles or IT placement agencies."""
    # 1. Check MCF's official categories for this job
    categories = [c.get('category', '') for c in job.get('categories', []) if isinstance(c, dict)]
    is_it_category = any("Information Technology" in cat for cat in categories)
    
    # 2. Check the job title for tech keywords
    tech_keywords = ['software', 'developer', 'cyber', 'network', 'data', 'cloud', 'system', 'engineer', 'architect']
    title_lower = title.lower()
    is_it_title = any(kw in title_lower for kw in tech_keywords)
    
    # 3. Check if the employer is a placement/consulting agency
    agency_keywords = ['recruitment', 'search', 'consulting', 'manpower', 'placement', 'agency', 'solutions', 'technologies']
    emp_lower = employer_name.lower()
    is_agency = any(kw in emp_lower for kw in agency_keywords)
    
    # Keep the job if it's an IT role OR if an agency is hiring for an IT title
    return is_it_category or is_it_title or is_agency

def anonymize_name(name):
    """Redacts the employer name with a short hash for safety."""
    if not name or name == 'Unknown':
        return 'Unknown'
    # Create a short 8-character hash of the name
    short_hash = hashlib.sha256(name.encode()).hexdigest()[:8]
    return f"Company-{short_hash}"

def fetch_jobs(page=0, limit=20):
    """Fetches a page of jobs from the MCF API."""
    params = {
        "limit": limit,
        "page": page,
        "sortBy": "new_posting_date"
    }
    
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

    # --- NEW: Fetch the ACRA ID once before processing jobs ---
    acra_resource_id = get_latest_acra_resource_id()
    if acra_resource_id:
        print(f"Successfully retrieved live ACRA Resource ID: {acra_resource_id}")
    else:
        print("Warning: Skipping ACRA lookups (Dataset ID not found).")

    for job in jobs_data:
        job_id = job.get('uuid')
        title = job.get('title')

        raw_employer_name = job.get('postedCompany', {}).get('name', 'Unknown')
        # --- SECTOR TARGETING ---
        # If it's not an IT role or an agency, skip to the next job immediately
        if not is_target_sector(job, title, raw_employer_name):
            continue
            
        # Anonymize the employer name immediately
        employer_name = anonymize_name(raw_employer_name)
        employer_uen = job.get('postedCompany', {}).get('uen', 'Unknown')

        # --- UPDATED: Pass the dynamic ID into the lookup ---
        company_age = get_company_age_years(employer_uen, acra_resource_id)

        posted_date = job.get('metadata', {}).get('newPostingDate')
        expires_date = job.get('metadata', {}).get('expiryDate')
        min_salary, max_salary = extract_salary_info(job)

        # Extract full job description text for TAFEP compliance checks
        description = job.get('description', '')
        
        # Build the MCF Job Link
        job_link = f"https://www.mycareersfuture.gov.sg/job/{job_id}"

        # 1. Insert raw data into the database FIRST
        try:
            cursor.execute('''
                INSERT OR IGNORE INTO jobs
                (job_id, title, employer_name, employer_uen, posted_date, expires_date, min_salary, max_salary, company_age_years)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (job_id, title, employer_name, employer_uen, posted_date, expires_date, min_salary, max_salary, company_age))
        except sqlite3.Error as e:
            print(f"Database error for job {job_id}: {e}")
            continue

        # --- 2. HEURISTICS ENGINE ---
        
        # Recycler Check: Count how many times this employer posted this exact title
        cursor.execute('''
            SELECT COUNT(job_id) FROM jobs 
            WHERE employer_uen = ? AND title = ?
        ''', (employer_uen, title))
        repost_count = cursor.fetchone()[0]

        # Calculate duration
        duration_days = None
        if posted_date and expires_date:
            try:
                posted = datetime.fromisoformat(posted_date.replace("Z", "+00:00"))
                expires = datetime.fromisoformat(expires_date.replace("Z", "+00:00"))
                duration_days = (expires - posted).days
            except ValueError:
                pass

        # --- NEW SALARY RULES ---
        # 1. High Salary Exemption: FCF 14-day rule doesn't apply to fixed monthly salaries >= $22,500
        is_exempt = min_salary is not None and min_salary >= 22500
        
        # 2. 2x Salary Violation: MOM states the max salary cannot exceed 2x the min salary
        is_salary_violation = (min_salary and max_salary and min_salary > 0 and max_salary > (2 * min_salary))

        # --- FLAG EVALUATION ---
        # Trigger 14-day flag ONLY if it's not exempt
        is_fcf_window = duration_days is not None and should_flag_duration(duration_days) and not is_exempt
        is_recycler = repost_count > 1

        # Escalate to LLM if ANY of our 3 rules trigger
        if is_fcf_window or is_recycler or is_salary_violation:
            analyze_with_groq(cursor, job_id, title, employer_name, employer_uen, duration_days, repost_count, min_salary, max_salary, is_salary_violation, description, company_age, job_link)

    conn.commit()
    conn.close()

def get_latest_acra_resource_id():
    """Returns the hardcoded active dataset ID since the Data.gov search API is unstable."""
    return "d_3f960c10fed6145404ca7b821f263b87"

def get_company_age_years(uen, resource_id):
    """Queries Data.gov.sg for the UEN to calculate company age."""
    if not uen or uen == 'Unknown' or not resource_id:
        return None
        
    acra_url = f"https://data.gov.sg/api/action/datastore_search?resource_id={resource_id}&q={uen}"
    
    try:
        response = requests.get(acra_url, timeout=5)
        if response.status_code == 200:
            data = response.json()
            records = data.get('result', {}).get('records', [])
            if records:
                incorp_date_str = records[0].get('uen_issue_date') or records[0].get('incorporation_date')
                if incorp_date_str:
                    incorp_date = datetime.strptime(incorp_date_str, "%Y-%m-%d")
                    age_days = (datetime.now() - incorp_date).days
                    return round(age_days / 365.25, 1)
        return None
    except requests.exceptions.RequestException:
        return None
    except Exception:
        return None

def analyze_with_groq(cursor, job_id, title, employer, uen, duration, repost_count, min_salary, max_salary, is_salary_violation, description, company_age, job_link):
    """Uses Groq to audit job postings for FCF and TAFEP violations."""
    groq_client = get_groq_client()
    if groq_client is None:
        print(f"Skipping Groq analysis for {title}: GROQ_API_KEY is not set.")
        return

    # Truncate description to 2500 characters to ensure clean token efficiency
    clean_desc = description[:2500] if description else "No description provided."

    prompt = f"""
    Analyze this job posting from the Singapore job market for TAFEP (Tripartite Alliance for Fair and Progressive Employment Practices) violations, discriminatory language, or 'hyper-tailored' ghost job requirements designed to favor a pre-selected candidate.

    Job Title: {title}
    Employer: {employer} (UEN: {uen})
    Company Age: {company_age if company_age is not None else 'Unknown'} years old
    Posting Duration: {duration if duration is not None else 'Unknown'} days
    Total Postings: This exact role has been posted {repost_count} time(s) by this employer.
    Salary Range: SGD {min_salary} to SGD {max_salary}
    2x Salary Rule Violation: {'YES' if is_salary_violation else 'No'}

    Job Description Excerpt:
    {clean_desc}

    Check for:
    1. Discriminatory language (age, gender, race, religion, or nationality preferences).
    2. Hyper-tailored, excessively niche requirements irrelevant to the core business designed to block local applicants.
    3. General compliance anomalies (duration/reposting/salary).

    Reply ONLY with a short, 1-sentence reason why it is flagged for a violation, or reply 'SAFE' if it complies with guidelines.
    """

    try:
        chat_completion = groq_client.chat.completions.create(
            messages=[
                {"role": "system", "content": "You are a strict Singapore MOM and TAFEP compliance auditor."},
                {"role": "user", "content": prompt}
            ],
            model="llama-3.1-8b-instant",
            temperature=0.1,
        )

        result = chat_completion.choices[0].message.content.strip()

        if result != "SAFE":
            final_reason = f"{result} [Link]({job_link})"
            print(f"FLAGGED [{uen}]: {title} - {result}")
            cursor.execute('INSERT INTO flags (job_id, flag_reason) VALUES (?, ?)', (job_id, final_reason))

    except Exception as e:
        print(f"Groq API Error: {e}")

if __name__ == "__main__":
    print("Starting MCF Scrape...")
    jobs_data = fetch_jobs(page=0, limit=20)
    
    if jobs_data:
        print(f"Fetched {len(jobs_data)} jobs. Analyzing...")
        store_jobs_and_analyze(jobs_data)
        print("Run complete.")
    else:
        print("No jobs found or error fetching.")