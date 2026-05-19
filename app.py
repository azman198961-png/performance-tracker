import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, timedelta
import json

# --- 1. CONFIG ---
st.set_page_config(page_title="Performance Pulse Tracker", layout="wide")
today = datetime.now().date()
today_str = str(today)

# --- 2. HELPER FUNCTIONS ---
def get_working_days(start_date, end_date):
    govt_holidays = [datetime(2026, 2, 21).date(), datetime(2026, 3, 26).date(), datetime(2026, 4, 14).date()]
    all_days = pd.date_range(start=start_date, end=end_date)
    working_days = [d for d in all_days if d.weekday() not in [4, 5] and d.date() not in govt_holidays]
    return len(working_days)

# --- 3. GOOGLE SHEETS CONNECTION ---
scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]

@st.cache_resource
def get_gspread_client():
    try:
        json_creds_str = st.secrets["gcp_service_account"]["json_creds"]
        creds_dict = json.loads(json_creds_str)
        creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n")
        creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
        return gspread.authorize(creds)
    except Exception as e:
        st.error(f"Authentication Error: {e}"); return None

client = get_gspread_client()
SHEET_ID = "1nWFF1uLd-Nwsxw7cXIeBDaVxLiC5360dvtHWrSyuoSM"

def get_ws(name):
    if not client: return None
    try: return client.open_by_key(SHEET_ID).worksheet(name)
    except Exception as e: st.error(f"Sheet '{name}' Error: {e}"); return None

# --- 4. NAVIGATION (লগইন ছাড়া সরাসরি এক্সেস) ---
page = st.sidebar.selectbox("Navigation", 
    ["Dashboard", "Plan Daily Tasks", "Update Task Status (EOD)", "QA Details", "Driver Onboarding", "Agent Training", "Improvement & Initiatives", "Suspension Re-Validation"])

# --- 5. PAGE: DASHBOARD (TARGETS + FILTERS) ---
if page == "Dashboard":
    st.header("📊 Performance Dashboard & Targets")
    
    # লোড ডাটা
    ws_qa = get_ws("qa"); ws_drivers = get_ws("drivers"); ws_training = get_ws("training"); ws_tasks = get_ws("tasks")
    q_df = pd.DataFrame(ws_qa.get_all_records()) if ws_qa else pd.DataFrame()
    d_df = pd.DataFrame(ws_drivers.get_all_records()) if ws_drivers else pd.DataFrame()
    t_df = pd.DataFrame(ws_training.get_all_records()) if ws_training else pd.DataFrame()
    tasks_df = pd.DataFrame(ws_tasks.get_all_records()) if ws_tasks else pd.DataFrame()

    # ডাটা ক্লিনিং
    for df in [q_df, d_df, t_df, tasks_df]:
        if not df.empty:
            df.columns = df.columns.str.strip()
            df['Date'] = pd.to_datetime(df['Date']).dt.date

    # --- ১. রিয়েল-টাইম টার্গেট সেকশন (সবসময় দেখা যাবে) ---
    st.subheader("🎯 Current Progress vs Targets")
    t_col1, t_col2, t_col3, t_col4 = st.columns(4)
    
    start_of_week = today - timedelta(days=(today.weekday() + 2) % 7)
    
    # ১.১ QA Audit (Daily Target: 12)
    today_qa = q_df[q_df['Date'] == today]['Audit Count'].sum() if not q_df.empty else 0
    t_col1.metric("Today's QA Audits", f"{int(today_qa)}/12", delta=int(today_qa)-12)
    
    # ১.২ Weekly Onboarding (Target: 10)
    week_dr = len(d_df[(d_df['Date'] >= start_of_week) & (d_df['Acc Status'] == 'Active')]) if not d_df.empty else 0
    t_col2.metric("Weekly Onboarding", f"{week_dr}/10", delta=week_dr-10)
    
    # ১.৩ Weekly Training (Target: 5)
    week_tr = len(t_df[t_df['Date'] >= start_of_week]) if not t_df.empty else 0
    t_col3.metric("Weekly Training", f"{week_tr}/5", delta=week_tr-5)
    
    # ১.৪ মাসিক কাজের দিন
    m_days = get_working_days(today.replace(day=1), today)
    t_col4.metric("Working Days (Month)", f"{m_days} Days")

    st.divider()

    # --- ২. ফিল্টার করা রিপোর্ট সেকশন ---
    st.subheader("🔍 Historical Report & Analytics")
    report_type = st.radio("Select View:", ["Daily", "Weekly", "Monthly"], horizontal=True)

    if report_type == "Daily":
        q_filtered = q_df[q_df['Date'] == today] if not q_df.empty else pd.DataFrame()
        d_filtered = d_df[d_df['Date'] == today] if not d_df.empty else pd.DataFrame()
        t_filtered = t_df[t_df['Date'] == today] if not t_df.empty else pd.DataFrame()
        suffix = "Today"
    elif report_type == "Weekly":
        q_filtered = q_df[q_df['Date'] >= start_of_week] if not q_df.empty else pd.DataFrame()
        d_filtered = d_df[d_df['Date'] >= start_of_week] if not d_df.empty else pd.DataFrame()
        t_filtered = t_df[t_df['Date'] >= start_of_week] if not t_df.empty else pd.DataFrame()
        suffix = "This Week"
    else: # Monthly
        start_of_month = today.replace(day=1)
        q_filtered = q_df[q_df['Date'] >= start_of_month] if not q_df.empty else pd.DataFrame()
        d_filtered = d_df[d_df['Date'] >= start_of_month] if not d_df.empty else pd.DataFrame()
        t_filtered = t_df[t_df['Date'] >= start_of_month] if not t_df.empty else pd.DataFrame()
        suffix = "This Month"

    # ফিল্টারড মেট্রিক্স
    f_col1, f_col2, f_col3, f_col4 = st.columns(4)
    f_col1.metric(f"Total Audits", int(q_filtered['Audit Count'].sum()) if not q_filtered.empty else 0)
    f_col2.metric(f"Total Onboarded", len(d_filtered[d_filtered['Acc Status'] == 'Active']) if not d_filtered.empty else 0)
    f_col3.metric(f"Total Training", len(t_filtered) if not t_filtered.empty else 0)
    
    if not q_filtered.empty:
        q_filtered['Acc_Num'] = pd.to_numeric(q_filtered['Accuracy %'].astype(str).str.rstrip('%'), errors='coerce')
        avg_acc = q_filtered['Acc_Num'].mean()
        f_col4.metric("Avg Accuracy", f"{avg_acc:.1f}%")
    else:
        f_col4.metric("Avg Accuracy", "0%")

    # --- ৩. ভিজ্যুয়াল চার্ট ---
    c1, c2 = st.columns(2)
    with c1:
        st.write(f"📈 **Audit Trend ({suffix})**")
        if not q_filtered.empty:
            chart_data = q_filtered.groupby('Date')['Audit Count'].sum()
            st.line_chart(chart_data)
    with c2:
        st.write(f"🏢 **Channel Distribution ({suffix})**")
        if not q_filtered.empty:
            st.bar_chart(q_filtered.groupby('Channel')['Audit Count'].sum())

    # --- ৪. ডিটেইলড টেবিল ---
    with st.expander("View Detailed Records"):
        tab_q, tab_t, tab_d = st.tabs(["QA Logs", "Training", "Drivers"])
        tab_q.dataframe(q_filtered, use_container_width=True)
        tab_t.dataframe(t_filtered, use_container_width=True)
        tab_d.dataframe(d_filtered, use_container_width=True)

