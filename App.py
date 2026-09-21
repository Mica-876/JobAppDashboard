import os
import re
import requests
import pandas as pd
import streamlit as st
from bs4 import BeautifulSoup
from datetime import date

DATA_FILE = "applications.csv"

# --- Storage Helpers ---
def load_data():
    if os.path.exists(DATA_FILE):
        return pd.read_csv(DATA_FILE)
    return pd.DataFrame(columns=[
        "Date Added", "Role Title", "Company", "Job URL", 
        "Summary / Excerpt", "Category", "Status", "Advisor Notes"
    ])

def save_data(df):
    df.to_csv(DATA_FILE, index=False)

# --- Web Scraper / Info Extractor ---
def extract_job_info(url):
    """Fetches the webpage and attempts to extract role title and description."""
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )
    }
    try:
        resp = requests.get(url, headers=headers, timeout=8)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        # 1. Extract Title (OpenGraph -> Twitter -> <title> -> <h1>)
        title = ""
        og_title = soup.find("meta", property="og:title") or soup.find("meta", attrs={"name": "twitter:title"})
        if og_title and og_title.get("content"):
            title = og_title["content"].strip()
        elif soup.title and soup.title.string:
            title = soup.title.string.strip()
        elif soup.find("h1"):
            title = soup.find("h1").get_text().strip()

        # Clean common job board suffixes (e.g., "SOC Analyst | LinkedIn" -> "SOC Analyst")
        title = re.split(r" [-|•] ", title)[0].strip()

        # 2. Extract Description / Summary
        description = ""
        og_desc = soup.find("meta", property="og:description") or soup.find("meta", attrs={"name": "description"})
        if og_desc and og_desc.get("content"):
            description = og_desc["content"].strip()
        else:
            # Fallback: take the first meaningful paragraph
            paragraphs = [p.get_text().strip() for p in soup.find_all("p") if len(p.get_text().strip()) > 60]
            description = paragraphs[0] if paragraphs else "No automatic description found."

        # Keep summary brief
        if len(description) > 280:
            description = description[:277] + "..."

        # 3. Simple Category Auto-Tagging
        combined_text = (title + " " + description).lower()
        if any(k in combined_text for k in ["soc", "security", "cyber", "analyst", "siem", "incident"]):
            category = "Cybersecurity / SOC"
        elif any(k in combined_text for k in ["network", "cisco", "switch", "routing", "noc", "firewall"]):
            category = "Infrastructure / Networks"
        elif any(k in combined_text for k in ["python", "software", "developer", "backend", "api"]):
            category = "Software / Python"
        elif any(k in combined_text for k in ["support", "helpdesk", "systems", "sysadmin"]):
            category = "Systems / IT Support"
        else:
            category = "Other"

        return title, description, category

    except Exception as e:
        st.warning(f"Could not automatically parse the link ({e}). You can enter details manually below.")
        return "", "", "Other"

# --- Page Setup ---
st.set_page_config(page_title="Security Role Tracker", layout="wide")
st.title("Job Application & Pipeline Tracker")

# ==========================================
# 1. QUICK INPUT: URL-FIRST INGESTION
# ==========================================
with st.expander("🔗 Add Job via URL (Auto-Extract)", expanded=True):
    col_url, col_comp = st.columns([3, 2])
    with col_url:
        input_url = st.text_input("Paste Job Link", placeholder="https://www.linkedin.com/jobs/view/...")
    with col_comp:
        input_company = st.text_input("Company Name", placeholder="e.g. CrowdStrike, Darktrace, Bank")

    if st.button("Fetch & Preview Details"):
        if not input_url.strip():
            st.error("Please paste a valid URL.")
        else:
            with st.spinner("Extracting job details from link..."):
                extracted_title, extracted_desc, auto_cat = extract_job_info(input_url.strip())
                st.session_state["preview_title"] = extracted_title
                st.session_state["preview_desc"] = extracted_desc
                st.session_state["preview_category"] = auto_cat
                st.session_state["preview_url"] = input_url.strip()
                st.session_state["preview_company"] = input_company.strip()

    # Confirmation stage after pulling
    if "preview_url" in st.session_state:
        st.markdown("---")
        st.caption("Review extracted data before saving:")
        c1, c2, c3 = st.columns([2, 2, 2])
        with c1:
            final_title = st.text_input("Role Title", value=st.session_state.get("preview_title", ""))
            final_company = st.text_input("Company", value=st.session_state.get("preview_company", ""))
        with c2:
            final_category = st.selectbox(
                "Category", 
                ["Cybersecurity / SOC", "Infrastructure / Networks", "Systems / IT Support", "Software / Python", "Other"],
                index=["Cybersecurity / SOC", "Infrastructure / Networks", "Systems / IT Support", "Software / Python", "Other"].index(
                    st.session_state.get("preview_category", "Other")
                )
            )
            final_status = st.selectbox("Status", ["Applied", "Reviewing", "Screening / Interview", "Declined / Rejected", "Offer"])
        with c3:
            final_desc = st.text_area("Summary / Description Excerpt", value=st.session_state.get("preview_desc", ""), height=110)

        if st.button("Confirm & Save to Dashboard", type="primary"):
            df = load_data()
            new_entry = pd.DataFrame([{
                "Date Added": str(date.today()),
                "Role Title": final_title,
                "Company": final_company,
                "Job URL": st.session_state["preview_url"],
                "Summary / Excerpt": final_desc,
                "Category": final_category,
                "Status": final_status,
                "Advisor Notes": ""
            }])
            updated_df = pd.concat([new_entry, df], ignore_index=True)
            save_data(updated_df)
            
            # Clear preview state
            del st.session_state["preview_url"]
            st.success("Application logged successfully!")
            st.rerun()

