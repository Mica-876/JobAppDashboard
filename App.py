import os
import re
import requests
import pandas as pd
import streamlit as st
from bs4 import BeautifulSoup
from datetime import date

DATA_FILE = "applications.csv"

# --- Storage Layer ---
def load_data():
    if os.path.exists(DATA_FILE):
        try:
            df = pd.read_csv(DATA_FILE)
            expected_cols = [
                "Date Added", "Role Title", "Company", "Job URL", 
                "Summary / Excerpt", "Category", "Status", "Advisor Notes", "Platform"
            ]
            for col in expected_cols:
                if col not in df.columns:
                    df[col] = ""
            return df
        except Exception:
            pass
    return pd.DataFrame(columns=[
        "Date Added", "Role Title", "Company", "Job URL", 
        "Summary / Excerpt", "Category", "Status", "Advisor Notes", "Platform"
    ])

def save_data(df):
    df.to_csv(DATA_FILE, index=False)

# --- Multi-Platform Web Scraper ---
def extract_job_info(url):
    """
    Parses LinkedIn, Indeed, Glassdoor, and generic career pages
    to extract role titles, companies, excerpts, and job platforms.
    """
    clean_url = url.strip()
    platform = "Direct / Other"
    
    if "linkedin.com" in clean_url:
        platform = "LinkedIn"
    elif "indeed.com" in clean_url:
        platform = "Indeed"
    elif "glassdoor." in clean_url:
        platform = "Glassdoor"

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/126.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "en-US,en;q=0.9",
    }

    try:
        resp = requests.get(clean_url, headers=headers, timeout=10)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        # 1. Title Extraction
        title = ""
        og_title = soup.find("meta", property="og:title") or soup.find("meta", attrs={"name": "twitter:title"})
        if og_title and og_title.get("content"):
            title = og_title["content"].strip()
        elif soup.title and soup.title.string:
            title = soup.title.string.strip()
        elif soup.find("h1"):
            title = soup.find("h1").get_text().strip()

        # Clean site suffixes from titles
        title = re.sub(r"(?i)\s*[-|•|–|:]\s*(linkedin|indeed|glassdoor|apply now|jobs).*$", "", title).strip()

        # 2. Company Extraction Fallbacks
        inferred_company = ""
        og_site_name = soup.find("meta", property="og:site_name")
        if og_site_name and og_site_name.get("content"):
            site_val = og_site_name["content"].strip()
            if site_val.lower() not in ["linkedin", "indeed", "glassdoor"]:
                inferred_company = site_val

        # 3. Description Extraction
        description = ""
        og_desc = soup.find("meta", property="og:description") or soup.find("meta", attrs={"name": "description"})
        if og_desc and og_desc.get("content"):
            description = og_desc["content"].strip()
        else:
            paragraphs = [p.get_text().strip() for p in soup.find_all("p") if len(p.get_text().strip()) > 50]
            description = paragraphs[0] if paragraphs else "No automated summary extracted."

        if len(description) > 280:
            description = description[:277] + "..."

        # 4. Auto Categorization
        combined_text = (title + " " + description).lower()
        if any(k in combined_text for k in ["soc", "security", "cyber", "analyst", "siem", "incident", "vulnerability", "infosec"]):
            category = "Cybersecurity / SOC"
        elif any(k in combined_text for k in ["network", "cisco", "switch", "routing", "noc", "firewall", "infrastructure"]):
            category = "Infrastructure / Networks"
        elif any(k in combined_text for k in ["python", "software", "developer", "backend", "api", "automation"]):
            category = "Software / Python"
        elif any(k in combined_text for k in ["support", "helpdesk", "systems", "sysadmin", "desktop", "it support"]):
            category = "Systems / IT Support"
        else:
            category = "Other"

        return title, inferred_company, description, category, platform

    except Exception as e:
        return "", "", f"Could not auto-extract details ({str(e)}). Please enter manually.", "Other", platform

