"""Check all email inbox status."""
import json, os

# 1. Gmail inbox classification
ic_path = "data/inbox_classification.json"
if os.path.exists(ic_path):
    d = json.load(open(ic_path))
    print("=== GMAIL INBOX CLASSIFICATION ===")
    for k, v in d.items():
        if isinstance(v, list):
            print(f"  {k}: {len(v)} messages")
        else:
            print(f"  {k}: {v}")
else:
    print("No inbox classification file")

# 2. Gmail responses log
gr_path = "data/gmail_responses.json"
if os.path.exists(gr_path):
    d = json.load(open(gr_path))
    if isinstance(d, list):
        print(f"\n=== GMAIL RESPONSES ({len(d)}) ===")
        for r in d[-5:]:
            print(f"  {r.get('subject','')[:50]:50s} from: {r.get('from','')[:30]:30s} {r.get('timestamp','')[:16]}")
    elif isinstance(d, dict):
        print(f"\n=== GMAIL RESPONSES ({len(d)} keys) ===")

# 3. Inbox monitor log
ml_path = "data/inbox_monitor_log.json"
if os.path.exists(ml_path):
    d = json.load(open(ml_path))
    if isinstance(d, list):
        print(f"\n=== INBOX MONITOR LOG ({len(d)} entries) ===")
        for r in d[-5:]:
            subj = r.get("subject", "")[:50]
            print(f"  {subj:50s} from: {str(r.get('from',''))[:30]:30s}")
    elif isinstance(d, dict):
        print(f"\n=== INBOX MONITOR LOG ===")
        for k in list(d.keys())[:5]:
            print(f"  {k}: {str(d[k])[:80]}")
        # Try nested
        for k, v in d.items():
            if isinstance(v, list):
                print(f"  {k}: {len(v)} items")
                for r in v[-3:]:
                    print(f"    {r.get('subject','')[:50]:50s} {r.get('from','')[:30]}")

# 4. Gmail seen IDs
seen_path = "logs/gmail_seen_ids.txt"
if os.path.exists(seen_path):
    with open(seen_path) as f:
        ids = [l.strip() for l in f if l.strip()]
    print(f"\n=== GMAIL SEEN IDS: {len(ids)} ===")

# 5. Hostinger responses
hr_path = "scripts/outreach/hostinger_responses.json"
if os.path.exists(hr_path):
    d = json.load(open(hr_path))
    print(f"\n=== HOSTINGER RESPONSES ===")
    if isinstance(d, list):
        print(f"  {len(d)} total")
        for r in d[-3:]:
            print(f"  {str(r.get('subject',''))[:50]:50s} {str(r.get('from',''))[:30]}")
    elif isinstance(d, dict):
        for k in list(d.keys())[:10]:
            print(f"  {k}: {str(d[k])[:80]}")

# 6. SES log
ses_log = "ses_logs"
if os.path.exists(ses_log):
    files = os.listdir(ses_log)
    print(f"\n=== SES LOGS: {len(files)} files ===")
