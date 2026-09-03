import smtplib, ssl, os, time, socket
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

socket.setdefaulttimeout(10)
SENDER = "charles@columbiataxlawyer.com"
PASS = os.environ.get("EMAIL_PASSWORD")
if not PASS:
    print("❌ EMAIL_PASSWORD not set"); exit(1)

STORY = "I am a 44-year-old US citizen with a formal ADHD diagnosis, relocating to Toronto this September to enroll full-time in the Certificate in Theological Studies at Trinity College, University of Toronto. I hold a JD and an LLM in Taxation and am returning to school as a mature, first-generation student. Income ~$55K USD, no federal loan eligibility. Member of Emmaus Church (Methodist tradition)."

# Load failed targets
with open("failed_targets.txt") as f:
    targets = [line.strip() for line in f if line.strip()]

print(f"📝 Retrying {len(targets)} failed targets with persistent retry...")

sent_total = 0
for idx, email in enumerate(targets, 1):
    subj = f"Inquiry — Scholarship Opportunities for Theological Studies"
    body = f"Dear {email.split('@')[1].split('.')[0].title()} Foundation,\n\n{STORY}\n\nPlease let me know about any scholarship opportunities for which I might be eligible.\n\nThank you,\nCharles Alan Prescott Jr.\ncharles@columbiataxlawyer.com\n843-504-4542"
    
    msg = MIMEMultipart()
    msg["From"] = SENDER; msg["To"] = email; msg["Subject"] = subj
    msg.attach(MIMEText(body, "plain"))
    
    for attempt in range(1, 61):  # up to 60 retries per email
        for port, tls in [(587, True), (465, False)]:
            try:
                if tls:
                    with smtplib.SMTP("smtp.hostinger.com", port) as s:
                        s.ehlo(); s.starttls(ctx:=ssl.create_default_context()); s.ehlo()
                        s.login(SENDER, PASS); s.sendmail(SENDER, email, msg.as_string())
                else:
                    with smtplib.SMTP_SSL("smtp.hostinger.com", port, ctx=ssl.create_default_context()) as s:
                        s.login(SENDER, PASS); s.sendmail(SENDER, email, msg.as_string())
                sent_total += 1
                print(f"✅ [{sent_total}] {email}")
                break
            except: pass
        else:
            if attempt < 60:
                if attempt == 1:
                    print(f"⏳ SMTP blocked, retrying every 30s...")
                time.sleep(30)
                continue
        break
    
    if idx % 50 == 0 and sent_total > 0:
        print(f"📊 {sent_total} sent so far out of {idx} attempts")

print(f"\n✅ Final: {sent_total} sent out of {len(targets)}")
