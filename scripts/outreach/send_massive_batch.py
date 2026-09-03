import smtplib, ssl, os, time, socket
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

socket.setdefaulttimeout(8)
SENDER = "charles@columbiataxlawyer.com"
PASS = os.environ.get("EMAIL_PASSWORD")
if not PASS:
    print("❌ EMAIL_PASSWORD not set"); exit(1)

STORY = "I am a 44-year-old US citizen with a formal ADHD diagnosis, relocating to Toronto this September to enroll full-time in the Certificate in Theological Studies at Trinity College, University of Toronto. I hold a JD and an LLM in Taxation and am returning to school as a mature, first-generation student. My income is ~$55K USD, no federal loan eligibility. Member of Emmaus Church (Methodist)."

# Read domains and generate email targets
domains = []
with open("big_foundation_list.txt") as f:
    for line in f:
        line = line.strip()
        if line and not line.startswith("#"):
            for d in line.split(","):
                d = d.strip()
                if d: domains.append(d)

targets = []
prefixes = ["info", "contact", "scholarships", "grants", "foundation", "admin"]
for d in domains:
    for p in prefixes:
        targets.append(f"{p}@{d}")

print(f"📝 {len(targets)} total targets from {len(domains)} domains")
print(f"🔍 Shuffling and starting sends...")

import random
random.shuffle(targets)  # mix them up so we hit different domains first

sent = 0
failed = []
for idx, email in enumerate(targets[:800], 1):  # cap at 800
    subj = f"Inquiry — Scholarship Opportunities for Theological Studies"
    body = f"Dear {email.split('@')[1].split('.')[0].title()} Foundation,\n\n{STORY}\n\nPlease let me know about any scholarship opportunities for which I might be eligible.\n\nThank you,\nCharles Alan Prescott Jr.\ncharles@columbiataxlawyer.com\n843-504-4542"
    
    msg = MIMEMultipart()
    msg["From"] = SENDER; msg["To"] = email; msg["Subject"] = subj
    msg.attach(MIMEText(body, "plain"))
    
    sent_ok = False
    for port, tls in [(587, True), (465, False)]:
        try:
            with smtplib.SMTP("smtp.hostinger.com", port) if tls else smtplib.SMTP_SSL("smtp.hostinger.com", port, ctx=ssl.create_default_context()) as s:
                if tls:
                    s.ehlo(); s.starttls(ctx:=ssl.create_default_context()); s.ehlo()
                s.login(SENDER, PASS)
                s.sendmail(SENDER, email, msg.as_string())
            sent += 1
            sent_ok = True
            if sent % 10 == 0:
                print(f"✅ {sent} sent so far...")
            break
        except: pass
    
    if not sent_ok:
        failed.append(email)
    
    if idx % 50 == 0:
        print(f"📊 Progress: {sent}/{idx} sent")

print(f"\n✅ Batch complete! Sent: {sent}/{min(800, len(targets))}")
if failed:
    print(f"📝 {len(failed)} failed - saved to failed_targets.txt")
    with open("failed_targets.txt", "w") as f:
        f.write("\n".join(failed))