# --- 6. PAGE: AGENT TRAINING ---
elif page == "Agent Training":
    st.header("🎓 Agent Training Management")
    ws = get_ws("training")
    
    tab1, tab2 = st.tabs(["➕ Add New Training", "🔄 Update Post-Training Score"])
    
    with tab1:
        with st.form("new_training", clear_on_submit=True):
            c1, c2 = st.columns(2)
            a_name = c1.text_input("Agent Name")
            eid = c2.text_input("Agent EID")
            chan = st.selectbox("Channel", ["Inbound", "Live Chat", "Email", "Complaint"])
            topic = st.text_area("Training Topic")
            pre_score = st.number_input("QA Score Before Training (%)", 0.0, 100.0, 0.0)
            if st.form_submit_button("Save Training Session"):
                ws.append_row([today_str, a_name, eid, chan, topic, pre_score, "N/A"])
                st.success("Training Logged!")

    with tab2:
        if ws:
            data = ws.get_all_records()
            if data:
                df = pd.DataFrame(data)
                pending = df[df['Score After'] == "N/A"]
                for idx, row in pending.iterrows():
                    with st.expander(f"Update Score: {row['Agent Name']} ({row['Topic']})"):
                        new_score = st.number_input("QA Score After Training (%)", 0.0, 100.0, key=f"tr_{idx}")
                        if st.button("Confirm Update", key=f"btn_tr_{idx}"):
                            ws.update_cell(idx + 2, 7, new_score) # Column 7 is Score After
                            st.success("Score Updated!"); st.rerun()

# --- 7. PAGE: IMPROVEMENT & INITIATIVES ---
elif page == "Improvement & Initiatives":
    st.header("💡 Process Improvement & Initiatives")
    with st.form("init_form", clear_on_submit=True):
        p_name = st.text_input("Proposal Name")
        desc = st.text_area("Description")
        impact = st.selectbox("Expected Impact", ["Efficiency Boost", "Quality Improvement", "Cost Reduction", "Agent Satisfaction"])
        timeline = st.text_input("Possible Timeline (e.g., Next 2 Weeks)")
        if st.form_submit_button("Submit Initiative"):
            ws = get_ws("initiatives")
            if ws:
                ws.append_row([today_str, p_name, desc, impact, timeline])
                st.success("Initiative Saved!")
                
