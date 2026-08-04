import sqlite3

def init_db():
    conn = sqlite3.connect('mcf_jobs.db')
    cursor = conn.cursor()
    
    # Table for raw job data
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS jobs (
        job_id TEXT PRIMARY KEY,
        title TEXT,
        employer_name TEXT,
        employer_uen TEXT,
        posted_date TEXT,
        expires_date TEXT,
        min_salary REAL,
        max_salary REAL,
        scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    
    # Table for flagged "ghost jobs"
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS flags (
        job_id TEXT,
        flag_reason TEXT,
        flagged_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(job_id) REFERENCES jobs(job_id)
    )
    ''')
    
    conn.commit()
    conn.close()
    print("Database initialized successfully.")

if __name__ == "__main__":
    init_db()