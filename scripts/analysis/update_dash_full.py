#!/usr/bin/env python3
"""Replace orchestrator dashboard with full category counts"""
code = '''
import streamlit as st
import sqlite3, os
from datetime import datetime

DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "churches.db")

st.set_page_config(page_title="GrantWizard Pipeline", layout="wide")
st.title("\U0001f4ca GrantWizard Pipeline")
st.caption(f"Orchestrator DB \u2022 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

def get_stats():
    conn = sqlite3.connect(DB)
    cur = conn.cursor()
    
    stats = {}
    queries = [
        ("total", "SELECT COUNT(*) FROM churches"),
        ("with_website", "SELECT COUNT(*) FROM churches WHERE website != ''"),
        ("with_email", "SELECT COUNT(*) FROM churches WHERE email != ''"),
        ("with_phone", "SELECT COUNT(*) FROM churches WHERE phone != ''"),
        ("with_pastor", "SELECT COUNT(*) FROM churches WHERE pastor_name != ''"),
        ("with_ein", "SELECT COUNT(*) FROM churches WHERE ein != ''"),
        ("with_affiliation", "SELECT COUNT(*) FROM churches WHERE denomination != '' AND denomination IS NOT NULL"),
        ("with_fb", "SELECT COUNT(*) FROM churches WHERE facebook != ''"),
        ("with_yt", "SELECT COUNT(*) FROM churches WHERE youtube != ''"),
        ("with_ig", "SELECT COUNT(*) FROM churches WHERE instagram != ''"),
        ("with_giving", "SELECT COUNT(*) FROM churches WHERE online_giving != '0' AND online_giving != ''"),
        ("with_attendance", "SELECT COUNT(*) FROM churches WHERE attendance != '0' AND attendance != ''"),
        ("with_youth", "SELECT COUNT(*) FROM churches WHERE has_youth != '0' AND has_youth != ''"),
        ("with_food_pantry", "SELECT COUNT(*) FROM churches WHERE has_food_pantry != '0' AND has_food_pantry != ''"),
        ("with_budget", "SELECT COUNT(*) FROM churches WHERE budget_amount != '0' AND budget_amount != ''"),
        ("from_irs", "SELECT COUNT(*) FROM churches WHERE source='irs'"),
        ("from_phase1", "SELECT COUNT(*) FROM churches WHERE source='phase1' OR source='scraped'"),
    ]
    
    for name, q in queries:
        cur.execute(q)
        stats[name] = cur.fetchone()[0]
    
    # Totals
    cur.execute("SELECT SUM(CAST(fb_followers AS INTEGER)) FROM churches")
    stats["fb_total"] = cur.fetchone()[0] or 0
    cur.execute("SELECT SUM(CAST(yt_subscribers AS INTEGER)) FROM churches")
    stats["yt_total"] = cur.fetchone()[0] or 0
    cur.execute("SELECT SUM(CAST(budget_amount AS INTEGER)) FROM churches WHERE CAST(budget_amount AS INTEGER) > 0")
    stats["budget_total"] = cur.fetchone()[0] or 0
    
    conn.close()
    return stats

s = get_stats()

# Row 1: Core counts
st.header("\U0001f4ca Core Data")
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Total Churches", f"{s['total']:,}")
c2.metric("IRS Records", f"{s['from_irs']:,}")
c3.metric("Phase 1+Scraped", f"{s['from_phase1']:,}")
c4.metric("With EIN", f"{s['with_ein']:,}")
c5.metric("With Website", f"{s['with_website']:,}")

# Row 2: Contact info
st.header("\U0001f4ec Contact Data")
c1, c2, c3, c4 = st.columns(4)
c1.metric("With Email", f"{s['with_email']:,}")
c2.metric("With Phone", f"{s['with_phone']:,}")
c3.metric("With Pastor Name", f"{s['with_pastor']:,}")
c4.metric("With Affiliation/Denom", f"{s['with_affiliation']:,}")

# Row 3: Social & Giving
st.header("\U0001f4f1 Social & Giving")
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Facebook Pages", f"{s['with_fb']:,}")
c2.metric("YouTube Channels", f"{s['with_yt']:,}")
c3.metric("Instagram", f"{s['with_ig']:,}")
c4.metric("Online Giving", f"{s['with_giving']:,}")
c5.metric("Budget Data", f"{s['with_budget']:,}")

c1, c2, c3 = st.columns(3)
c1.metric("Total FB Followers", f"{s['fb_total']:,}")
c2.metric("Total YT Subscribers", f"{s['yt_total']:,}")
c3.metric("Total Budget (found)", f"\${s['budget_total']:,}")

# Row 4: Ministries
st.header("\U0001f54a Ministries")
c1, c2, c3, c4 = st.columns(4)
c1.metric("Youth Ministry", f"{s['with_youth']:,}")
c2.metric("Food Pantry", f"{s['with_food_pantry']:,}")
c3.metric("Attendance Data", f"{s['with_attendance']:,}")
c4.metric("Service Times", "TBD")

# Row 5: Chunk progress from state file
import json
state_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "chunks", "state.json")
st.header("\U0001f5a5\ufe0f IRS Finder Queue")
if os.path.exists(state_path):
    with open(state_path) as f:
        state = json.load(f)
    pending = sum(1 for c in state["chunks"].values() if c["status"] == "pending")
    assigned = sum(1 for c in state["chunks"].values() if c["status"] == "assigned")
    completed = sum(1 for c in state["chunks"].values() if c["status"] == "completed")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Chunks", state["total_chunks"])
    c2.metric("Pending", pending)
    c3.metric("In Progress", assigned)
    c4.metric("Completed", completed)
    for wname, winfo in state["workers"].items():
        chunk_status = f"Chunk {winfo.get('chunk','none')}" if winfo.get('chunk') is not None else "Idle"
        st.caption(f"  {wname}: {chunk_status}")
else:
    st.caption("No chunk state file yet")

st.caption(f"\u2022 Updated {datetime.now().strftime('%H:%M:%S')}")
'''

with open("/home/ec2-user/grantwizard/dashboard.py", "w") as f:
    f.write(code)
print("Dashboard updated with full category counts")

import py_compile
py_compile.compile("/home/ec2-user/grantwizard/dashboard.py", doraise=True)
print("Syntax OK")