# --- 8. PAGE: PLAN DAILY TASKS ---
elif page == "Plan Daily Tasks":
    st.header("📝 Morning Planning")
    with st.form("plan", clear_on_submit=True):
        cat = st.selectbox("Category", ["QA Audit", "Rental Driver Onboarding", "Agent Training", "Initiatives", "Suspension", "Adhoc"])
        name = st.text_input("Task Name")
        ph = st.number_input("Planned Hours", 0.5, 12.0, 1.0)
        if st.form_submit_button("Add to Plan"):
            ws = get_ws("tasks")
            if ws:
                ws.append_row([today_str, cat, name, ph, 0.0, "Planned", ""])
                st.success("Task added!")
                st.rerun()

# --- 9. PAGE: UPDATE TASK STATUS (EOD) ---
elif page == "Update Task Status (EOD)":
    st.header("✅ End of Day Update")
    ws = get_ws("tasks")
    if ws:
        data = ws.get_all_records()
        if data:
            df = pd.DataFrame(data)
            df.columns = df.columns.str.strip()
            mask = (df['Date'].astype(str) == today_str) & (df['Status'] == "Planned")
            pending = df[mask]
            if not pending.empty:
                for idx, row in pending.iterrows():
                    with st.expander(f"Update: {row['Task Name']}"):
                        row_num = idx + 2
                        ah = st.number_input("Actual Hours", 0.0, 15.0, float(row['Planned Hours']), key=f"h{idx}")
                        stat = st.selectbox("Status", ["Completed", "Incompleted"], key=f"s{idx}")
                        if st.button("Save Update", key=f"b{idx}"):
                            ws.update_cell(row_num, 5, ah)
                            ws.update_cell(row_num, 6, stat)
                            st.success("Updated!")
                            st.rerun()
            else: st.info("No pending tasks today.")

# --- 10. PAGE: QA DETAILS ---
elif page == "QA Details":
    st.header("🔍 QA Audit Logs")
    with st.form("qa_log", clear_on_submit=True):
        channel = st.selectbox("Channel", ["Inbound", "Live Chat", "Report Issue & Email", "Complaint Management"])
        cnt = st.number_input("Audit Count", min_value=1, step=1)
        err = st.number_input("Critical Errors", min_value=0, step=1)
        if st.form_submit_button("Log QA Data"):
            ws = get_ws("qa")
            if ws:
                acc = f"{((cnt-err)/cnt)*100:.1f}%"
                hrs = round((cnt * 15) / 60, 2)
                ws.append_row([today_str, channel, cnt, err, acc, hrs])
                st.success(f"QA Saved for {channel}!")

# --- 11. PAGE: DRIVER ONBOARDING ---
elif page == "Driver Onboarding":
    st.header("🚗 Driver Onboarding & Management")
    ws = get_ws("drivers")
    
    st.subheader("Step 1: New Driver Entry")
    with st.form("dr_new", clear_on_submit=True):
        c1, c2, c3 = st.columns(3)
        n = c1.text_input("Name")
        p = c2.text_input("Phone")
        city = c3.selectbox("City", ["Dhaka", "Chittagong", "Sylhet"])
        c4, c5, c6 = st.columns(3)
        interested = c4.selectbox("Interested?", ["Yes", "No"])
        doc_stat = c5.selectbox("Doc Status", ["Pending", "Partially Submitted", "Submitted"])
        acc_stat = c6.selectbox("Acc Status", ["Inactive", "Active"])
        if st.form_submit_button("Submit"):
            if ws and n and p:
                ws.append_row([today_str, n, p, city, interested, doc_stat, acc_stat, "No"])
                st.success("New driver entry saved!")
                st.rerun()

    st.divider()
    st.subheader("Step 2: Update Existing Status")
    if ws:
        data = ws.get_all_records()
        if data:
            df = pd.DataFrame(data)
            df.columns = df.columns.str.strip()
            pending = df[df['First Trip'] != "Yes"]
            for idx, row in pending.iterrows():
                row_num = idx + 2
                with st.expander(f"Update: {row['Name']} ({row['Phone']})"):
                    u1, u2, u3 = st.columns(3)
                    new_doc = u1.selectbox("Doc Status", ["Pending", "Partially Submitted", "Submitted"], key=f"d{idx}")
                    new_acc = u2.selectbox("Acc Status", ["Inactive", "Active"], key=f"a{idx}")
                    trip = u3.checkbox("First Trip Completed?", key=f"t{idx}")
                    if st.button("Confirm Update", key=f"btn{idx}"):
                        ws.update_cell(row_num, 6, new_doc)
                        ws.update_cell(row_num, 7, new_acc)
                        if trip: ws.update_cell(row_num, 8, "Yes")
                        st.success("Updated!")
                        st.rerun()

# --- 12. PAGE: SUSPENSION RE-VALIDATION ---
elif page == "Suspension Re-Validation":
    st.header("⚠️ Suspension Re-Validation")
    up = st.file_uploader("Upload CSV/Excel", type=["csv", "xlsx"])
    if up:
        raw = pd.read_excel(up) if up.name.endswith('xlsx') else pd.read_csv(up)
        if st.button("Push Data to Sheet"):
            ws = get_ws("revalidation")
            if ws:
                ws.append_rows(raw.fillna("").values.tolist())
                st.success("Suspension data updated!")
