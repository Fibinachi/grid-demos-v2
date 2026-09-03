import smtplib, ssl, os, time, socket
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

socket.setdefaulttimeout(10)
SENDER = "charles@columbiataxlawyer.com"
PASS = os.environ.get("EMAIL_PASSWORD")
if not PASS:
    print("❌ EMAIL_PASSWORD not set"); exit(1)

STORY = "I am a 44-year-old US citizen from an old South Carolina family whose ancestors were among the first settlers of South Carolina. I have a formal ADHD diagnosis and major depressive disorder. I am relocating to Toronto this September to enroll full-time in the Certificate in Theological Studies at Trinity College, University of Toronto. I hold a JD and an LLM in Taxation and am returning to school as a mature, first-generation student. Income ~$55K USD, no federal loan eligibility."

emails = [
    # Lineage-based
    ("info@southcarolinasc.org", "SC Society - Heritage Scholarship Inquiry", f"Dear South Carolina Society,\n\n{STORY}\n\nPlease advise on any scholarship opportunities for descendants of early South Carolina families.\n\nThank you,\nCharles Alan Prescott Jr."),
    ("contact@nscda.org", "National Society Colonial Dames - Scholarship", f"Dear NSCDA,\n\n{STORY}\n\nPlease advise on scholarship opportunities for descendants of early American settlers.\n\nThank you,\nCharles Alan Prescott Jr."),
    ("info@nsdar.org", "DAR - Scholarship Inquiry", f"Dear DAR,\n\n{STORY}\n\nPlease let me know about scholarship opportunities.\n\nThank you,\nCharles Alan Prescott Jr."),
    ("info@sc-americanheritage.org", "SC American Heritage - Scholarship", f"Dear SC American Heritage,\n\n{STORY}\n\nThank you,\nCharles Alan Prescott Jr."),
    
    # SC-specific foundations
    ("info@scphilanthropy.org", "SC Philanthropy - Scholarship Inquiry", f"Dear SC Philanthropy,\n\nI am a South Carolina native. {STORY}\n\nThank you,\nCharles Alan Prescott Jr."),
    ("info@sc-arts.org", "SC Arts Foundation - Scholarship Inquiry", f"Dear SC Arts Foundation,\n\n{STORY}\n\nThank you,\nCharles Alan Prescott Jr."),
    ("info@sc-education.org", "SC Education Foundation - Scholarship", f"Dear SC Education Foundation,\n\n{STORY}\n\nThank you,\nCharles Alan Prescott Jr."),
    
    # Heritage & preservation
    ("info@preservationnation.org", "Preservation Nation - Scholarship Inquiry", f"Dear Preservation Nation,\n\n{STORY}\n\nThank you,\nCharles Alan Prescott Jr."),
    ("info@scpreservation.org", "SC Preservation - Scholarship Inquiry", f"Dear SC Preservation,\n\n{STORY}\n\nThank you,\nCharles Alan Prescott Jr."),
    
    # Historical societies
    ("info@americanancestors.org", "American Ancestors - Scholarship", f"Dear American Ancestors,\n\n{STORY}\n\nThank you,\nCharles Alan Prescott Jr."),
    ("info@huguenotsociety.org", "Huguenot Society - Scholarship Inquiry", f"Dear Huguenot Society,\n\n{STORY}\n\nThank you,\nCharles Alan Prescott Jr."),
    
    # Mayflower / First Families
    ("info@themayflowersociety.org", "Mayflower Society - Scholarship", f"Dear Mayflower Society,\n\n{STORY}\n\nThank you,\nCharles Alan Prescott Jr."),
    ("info@firstfamilies.org", "First Families - Scholarship Inquiry", f"Dear First Families,\n\n{STORY}\n\nThank you,\nCharles Alan Prescott Jr."),
]

total = len(emails)
sent = 0

for idx, (to, subj, body) in enumerate(emails, 1):
    msg = MIMEMultipart()
    msg["From"] = SENDER; msg["To"] = to; msg["Subject"] = subj
    msg.attach(MIMEText(body, "plain"))
    
    for attempt in range(1, 31):
        for port, tls in [(587, True), (465, False)]:
            try:
                if tls:
                    with smtplib.SMTP("smtp.hostinger.com", port) as s:
                        s.ehlo(); s.starttls(ctx:=ssl.create_default_context()); s.ehlo()
                        s.login(SENDER, PASS); s.sendmail(SENDER, to, msg.as_string())
                else:
                    with smtplib.SMTP_SSL("smtp.hostinger.com", port, ctx=ssl.create_default_context()) as s:
                        s.login(SENDER, PASS); s.sendmail(SENDER, to, msg.as_string())
                sent += 1
                print(f"✅ [{sent}/{total}] {to}")
                break
            except: pass
        else:
            if attempt < 30:
                time.sleep(30)
                continue
            print(f"❌ [{idx}/{total}] {to}")
        break

print(f"\n✅ Sent: {sent}/{total}")
