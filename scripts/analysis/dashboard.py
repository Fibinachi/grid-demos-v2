"""
GrantWizard Pipeline Dashboard
===============================
Monitors 6 EC2 instances running church data enrichment.
Run: streamlit run dashboard.py
"""
import streamlit as st
import subprocess, json, os, csv, sqlite3
from datetime import datetime
from collections import Counter

st.set_page_config(page_title="GrantWizard Pipeline", layout="wide")
st.title("📊 GrantWizard Pipeline")

KEY = os.path.expanduser("~/.ssh/grantwizard-key.pem")
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# Current EC2 instances
INSTANCES = {
    "Phase 1 Chunk 0": ("18.118.169.15", "ec2_deep_scrape", "deep_profiles.csv"),
    "Phase 1 Chunk 1": ("18.188.95.190", "ec2_phones_scraper", "scraped_chunk_1.csv"),
    "Phase 1 Chunk 2": ("18.191.145.108", "ec2_phones_scraper", "scraped_chunk_2.csv"),
    "IRS Finder 2": ("3.138.187.55", "ec2_find_websites", "found_chunk_0.csv"),
    "IRS Finder 0": ("3.19.141.81", "ec2_find_websites", "found_chunk_0.csv"),
    "IRS Finder 1": ("18.191.24.204", "ec2_find_websites", "found_chunk_0.csv"),
}

def ssh(ip, cmd, timeout=8):
    full = ['ssh', '-o', 'StrictHostKeyChecking=no', '-o', 'ConnectTimeout=5',
            '-i', KEY, f'ubuntu@{ip}', cmd]
    try:
        r = subprocess.run(full, capture_output=True, text=True, timeout=timeout)
        return r.stdout.strip()
    except:
        return None

@st.cache_data(ttl=30)
def get_ec2_status(_instances):
    """Query all EC2 instances, cached for 30 seconds."""
    results = {}
    for name, (ip, proc, outfile) in _instances:
        ckpt = outfile.replace('.csv', '_ckpt.csv')
        cmd = (
            f"running=$(ps aux | grep '{proc}' | grep -v grep | grep python | wc -l); "
            f"main=$(ls ~/{outfile} 1>/dev/null 2>/dev/null && wc -l ~/{outfile} | cut -d' ' -f1 || echo 0); "
            f"ckpt=$(ls ~/{ckpt} 1>/dev/null 2>/dev/null && wc -l ~/{ckpt} | cut -d' ' -f1 || echo 0); "
            f"echo \"$running|$main|$ckpt\""
        )
        r = ssh(ip, cmd, timeout=8)
        if r and '|' in r:
            parts = r.split('|')
            results[name] = (parts[0].strip(), parts[1].strip(), parts[2].strip())
        else:
            results[name] = ('0', '0', '0')
    return results

def read_local_csv(path):
    try:
        with open(path, encoding="utf-8-sig") as f:
            return list(csv.DictReader(f))
    except:
        return []

def get_db_stats():
    try:
        conn = sqlite3.connect(os.path.join(SCRIPT_DIR, "churches.db"))
        cur = conn.cursor()
        total = cur.execute("SELECT COUNT(*) FROM churches").fetchone()[0]
        with_email = cur.execute("SELECT COUNT(*) FROM churches WHERE email != ''").fetchone()[0]
        with_pastor = cur.execute("SELECT COUNT(*) FROM churches WHERE pastor_name != ''").fetchone()[0]
        with_web = cur.execute("SELECT COUNT(*) FROM churches WHERE has_website = 1").fetchone()[0]
        conn.close()
        return total, with_email, with_pastor, with_web
    except:
        return 0, 0, 0, 0

st.sidebar.header("⏱ Controls")
if st.sidebar.button("🔄 Refresh Now"):
    st.rerun()
st.sidebar.caption("SSH queries to 6 EC2s - may take a few seconds")

# DB Summary
st.header("🗄️ Master Database")
db_total, db_email, db_pastor, db_web = get_db_stats()
c1, c2, c3, c4 = st.columns(4)
c1.metric("Total Churches", f"{db_total:,}")
c2.metric("With Pastor Name", f"{db_pastor:,}")
c3.metric("Has Website", f"{db_web:,}")
c4.metric("Has Email", f"{db_email:,}")