# ==========================================
# 2. ADVISOR BOARDVIEW & DETAILS
# ==========================================
st.markdown("---")
df = load_data()

# KPI Metrics Bar
kpi1, kpi2, kpi3, kpi4 = st.columns(4)
total_apps = len(df)
declined_apps = len(df[df["Status"] == "Declined / Rejected"])
active_apps = len(df[df["Status"].isin(["Applied", "Reviewing", "Screening / Interview"])])
interview_count = len(df[df["Status"] == "Screening / Interview"])

kpi1.metric("Total Jobs Logged", total_apps)
kpi2.metric("Active / Pipeline", active_apps)
kpi3.metric("Interviews", interview_count)
kpi4.metric("Declined / Rejected", declined_apps)

st.subheader("Applications Overview")

if df.empty:
    st.info("No applications logged yet. Paste a link above to get started.")
else:
    # Quick Status Filter
    status_filter = st.multiselect(
        "Filter by Status:", 
        options=df["Status"].unique().tolist(), 
        default=df["Status"].unique().tolist()
    )
    filtered_df = df[df["Status"].isin(status_filter)]

    # Interactive Table with single-row selection
    event = st.dataframe(
        filtered_df[["Date Added", "Role Title", "Company", "Category", "Status", "Job URL"]],
        use_container_width=True,
        hide_index=True,
        on_select="rerun",
        selection_mode="single-row",
        column_config={
            "Job URL": st.column_config.LinkColumn("Link", display_text="Open Job Ad")
        }
    )

    # Detail View on Click
    selected_rows = event.selection.rows
    if selected_rows:
        selected_index = filtered_df.index[selected_rows[0]]
        selected_job = df.loc[selected_index]

        st.markdown("### Job Detail & Advisor Review Panel")
        col_detail1, col_detail2 = st.columns([3, 2])

        with col_detail1:
            st.markdown(f"#### **{selected_job['Role Title']}** at **{selected_job['Company']}**")
            st.markdown(f"**Direct Link:** [{selected_job['Job URL']}]({selected_job['Job URL']})")
            st.markdown(f"**Category:** `{selected_job['Category']}` | **Date Added:** `{selected_job['Date Added']}`")
            st.info(f"**Job Summary / Requirements:**\n\n{selected_job['Summary / Excerpt']}")

        with col_detail2:
            st.markdown("#### Advisor Actions")
            new_status = st.selectbox(
                "Update Status:",
                ["Applied", "Reviewing", "Screening / Interview", "Declined / Rejected", "Offer"],
                index=["Applied", "Reviewing", "Screening / Interview", "Declined / Rejected", "Offer"].index(selected_job["Status"]),
                key=f"status_{selected_index}"
            )
            notes = st.text_area(
                "Advisor Notes / Feedback:",
                value=str(selected_job["Advisor Notes"]) if pd.notna(selected_job["Advisor Notes"]) else "",
                placeholder="e.g. Needs better SIEM framing; I'll apply for the SOC Tier 1 role at Company Y for you.",
                key=f"notes_{selected_index}"
            )

            if st.button("Update Record", key=f"save_{selected_index}"):
                df.at[selected_index, "Status"] = new_status
                df.at[selected_index, "Advisor Notes"] = notes
                save_data(df)
                st.success("Record updated!")
                st.rerun()