# --- Page Config ---
st.set_page_config(
    page_title="Job Pipeline Hub",
    page_icon="🎯",
    layout="wide"
)

st.title("🎯 Job Tracker & Advisor Review Hub")
st.caption("Track, review, and manage applications across LinkedIn, Indeed, Glassdoor, and company portals.")

# ==============================================================================
# 1. ADD NEW APPLICATION
# ==============================================================================
with st.expander("➕ Add New Application (Paste URL)", expanded=False):
    c_link, c_btn = st.columns([4, 1])
    with c_link:
        raw_url = st.text_input("Paste Job Link (LinkedIn, Glassdoor, Indeed, etc.)", placeholder="https://...")
    with c_btn:
        st.write("")
        st.write("")
        parse_clicked = st.button("Parse Link", use_container_width=True)

    if parse_clicked:
        if not raw_url.strip():
            st.warning("Please enter a link first.")
        else:
            with st.spinner("Extracting posting details..."):
                t, comp, d, cat, plat = extract_job_info(raw_url.strip())
                st.session_state["p_title"] = t
                st.session_state["p_comp"] = comp
                st.session_state["p_desc"] = d
                st.session_state["p_cat"] = cat
                st.session_state["p_plat"] = plat
                st.session_state["p_url"] = raw_url.strip()

    if "p_url" in st.session_state:
        st.markdown("---")
        st.markdown(f"**Detected Platform:** `{st.session_state.get('p_plat', 'Web')}`")
        
        col1, col2 = st.columns(2)
        with col1:
            inp_title = st.text_input("Role Title", value=st.session_state.get("p_title", ""))
            inp_company = st.text_input("Company Name", value=st.session_state.get("p_comp", ""))
            cat_list = ["Cybersecurity / SOC", "Infrastructure / Networks", "Systems / IT Support", "Software / Python", "Other"]
            cur_cat = st.session_state.get("p_cat", "Other")
            inp_cat = st.selectbox("Category", cat_list, index=cat_list.index(cur_cat) if cur_cat in cat_list else 4)

        with col2:
            stat_list = ["Applied", "Reviewing", "Screening / Interview", "Declined / Rejected", "Offer"]
            inp_status = st.selectbox("Status", stat_list, index=0)
            inp_desc = st.text_area("Job Summary / Requirements Excerpt", value=st.session_state.get("p_desc", ""), height=115)

        if st.button("Confirm & Save Application", type="primary"):
            if not inp_title.strip() or not inp_company.strip():
                st.error("Both Role Title and Company are required.")
            else:
                df = load_data()
                new_row = pd.DataFrame([{
                    "Date Added": str(date.today()),
                    "Role Title": inp_title.strip(),
                    "Company": inp_company.strip(),
                    "Job URL": st.session_state["p_url"],
                    "Summary / Excerpt": inp_desc.strip(),
                    "Category": inp_cat,
                    "Status": inp_status,
                    "Advisor Notes": "",
                    "Platform": st.session_state.get("p_plat", "Direct")
                }])
                updated_df = pd.concat([new_row, df], ignore_index=True)
                save_data(updated_df)
                del st.session_state["p_url"]
                st.success(f"Added {inp_title} at {inp_company}!")
                st.rerun()

# ==============================================================================
# 2. KPI METRICS
# ==============================================================================
df = load_data()

k1, k2, k3, k4, k5 = st.columns(5)
total_count = len(df)
active_count = len(df[df["Status"].isin(["Applied", "Reviewing"])])
interview_count = len(df[df["Status"] == "Screening / Interview"])
declined_count = len(df[df["Status"] == "Declined / Rejected"])
offer_count = len(df[df["Status"] == "Offer"])

k1.metric("Total Tracked", total_count)
k2.metric("Active / Applied", active_count)
k3.metric("Interviews", interview_count)
k4.metric("Declined", declined_count)
k5.metric("Offers", offer_count)

st.markdown("---")

# ==============================================================================
# 3. VISUAL TILE BOARD
# ==============================================================================
if df.empty:
    st.info("No applications logged yet. Paste a link above to add your first job card.")