# EC2 Status with live progress
st.header("🖥️ EC2 Instance Status")

results = get_ec2_status(tuple(INSTANCES.items()))

total_records = 0
total_running = 0
cols = st.columns(3)
for i, (name, (ip, proc, outfile)) in enumerate(INSTANCES.items()):
    with cols[i % 3]:
        st.subheader(name)
        running, main_out, ckpt_out = results.get(name, ('0', '0', '0'))
        
        main_count = int(main_out) - 1 if main_out.isdigit() and int(main_out) > 0 else 0
        ckpt_count = int(ckpt_out) - 1 if ckpt_out.isdigit() and int(ckpt_out) > 0 else 0
        count = max(main_count, ckpt_count)
        total_records += count
        
        is_running = running.strip() != "0"
        if is_running:
            total_running += 1
        
        if is_running:
            st.success("🟢 Running")
            if count > 0:
                st.metric("Found", count)
            else:
                st.caption("Starting...")
        else:
            if count > 0:
                st.success(f"✅ Done - {count} records")
            else:
                st.warning("⏸️ Idle")

# Summary row
st.metric("Total EC2 Records Found", total_records)
st.caption(f"{total_running}/6 instances running | Refresh for live updates")

# Quick enrichment overview (if deep_profiles.csv exists locally)
dp_csv = os.path.join(SCRIPT_DIR, "deep_profiles.csv")
if os.path.exists(dp_csv):
    try:
        with open(dp_csv, encoding="utf-8") as f:
            dp = list(csv.DictReader(f))
        if dp:
            st.header("🌐 Deep Profile Enrichment")
            c1, c2, c3, c4, c5 = st.columns(5)
            with_affil = sum(1 for r in dp if r.get("affiliation", ""))
            with_fb = sum(1 for r in dp if r.get("fb_followers", "0").isdigit() and int(r.get("fb_followers", "0")) > 0)
            with_yt = sum(1 for r in dp if r.get("yt_subscribers", "0").isdigit() and int(r.get("yt_subscribers", "0")) > 0)
            with_budget = sum(1 for r in dp if r.get("budget_amount", "0").isdigit() and int(r.get("budget_amount", "0")) > 0)
            c1.metric("With Affiliation", f"{with_affil}")
            c2.metric("FB Followers Found", f"{with_fb}")
            c3.metric("YT Subscribers", f"{with_yt}")
            c4.metric("Budget Data", f"{with_budget}")
            c5.metric("Total Profiles", f"{len(dp)}")
    except:
        pass

# Email Templates
st.header("📧 Email Templates Ready")
temps = [
    "mustard_seed", "pentecostal", "social_gospel", "nondenom",
    "baptist", "churches_of_christ", "evangelical", "spirit_led", "progressive"
]
temp_cols = st.columns(3)
for i, t in enumerate(temps):
    with temp_cols[i % 3]:
        path = os.path.join(SCRIPT_DIR, f"email_template_{t}.md")
        if os.path.exists(path):
            st.success(f"✅ {t.replace('_',' ').title()}")

# Budget
st.header("💰 Budget")
cost_per_hr = 6 * 0.0116  # 6 t2.micro
budget = 25.0
hours_run = 2.5  # approx so far
spent = hours_run * cost_per_hr
remaining = budget - spent
hours_left = remaining / cost_per_hr if cost_per_hr > 0 else 0

st.metric("Budget Remaining", f"${remaining:.2f}")
st.progress(spent / budget, text=f"${spent:.2f} spent / ${budget:.0f} budget")
st.caption(f"~{hours_left:.0f} hours of runtime left at 6 instances")

# Footer
st.markdown("---")
st.caption(f"Last refreshed: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
try:
    # Check enrichment state on chunk 0
    state_data = ssh("3.16.31.223", "python3 -c 'import json; s=json.load(open(\"enriched_contacts_state_chunk0.json\")); items=list(s.get(\"found_emails\",{}).items())[:5]; [print(v.get(\"email\",\"?\"),v.get(\"domain\",\"?\"),v.get(\"source\",\"?\")) for k,v in items]'", timeout=8)
    if state_data:
        st.code(state_data)
except:
    st.info("No foundation emails yet")

# ─── FOOTER ───
st.divider()
st.caption(f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
st.caption("GrantWizard Pipeline Monitor v1.0")
