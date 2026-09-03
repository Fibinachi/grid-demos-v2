"""Send GRID sales outreach via Gmail SMTP — 1 per 3 min, with map attachments."""
import csv, smtplib, time, sys, os
from pathlib import Path
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders

SMTP, PORT = "smtp.gmail.com", 587
FROM = "charlesaprescottjr@gmail.com"
PWD = os.environ.get("GMAIL_APP_PASSWORD")
if not PWD:
    print("ERROR: GMAIL_APP_PASSWORD not set. Run:")
    print("  [Environment]::SetEnvironmentVariable('GMAIL_APP_PASSWORD','your-key','User')")
    sys.exit(1)
CSV = Path("outputs/outreach/outreach_emails.csv")
MAPS = Path("outputs/outreach")
SENT = Path("outputs/outreach/gmail_sent.txt")
INTERVAL = 180

already = set()
if SENT.exists(): already = set(SENT.read_text().strip().split("\n"))

drafts = []
with open(CSV, encoding="utf-8") as f:
    for r in csv.DictReader(f):
        if r["contact_type"] == "Email" and r["org"] not in already:
            drafts.append(r)

print(f"Pending: {len(drafts)} | Sent: {len(already)} | 1/{INTERVAL//60}min")
if not drafts: print("All done."); sys.exit(0)

ok = fail = 0
for i, r in enumerate(drafts):
    org, to_addr = r["org"], r["contact_value"]
    print(f"[{i+1}/{len(drafts)}] {org} -> {to_addr}")

    msg = MIMEMultipart()
    msg["From"] = f"Charles Prescott <{FROM}>"
    msg["To"] = to_addr
    msg["Reply-To"] = "charlesaprescott@outlook.com"
    msg["Subject"] = r["subject"]
    msg.attach(MIMEText(r["body"], "plain"))

    mp = MAPS / r.get("map_attach", "")
    if mp.exists():
        with open(mp, "rb") as fh:
            p = MIMEBase("text", "html"); p.set_payload(fh.read())
            encoders.encode_base64(p)
            p.add_header("Content-Disposition", f'attachment; filename="{mp.name}"')
            msg.attach(p)

    try:
        with smtplib.SMTP(SMTP, PORT, timeout=30) as s:
            s.starttls(); s.login(FROM, PWD); s.send_message(msg)
        ok += 1
        with open(SENT, "a") as sf: sf.write(f"{org}\n")
        print(f"  SENT ({ok} ok, {fail} fail)")
    except Exception as e:
        fail += 1
        print(f"  FAIL: {e}")

    if i < len(drafts) - 1:
        print(f"  Waiting {INTERVAL//60}min...")
        time.sleep(INTERVAL)

print(f"\nDone: {ok} sent, {fail} failed")
