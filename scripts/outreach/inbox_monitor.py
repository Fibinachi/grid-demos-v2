"""Auto-monitor: checks inbox hourly for new replies. Logs findings to file."""
import imaplib, email, os, time, json
from datetime import datetime

LOG_FILE = "inbox_monitor_log.json"
KNOWN_FILE = "known_message_ids.txt"

def check_inbox():
    P = os.environ.get("EMAIL_PASSWORD")
    if not P: return "NO_PASSWORD"
    
    try:
        M = imaplib.IMAP4_SSL("imap.hostinger.com", 993, timeout=20)
        M.login("charles@columbiataxlawyer.com", P)
        M.select("INBOX")
        
        status, ids = M.search(None, "ALL")
        all_ids = ids[0].split() if ids[0] else []
        
        # Load known IDs
        known = set()
        try:
            with open(KNOWN_FILE) as f:
                known = set(line.strip() for line in f)
        except: pass
        
        new_messages = []
        for num in all_ids:
            if num.decode() if isinstance(num, bytes) else num not in known:
                status2, data = M.fetch(num, "(BODY.PEEK[HEADER.FIELDS (FROM SUBJECT DATE)])")
                if status2 != "OK": continue
                h = ""
                if len(data) > 1 and data[1] and isinstance(data[1][0], bytes):
                    h = data[1][0].decode("utf-8",errors="ignore")
                elif isinstance(data[0][1], bytes):
                    h = data[0][1].decode("utf-8",errors="ignore")
                
                # Skip auto-bounces
                if any(x in h.lower() for x in ["mailer-daemon","postmaster","mailchannels"]): continue
                
                from_v = subj_v = date_v = ""
                for line in h.split("\n"):
                    l = line.strip()
                    if l.startswith("From:"): from_v = l[5:].strip()
                    if l.startswith("Subject:"): subj_v = l[8:].strip()
                    if l.startswith("Date:"): date_v = l[5:].strip()
                
                if from_v and "charles@" not in from_v.lower():
                    new_messages.append({"from": from_v[:60], "subject": subj_v[:80], "date": date_v[:20], "id": str(num)})
        
        # Save known IDs
        with open(KNOWN_FILE, "w") as f:
            for n in all_ids:
                f.write((n.decode() if isinstance(n, bytes) else n) + "\n")
        
        M.logout()
        return new_messages
    except Exception as e:
        return "ERROR: " + str(e)[:60]

# Run once and report
results = check_inbox()
if isinstance(results, list):
    if results:
        print("[%s] %d NEW MESSAGES:" % (datetime.now().strftime("%H:%M"), len(results)))
        for m in results:
            print("  From: %s" % m["from"])
            print("  Subj: %s" % m["subject"])
            print()
        # Save to log
        log = {"timestamp": datetime.now().isoformat(), "new": len(results), "messages": results}
        try:
            with open(LOG_FILE) as f:
                history = json.load(f)
        except:
            history = []
        history.append(log)
        with open(LOG_FILE, "w") as f:
            json.dump(history, f, indent=2)
    else:
        print("[%s] No new messages" % datetime.now().strftime("%H:%M"))
else:
    print("Error: %s" % results)