else:
    # Filter Bar
    f_col1, f_col2, f_col3 = st.columns([2, 2, 2])
    with f_col1:
        selected_status = st.multiselect(
            "Filter by Status", 
            options=df["Status"].unique().tolist(), 
            default=df["Status"].unique().tolist()
        )
    with f_col2:
        selected_cat = st.multiselect(
            "Filter by Category", 
            options=df["Category"].unique().tolist(), 
            default=df["Category"].unique().tolist()
        )
    with f_col3:
        platform_options = [p for p in df["Platform"].unique().tolist() if pd.notna(p) and p != ""]
        selected_plat = st.multiselect(
            "Filter by Platform",
            options=platform_options,
            default=platform_options
        )

    # Filter records
    filtered_df = df[
        df["Status"].isin(selected_status) & 
        df["Category"].isin(selected_cat) &
        (df["Platform"].isin(selected_plat) if selected_plat else True)
    ].reset_index()

    st.subheader(f"Showing {len(filtered_df)} Job Card{'s' if len(filtered_df) != 1 else ''}")

    # Display 2 columns of rich cards/tiles
    cols = st.columns(2)
    statuses = ["Applied", "Reviewing", "Screening / Interview", "Declined / Rejected", "Offer"]

    for i, row in filtered_df.iterrows():
        col_idx = i % 2
        original_idx = row["index"]

        with cols[col_idx]:
            with st.container(border=True):
                # Header row inside card: Title + Direct Delete
                header_left, header_right = st.columns([4, 1])
                with header_left:
                    st.markdown(f"### {row['Role Title']}")
                    st.markdown(f"🏢 **{row['Company']}** · `{row.get('Platform', 'Web')}`")
                with header_right:
                    if st.button("🗑️ Delete", key=f"del_{original_idx}", help="Permanently remove this job"):
                        df = df.drop(index=original_idx).reset_index(drop=True)
                        save_data(df)
                        st.rerun()

                # Tags & Metadata
                st.caption(f"📅 Added: {row['Date Added']} | 🏷️ Category: {row['Category']}")
                
                # Excerpt/Summary
                if pd.notna(row["Summary / Excerpt"]) and row["Summary / Excerpt"]:
                    st.info(row["Summary / Excerpt"])

                # Links and Quick Status Update
                c_status, c_link = st.columns([3, 2])
                with c_status:
                    cur_stat = row["Status"] if row["Status"] in statuses else "Applied"
                    new_stat = st.selectbox(
                        "Status", 
                        statuses, 
                        index=statuses.index(cur_stat), 
                        key=f"status_select_{original_idx}"
                    )
                with c_link:
                    st.write("")
                    st.write("")
                    st.link_button("🌐 Open Job Link", row["Job URL"], use_container_width=True)

                # Advisor Notes / Feedback Section
                cur_notes = str(row["Advisor Notes"]) if pd.notna(row["Advisor Notes"]) else ""
                new_notes = st.text_area(
                    "Advisor Notes / Actions Taken:", 
                    value=cur_notes,
                    placeholder="e.g. Needs SOC 1 phrasing; applying on their behalf to Partner Co.",
                    key=f"notes_input_{original_idx}",
                    height=70
                )

                # Save updates button if advisor or user changed status/notes
                if new_stat != row["Status"] or new_notes != cur_notes:
                    if st.button("💾 Save Card Changes", key=f"save_card_{original_idx}", type="secondary"):
                        df.at[original_idx, "Status"] = new_stat
                        df.at[original_idx, "Advisor Notes"] = new_notes.strip()
                        save_data(df)
                        st.success("Card updated!")
                        st.rerun()

    # CSV Backup Export at bottom
    st.markdown("---")
    csv_bytes = df.to_csv(index=False).encode("utf-8")
    st.download_button(
        label="📥 Download Full Pipeline as CSV",
        data=csv_bytes,
        file_name=f"job_tracker_{date.today()}.csv",
        mime="text/csv"
    )