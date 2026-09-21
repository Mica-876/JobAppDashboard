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
    expected_cols = [
        "Date Added", "Role Title", "Company", "Job URL", 
        "Summary / Excerpt", "Category", "Status", "Advisor Notes", "Platform"
    ]
    if os.path.exists(DATA_FILE):
        try:
            df = pd.read_csv(DATA_FILE, dtype=str)
            for col in expected_cols:
                if col not in df.columns:
                    df[col] = ""
            df = df.fillna("")
            return df[expected_cols]
        except Exception:
            pass
    return pd.DataFrame(columns=expected_cols, dtype=str)

def save_data(df):
    df.to_csv(DATA_FILE, index=False)

def detect_platform(url):
    u = url.lower()
    if "linkedin.com" in u:
        return "LinkedIn"
    elif "indeed.com" in u:
        return "Indeed"
    elif "glassdoor" in u:
        return "Glassdoor"
    elif "totaljobs" in u:
        return "Totaljobs"
    elif "reed.co.uk" in u:
        return "Reed"
    elif u.strip():
        return "Direct / Web"
    return "Other"

# --- Smart Extractor with Fallback Detection ---
def try_extract_job_data(url):
    """
    Attempts to fetch and scrape job metadata.
    Returns: (success: bool, title: str, company: str, desc: str, cat: str)
    """
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "en-US,en;q=0.9",
    }
    
    try:
        resp = requests.get(url.strip(), headers=headers, timeout=6)
        if resp.status_code != 200:
            return False, "", "", "", "Other"
        
        soup = BeautifulSoup(resp.text, "html.parser")
        
        title = ""
        og_title = soup.find("meta", property="og:title") or soup.find("meta", attrs={"name": "twitter:title"})
        if og_title and og_title.get("content"):
            title = og_title["content"].strip()
        elif soup.title and soup.title.string:
            title = soup.title.string.strip()
        elif soup.find("h1"):
            title = soup.find("h1").get_text().strip()

        title = re.sub(r"(?i)\s*[-|•|–|:]\s*(linkedin|indeed|glassdoor|apply now|jobs|careers).*$", "", title).strip()

        blocked_signals = ["security verification", "just a moment", "sign in", "login", "robot or human", "access denied"]
        if any(b in title.lower() for b in blocked_signals) or len(title) < 3:
            return False, "", "", "", "Other"

        company = ""
        og_site = soup.find("meta", property="og:site_name")
        if og_site and og_site.get("content"):
            c_name = og_site["content"].strip()
            if c_name.lower() not in ["linkedin", "indeed", "glassdoor", "totaljobs", "reed"]:
                company = c_name

        desc = ""
        og_desc = soup.find("meta", property="og:description") or soup.find("meta", attrs={"name": "description"})
        if og_desc and og_desc.get("content"):
            desc = og_desc["content"].strip()
        else:
            paragraphs = [p.get_text().strip() for p in soup.find_all("p") if len(p.get_text().strip()) > 50]
            desc = paragraphs[0] if paragraphs else ""

        if len(desc) > 280:
            desc = desc[:277] + "..."

        combined_text = (title + " " + desc).lower()
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

        return True, title, company, desc, category

    except Exception:
        return False, "", "", "", "Other"

# --- Page Setup & Styling ---
st.set_page_config(
    page_title="Jobappdashboard",
    page_icon="🎯",
    layout="wide"
)

st.markdown("""
<style>
    div[data-testid="stVerticalBlock"] > div[data-testid="stVerticalBlock"] > div[data-testid="stContainer"] {
        padding: 0.75rem 0.9rem;
    }
</style>
""", unsafe_allow_html=True)

st.title("Jobappdashboard")

