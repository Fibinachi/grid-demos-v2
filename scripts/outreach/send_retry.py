import smtplib
import ssl
import os
import time
import socket
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

socket.setdefaulttimeout(10)

SENDER_EMAIL = "charles@columbiataxlawyer.com"
PASSWORD = os.environ.get("EMAIL_PASSWORD")

if not PASSWORD:
    print("❌ EMAIL_PASSWORD not set")
    exit(1)

emails = [
    {
        "to": "scholarships@autismspeaks.org",
        "subject": "Late Inquiry — Higher Learning Scholarship for Theological Studies",
        "body": "Dear Autism Speaks Scholarship Committee,\n\nI apologize for contacting you after the May 31 deadline. My need has arisen very recently. I am a 44-year-old US citizen with a formal ADHD diagnosis and probable autism. I will be relocating to Toronto this September to enroll full-time in the Certificate in Theological Studies at Trinity College, University of Toronto.\n\nI hold a JD and an LLM in Taxation and am returning to school as a mature, first-generation student. My annual income is approximately $55,000 USD and I am not eligible for US federal student loans.\n\nIf any flexibility exists despite the passed deadline, I would be most grateful. Otherwise, please let me know when the 2027 cycle opens.\n\nThank you,\nCharles Alan Prescott Jr.\ncharles@columbiataxlawyer.com"
    },
    {
        "to": "info@limeconnect.com",
        "subject": "Inquiry — Scholarship Opportunities for Neurodivergent Graduate Student",
        "body": "Dear Lime Connect,\n\nI am writing to inquire about scholarship opportunities for students with ADHD. I am a 44-year-old US citizen with a formal ADHD diagnosis and probable autism. I will be relocating to Toronto this September to enroll full-time in the Certificate in Theological Studies at Trinity College, University of Toronto.\n\nI hold a JD and an LLM in Taxation and am returning to school as a mature, first-generation student. My annual income is approximately $55,000 USD and I am not eligible for US federal student loans.\n\nPlease let me know about any current or upcoming scholarship opportunities.\n\nThank you,\nCharles Alan Prescott Jr.\ncharles@columbiataxlawyer.com"
    },
    {
        "to": "scholarships@add.org",
        "subject": "Late Inquiry — ADHD Student Scholarship for Theological Studies",
        "body": "Dear ADDA Scholarship Committee,\n\nI apologize for contacting you after any applicable deadline. I am a 44-year-old US citizen with a formal ADHD diagnosis. I will be relocating to Toronto this September to enroll full-time in the Certificate in Theological Studies at Trinity College, University of Toronto.\n\nI hold a JD and an LLM in Taxation and am returning to school as a mature, first-generation student. Please let me know about any current opportunities or 2027 cycle deadlines.\n\nThank you,\nCharles Alan Prescott Jr.\ncharles@columbiataxlawyer.com"
    },
    {
        "to": "info@legion-aux.org",
        "subject": "Late Inquiry — Non-Traditional Student Scholarship",
        "body": "Dear American Legion Auxiliary,\n\nMy father is a 100% VA-disabled US Army veteran. I am a South Carolina resident and a 44-year-old non-traditional student enrolling full-time in the Certificate in Theological Studies at Trinity College, University of Toronto starting September 2026.\n\nI apologize for the late inquiry. I would be grateful to know about any late consideration possibilities or 2027 cycle dates.\n\nThank you,\nCharles Alan Prescott Jr.\ncharles@columbiataxlawyer.com\n150 Southwell Rd., Columbia, SC 29210"
    },
    {
        "to": "info@dav.org",
        "subject": "Inquiry — Scholarship for Child of Disabled Veteran",
        "body": "Dear DAV,\n\nMy father is a 100% VA-disabled US Army veteran. I am a 44-year-old South Carolina resident enrolling full-time in the Certificate in Theological Studies at Trinity College, University of Toronto starting September 2026.\n\nI hold a JD and an LLM in Taxation and am returning to school as a mature, first-generation student. Please let me know about any scholarship opportunities for children of disabled veterans.\n\nThank you,\nCharles Alan Prescott Jr.\ncharles@columbiataxlawyer.com"
    }
]

MAX_RETRIES = 30
retry_delay = 30  # seconds

for email_data in emails:
    sent = False
    for attempt in range(1, MAX_RETRIES + 1):
        msg = MIMEMultipart()
        msg["From"] = SENDER_EMAIL
        msg["To"] = email_data["to"]
        msg["Subject"] = email_data["subject"]
        msg.attach(MIMEText(email_data["body"], "plain"))
        
        for port, use_starttls in [(587, True), (465, False)]:
            try:
                if use_starttls:
                    with smtplib.SMTP("smtp.hostinger.com", port) as server:
                        server.ehlo()
                        server.starttls(context=ssl.create_default_context())
                        server.ehlo()
                        server.login(SENDER_EMAIL, PASSWORD)
                        server.sendmail(SENDER_EMAIL, email_data["to"], msg.as_string())
                else:
                    ctx = ssl.create_default_context()
                    with smtplib.SMTP_SSL("smtp.hostinger.com", port, context=ctx) as server:
                        server.login(SENDER_EMAIL, PASSWORD)
                        server.sendmail(SENDER_EMAIL, email_data["to"], msg.as_string())
                
                print(f"✅ [{email_data['to']}] sent on attempt {attempt}")
                sent = True
                break
            except:
                pass
        
        if sent:
            break
        
        if attempt < MAX_RETRIES:
            print(f"⏳ [{email_data['to']}] attempt {attempt}/{MAX_RETRIES} failed, retrying in {retry_delay}s...")
            time.sleep(retry_delay)
    
    if not sent:
        print(f"❌ [{email_data['to']}] failed after {MAX_RETRIES} attempts")
    time.sleep(5)

print("\n✅ All done!")
