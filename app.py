import streamlit as st
import pandas as pd
import sqlite3

# Configure the page
st.set_page_config(page_title="MrSherlock Dashboard", page_icon="🕵️‍♂️", layout="wide")
st.title("🕵️‍♂️ MrSherlock: MCF Ghost Job Tracker")
st.markdown("A dashboard to visualize flagged job postings from MyCareersFuture.")

# Function to load data from SQLite
@st.cache_data
def load_data():
    try:
        conn = sqlite3.connect('mcf_jobs.db')
        query = """
            SELECT 
                j.employer_name AS 'Employer',
                j.company_age_years AS 'Age (Yrs)', -- NEW COLUMN PULL 
                j.title AS 'Job Title', 
                f.flag_reason AS 'Reason Flagged', 
                j.posted_date AS 'Posted Date', 
                j.expires_date AS 'Expires Date'
            FROM flags f 
            JOIN jobs j ON f.job_id = j.job_id
            ORDER BY j.posted_date DESC
        """
        df = pd.read_sql_query(query, conn)
        conn.close()
        return df
    except sqlite3.Error as e:
        st.error(f"Database error: {e}")
        return pd.DataFrame() # Return empty df on error

# Load the data
df = load_data()

# --- Sidebar Filtering ---
st.sidebar.header("Filter Results")

if not df.empty:
    # Create a multiselect filter for Employers
    employers = df['Employer'].unique().tolist()
    selected_employers = st.sidebar.multiselect("Filter by Employer", employers, default=[])
    
    # Apply the filter if an employer is selected
    if selected_employers:
        filtered_df = df[df['Employer'].isin(selected_employers)]
    else:
        filtered_df = df
        
    # --- Main Display ---
    st.subheader(f"Showing {len(filtered_df)} Flagged Jobs")
    
    # Display the interactive dataframe
    # st.dataframe provides sorting, resizing, and scrolling out of the box
    # Display the interactive dataframe with column configuration
    st.dataframe(
        filtered_df, 
        use_container_width=True, 
        hide_index=True,
        column_config={
            "Age (Yrs)": st.column_config.NumberColumn(
            "Age (Yrs)",
                help="The age of the company in years, based on ACRA registration data.",
                format="%.1f"
            ),
            "Reason Flagged": st.column_config.MarkdownColumn(
                "Reason Flagged",
                help="The reason Groq flagged this job. Click the link to view the original posting."
            )
        }
    )
    
    # Add a quick summary metric
    st.sidebar.markdown("---")
    st.sidebar.metric("Total Flagged Jobs", len(df))
    
else:
    st.warning("No flagged jobs found in the database. Run the scraper first.")