# ==============================================================================
# 1. ADD JOB (PERMANENT CARD CONTAINER)
# ==============================================================================
with st.container(border=True):
    st.markdown("#### ➕ Add a Job Application")
    col_input, col_action = st.columns([4, 1])
    with col_input:
        target_url = st.text_input(
            "Job Listing URL", 
            placeholder="Paste LinkedIn, Indeed, Glassdoor, or company careers link...", 
            key="input_target_url"
        )
    with col_action:
        st.write("")
        st.write("")
        fetch_btn = st.button("Fetch Details", use_container_width=True, type="secondary")

    if fetch_btn:
        if not target_url.strip():
            st.warning("Please paste a URL first.")
        else:
            with st.spinner("Checking and parsing link..."):
                success, title, comp, desc, cat = try_extract_job_data(target_url.strip())
                st.session_state["parsed_data"] = {
                    "success": success,
                    "url": target_url.strip(),
                    "title": title,
                    "company": comp,
                    "desc": desc,
                    "cat": cat,
                    "platform": detect_platform(target_url.strip())
                }

    if "parsed_data" in st.session_state:
        p_data = st.session_state["parsed_data"]
        st.markdown("---")

        if p_data["success"]:
            st.success(f"✅ Found details from **{p_data['platform']}**! Review and confirm below:")
        else:
            st.warning(
                f"⚠️ **Could not automatically extract info from {p_data['platform']}** (protected by login/bot detection).\n\n"
                "Please enter the title and company manually below:"
            )

        f1, f2 = st.columns(2)
        with f1:
            val_title = st.text_input("Role Title *", value=p_data.get("title", ""))
            val_company = st.text_input("Company Name *", value=p_data.get("company", ""))
            cat_options = [
                "Cybersecurity / SOC", 
                "Infrastructure / Networks", 
                "Systems / IT Support", 
                "Software / Python", 
                "Other"
            ]
            def_cat = p_data.get("cat", "Other")
            val_cat = st.selectbox("Category", cat_options, index=cat_options.index(def_cat) if def_cat in cat_options else 4)

        with f2:
            stat_options = ["Applied", "Reviewing", "Screening / Interview", "Declined / Rejected", "Offer"]
            val_status = st.selectbox("Status", stat_options, index=0)
            val_desc = st.text_area("Key Requirements / Notes", value=p_data.get("desc", ""), height=115)

        save_c1, save_c2 = st.columns([1, 4])
        with save_c1:
            if st.button("Save Job", type="primary", use_container_width=True):
                if not val_title.strip() or not val_company.strip():
                    st.error("Please provide both Role Title and Company Name.")
                else:
                    df = load_data()
                    new_job = pd.DataFrame([{
                        "Date Added": str(date.today()),
                        "Role Title": str(val_title).strip(),
                        "Company": str(val_company).strip(),
                        "Job URL": str(p_data["url"]).strip(),
                        "Summary / Excerpt": str(val_desc).strip(),
                        "Category": str(val_cat),
                        "Status": str(val_status),
                        "Advisor Notes": "",
                        "Platform": str(p_data["platform"])
                    }], dtype=str)
                    updated_df = pd.concat([new_job, df], ignore_index=True)
                    save_data(updated_df)
                    del st.session_state["parsed_data"]
                    st.success("Job application saved!")
                    st.rerun()
        with save_c2:
            if st.button("Cancel", type="secondary"):
                del st.session_state["parsed_data"]
                st.rerun()

# ==============================================================================
# 2. METRICS OVERVIEW
# ==============================================================================
df = load_data()

k1, k2, k3, k4, k5 = st.columns(5)
total_count = len(df)
active_count = len(df[df["Status"].isin(["Applied", "Reviewing"])])
interview_count = len(df[df["Status"] == "Screening / Interview"])
declined_count = len(df[df["Status"] == "Declined / Rejected"])
offer_count = len(df[df["Status"] == "Offer"])

k1.metric("Total Logged", total_count)
k2.metric("Active / Applied", active_count)
k3.metric("Interviews", interview_count)
k4.metric("Declined", declined_count)
k5.metric("Offers", offer_count)

st.markdown("---")

# ==============================================================================
# 3. SEARCH BAR & COMPACT TILE GRID
# ==============================================================================
if df.empty:
    st.info("No applications in pipeline. Paste a link above to start tracking.")
