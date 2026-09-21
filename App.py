import os
import pandas as pd
import streamlit as st
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
        return "Direct"
    return "Other"

# --- Page Config ---
st.set_page_config(
    page_title="Security Role Tracker",
    page_icon="🎯",
    layout="wide"
)

# Custom compact styling
st.markdown("""
<style>
    div[data-testid="stVerticalBlock"] > div[data-testid="stVerticalBlock"] > div[data-testid="stContainer"] {
        padding: 0.75rem 1rem;
    }
    .badge-status {
        display: inline-block;
        padding: 2px 8px;
        border-radius: 4px;
        font-size: 0.8rem;
        font-weight: 600;
    }
</style>
""", unsafe_allow_html=True)

st.title("🎯 Job Pipeline & Advisor Review")

# ==============================================================================
# 1. FAST SINGLE-STEP INPUT FORM
# ==============================================================================
with st.expander("➕ Log a New Job Application", expanded=False):
    with st.form("quick_add_form", clear_on_submit=True):
        f_c1, f_c2 = st.columns(2)
        with f_c1:
            inp_role = st.text_input("Role Title *", placeholder="e.g. Junior SOC Analyst / Systems Engineer")
            inp_company = st.text_input("Company Name *", placeholder="e.g. Darktrace / Cisco / NHS")
            inp_url = st.text_input("Job Ad Link *", placeholder="https://...")
            
        with f_c2:
            inp_cat = st.selectbox("Category", [
                "Cybersecurity / SOC", 
                "Infrastructure / Networks", 
                "Systems / IT Support", 
                "Software / Python", 
                "Other"
            ])
            inp_status = st.selectbox("Status", [
                "Applied", 
                "Reviewing", 
                "Screening / Interview", 
                "Declined / Rejected", 
                "Offer"
            ])
            inp_desc = st.text_area("Key Requirements / Short Notes", placeholder="e.g. Shift work, SIEM focus, Splunk, Windows Server", height=68)

        btn_submit = st.form_submit_button("Add to Board", type="primary")

        if btn_submit:
            if not inp_role.strip() or not inp_company.strip():
                st.error("Role Title and Company are required.")
            else:
                df = load_data()
                detected_plat = detect_platform(inp_url)
                new_row = pd.DataFrame([{
                    "Date Added": str(date.today()),
                    "Role Title": inp_role.strip(),
                    "Company": inp_company.strip(),
                    "Job URL": inp_url.strip(),
                    "Summary / Excerpt": inp_desc.strip(),
                    "Category": inp_cat,
                    "Status": inp_status,
                    "Advisor Notes": "",
                    "Platform": detected_plat
                }])
                updated_df = pd.concat([new_row, df], ignore_index=True)
                save_data(updated_df)
                st.success(f"Added **{inp_role}** at **{inp_company}**!")
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
# 3. COMPACT VISUAL TILE BOARD (3 COLUMNS)
# ==============================================================================
if df.empty:
    st.info("No applications logged yet. Click 'Log a New Job Application' above to add your first role.")
else:
    # Filter Controls
    flt_col1, flt_col2, flt_col3 = st.columns([2, 2, 2])
    with flt_col1:
        sel_status = st.multiselect("Filter Status", options=df["Status"].unique().tolist(), default=df["Status"].unique().tolist())
    with flt_col2:
        sel_cat = st.multiselect("Filter Category", options=df["Category"].unique().tolist(), default=df["Category"].unique().tolist())
    with flt_col3:
        plat_list = [p for p in df["Platform"].unique().tolist() if pd.notna(p) and p != ""]
        sel_plat = st.multiselect("Filter Platform", options=plat_list, default=plat_list)

    filtered_df = df[
        df["Status"].isin(sel_status) & 
        df["Category"].isin(sel_cat) &
        (df["Platform"].isin(sel_plat) if sel_plat else True)
    ].reset_index()

    st.caption(f"Showing **{len(filtered_df)}** roles")

    # Render in 3 responsive columns for a compact view
    NUM_COLS = 3
    card_cols = st.columns(NUM_COLS)
    all_statuses = ["Applied", "Reviewing", "Screening / Interview", "Declined / Rejected", "Offer"]

    # Status color tagging
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
                # Header: Role & Delete
                top_l, top_r = st.columns([4, 1])
                with top_l:
                    st.markdown(f"**{row['Role Title']}**")
                    st.caption(f"🏢 {row['Company']} · `{row.get('Platform', 'Web')}`")
                with top_r:
                    if st.button("✕", key=f"del_{original_idx}", help="Delete this application"):
                        df = df.drop(index=original_idx).reset_index(drop=True)
                        save_data(df)
                        st.rerun()

                # Status pill & Date
                st.markdown(
                    f"<span style='background-color:{color}22; color:{color}; border: 1px solid {color}; padding:2px 8px; border-radius:4px; font-size:12px; font-weight:600;'>{row['Status']}</span>"
                    f" &nbsp; <span style='font-size:11px; color:gray;'>{row['Date Added']}</span>",
                    unsafe_allow_html=True
                )

                # Summary snippet (if present)
                if pd.notna(row["Summary / Excerpt"]) and row["Summary / Excerpt"].strip():
                    short_desc = row["Summary / Excerpt"].strip()
                    if len(short_desc) > 90:
                        short_desc = short_desc[:87] + "..."
                    st.markdown(f"<p style='font-size:12px; margin-top:6px; color:#444;'>{short_desc}</p>", unsafe_allow_html=True)

                # Link Button
                if pd.notna(row["Job URL"]) and row["Job URL"].strip().startswith("http"):
                    st.link_button("🔗 View Ad", row["Job URL"], use_container_width=True)

                # Expandable Advisor & Status Drawer
                with st.expander("Advisor & Edit"):
                    cur_stat = row["Status"] if row["Status"] in all_statuses else "Applied"
                    new_stat = st.selectbox("Update Status", all_statuses, index=all_statuses.index(cur_stat), key=f"sel_st_{original_idx}")
                    
                    cur_notes = str(row["Advisor Notes"]) if pd.notna(row["Advisor Notes"]) else ""
                    new_notes = st.text_area("Advisor Notes / Actions Taken", value=cur_notes, key=f"note_in_{original_idx}", height=70)

                    if new_stat != row["Status"] or new_notes != cur_notes:
                        if st.button("Save", key=f"save_btn_{original_idx}", type="primary"):
                            df.at[original_idx, "Status"] = new_stat
                            df.at[original_idx, "Advisor Notes"] = new_notes.strip()
                            save_data(df)
                            st.rerun()

    # Footer CSV download
    st.markdown("---")
    csv_bytes = df.to_csv(index=False).encode("utf-8")
    st.download_button(
        label="📥 Download Data as CSV",
        data=csv_bytes,
        file_name=f"job_tracker_{date.today()}.csv",
        mime="text/csv"
    )