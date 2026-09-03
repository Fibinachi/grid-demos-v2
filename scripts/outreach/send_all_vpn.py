"""Master sender - sends all queued emails through WARP VPN with correct SMTP."""
import smtplib, ssl, os, sys, re

PASS = os.environ.get("EMAIL_PASSWORD")
if not PASS:
    print("ERROR: EMAIL_PASSWORD not set"); sys.exit(1)

SENDER = "charles@columbiataxlawyer.com"

def send_email(to, subject, body):
    """Send via port 587 with correct context= parameter."""
    msg = "From: %s\r\nTo: %s\r\nSubject: %s\r\nContent-Type: text/plain; charset=UTF-8\r\n\r\n%s" % (SENDER, to, subject, body)
    try:
        s = smtplib.SMTP("smtp.hostinger.com", 587, timeout=30)
        s.ehlo()
        s.starttls(context=ssl.create_default_context())
        s.ehlo()
        s.login(SENDER, PASS)
        s.sendmail(SENDER, to, msg.encode("utf-8"))
        s.quit()
        return True
    except Exception as e:
        return False

def extract_targets_from_file(filepath):
    """Parse email targets from a batch script file."""
    targets = []
    with open(filepath, encoding="utf-8") as f:
        content = f.read()
    # Find all (email, subject, body) tuples
    matches = re.findall(r'\(["\']([\w.@+-]+)["\'],\s*["\'](.+?)["\'],\s*["\'](.+?)["\']\s*\)', content, re.DOTALL)
    for email, subject, body in matches:
        if "@" in email:
            targets.append((email, subject, body))
    return targets

# Load all targets from batch scripts
all_targets = []
script_order = [
    "send_mensa_batch.py",
    "send_autism_parent_batch.py",
    "send_film_industry_batch.py",
    "send_arts_nonprofit_batch.py",
    "send_lineage_batch.py",
]

for script in script_order:
    try:
        targets = extract_targets_from_file(script)
        all_targets.extend(targets)
        print("Loaded %d targets from %s" % (len(targets), script))
    except Exception as e:
        print("Error loading %s: %s" % (script, e))

print("\nTotal: %d targets to send" % len(all_targets))
print("Sending via WARP VPN on port 587...\n")

sent = 0
failed = 0

for i, (to, subj, body) in enumerate(all_targets, 1):
    short_subj = subj[:50]
    print("[%d/%d] %s" % (i, len(all_targets), to), end="")
    
    if send_email(to, subj, body):
        sent += 1
        print(" ✅")
    else:
        failed += 1
        print(" ❌")
    
    if i % 5 == 0:
        print("  Progress: %d sent, %d failed\n" % (sent, failed))

print("\n=== DONE ===")
print("Sent:   %d" % sent)
print("Failed: %d" % failed)
print("Total:  %d" % len(all_targets))