else:
    search_col, clear_col, _ = st.columns([3, 1, 3])
    with search_col:
        search_query = st.text_input(
            "🔍 Search Applications",
            placeholder="Type role, company, or status (e.g. Cisco, SOC, Declined)...",
            key="search_input_box"
        )
    with clear_col:
        st.write("")
        st.write("")
        if st.button("Clear Search", use_container_width=True):
            st.session_state["search_input_box"] = ""
            st.rerun()

    if search_query.strip():
        q = search_query.strip().lower()
        filtered_df = df[
            df["Role Title"].str.lower().str.contains(q, na=False) |
            df["Company"].str.lower().str.contains(q, na=False) |
            df["Status"].str.lower().str.contains(q, na=False) |
            df["Category"].str.lower().str.contains(q, na=False) |
            df["Platform"].str.lower().str.contains(q, na=False) |
            df["Advisor Notes"].str.lower().str.contains(q, na=False) |
            df["Summary / Excerpt"].str.lower().str.contains(q, na=False)
        ].reset_index()
    else:
        filtered_df = df.reset_index()

    st.caption(f"Showing **{len(filtered_df)}** of **{len(df)}** application cards")

    NUM_COLS = 3
    card_cols = st.columns(NUM_COLS)
    all_statuses = ["Applied", "Reviewing", "Screening / Interview", "Declined / Rejected", "Offer"]

    def get_status_color(status):
        if status == "Declined / Rejected":
            return "#ff4b4b"
        elif status == "Screening / Interview":
            return "#ffa421"
        elif status == "Offer":
            return "#21c354"
        return "#1f77b4"

    for i, row in filtered_df.iterrows():
        col_target = card_cols[i % NUM_COLS]
        original_idx = row["index"]
        color = get_status_color(row["Status"])

        with col_target:
            with st.container(border=True):
                # Header: Title, Company, Delete
                top_l, top_r = st.columns([4, 1])
                with top_l:
                    st.markdown(f"**{row['Role Title']}**")
                    st.caption(f"🏢 {row['Company']} · `{row.get('Platform', 'Direct')}`")
                with top_r:
                    if st.button("✕", key=f"del_btn_{original_idx}", help="Delete this application"):
                        st.session_state[f"confirm_del_{original_idx}"] = True
                        st.rerun()

                # Confirmation Box for Delete
                if st.session_state.get(f"confirm_del_{original_idx}", False):
                    st.warning("Are you sure you want to delete this job?")
                    c_yes, c_no = st.columns(2)
                    with c_yes:
                        if st.button("Yes, delete", key=f"confirm_yes_{original_idx}", type="primary"):
                            df = df.drop(index=original_idx).reset_index(drop=True)
                            save_data(df)
                            st.session_state.pop(f"confirm_del_{original_idx}", None)
                            st.rerun()
                    with c_no:
                        if st.button("Cancel", key=f"confirm_no_{original_idx}"):
                            st.session_state.pop(f"confirm_del_{original_idx}", None)
                            st.rerun()

                # Status pill & Date
                st.markdown(
                    f"<span style='background-color:{color}22; color:{color}; border: 1px solid {color}; padding:2px 8px; border-radius:4px; font-size:12px; font-weight:600;'>{row['Status']}</span>"
                    f" &nbsp; <span style='font-size:11px; color:gray;'>{row['Date Added']}</span>",
                    unsafe_allow_html=True
                )

                # Summary snippet
                if pd.notna(row["Summary / Excerpt"]) and str(row["Summary / Excerpt"]).strip():
                    short_desc = str(row["Summary / Excerpt"]).strip()
                    if len(short_desc) > 85:
                        short_desc = short_desc[:82] + "..."
                    st.markdown(f"<p style='font-size:12px; margin-top:6px; color:#444;'>{short_desc}</p>", unsafe_allow_html=True)

                # Link Button
                if pd.notna(row["Job URL"]) and str(row["Job URL"]).strip().startswith("http"):
                    st.link_button("🔗 View Posting", str(row["Job URL"]).strip(), use_container_width=True)

                # Advisor Drawer
                with st.expander("Advisor / Edit"):
                    cur_stat = row["Status"] if row["Status"] in all_statuses else "Applied"
                    new_stat = st.selectbox(
                        "Update Status", 
                        all_statuses, 
                        index=all_statuses.index(cur_stat), 
                        key=f"st_sel_{original_idx}"
                    )
                    
                    cur_notes = str(row["Advisor Notes"]) if pd.notna(row["Advisor Notes"]) else ""
                    new_notes = st.text_area(
                        "Advisor Notes / Actions Taken", 
                        value=cur_notes, 
                        key=f"note_txt_{original_idx}", 
                        height=70
                    )

                    if st.button("Save", key=f"save_btn_{original_idx}", type="primary"):
                        df.loc[original_idx, "Status"] = str(new_stat)
                        df.loc[original_idx, "Advisor Notes"] = str(new_notes).strip()
                        save_data(df)
                        st.success("Updated successfully!")
                        st.rerun()

    # Footer CSV download
    st.markdown("---")
    csv_bytes = df.to_csv(index=False).encode("utf-8")
    st.download_button(
        label="📥 Download Full Pipeline (CSV)",
        data=csv_bytes,
        file_name=f"job_tracker_{date.today()}.csv",
        mime="text/csv"
    )