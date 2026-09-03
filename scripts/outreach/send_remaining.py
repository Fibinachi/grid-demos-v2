import smtplib
import ssl
import os
import socket
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

socket.setdefaulttimeout(15)  # shorter timeout

SENDER_EMAIL = "charles@columbiataxlawyer.com"
PASSWORD = os.environ.get("EMAIL_PASSWORD")

if not PASSWORD:
    print("❌ EMAIL_PASSWORD not set")
    exit(1)

emails = [
    {
        "to": "scholarships@autismspeaks.org",
        "subject": "Late Inquiry — Higher Learning Scholarship for Theological Studies",
        "body": """Dear Autism Speaks Scholarship Committee,

I apologize for contacting you after the May 31 deadline. My need has arisen very recently — I only made the decision to pursue theological studies in recent weeks.

I am a 44-year-old US citizen with a formal ADHD diagnosis and probable autism. I will be relocating to Toronto this September to enroll full-time in the Certificate in Theological Studies at Trinity College, University of Toronto.

I hold a JD and an LLM in Taxation and am returning to school as a mature, first-generation student. My annual income is approximately $55,000 USD and I am not eligible for US federal student loans.

If any flexibility exists despite the passed deadline, I would be most grateful. Otherwise, please let me know when the 2027 cycle opens.

Thank you,
Charles Alan Prescott Jr.
charles@columbiataxlawyer.com"""
    },
    {
        "to": "info@limeconnect.com",
        "subject": "Inquiry — Scholarship Opportunities for Neurodivergent Graduate Student",
        "body": """Dear Lime Connect,

I am writing to inquire about scholarship opportunities for students with ADHD.

I am a 44-year-old US citizen with a formal ADHD diagnosis and probable autism. I will be relocating to Toronto this September to enroll full-time in the Certificate in Theological Studies at Trinity College, University of Toronto.

I hold a JD and an LLM in Taxation and am returning to school as a mature, first-generation student. My annual income is approximately $55,000 USD and I am not eligible for US federal student loans.

Please let me know about any current or upcoming scholarship opportunities I may be eligible for.

Thank you,
Charles Alan Prescott Jr.
charles@columbiataxlawyer.com"""
    },
    {
        "to": "scholarships@add.org",
        "subject": "Late Inquiry — ADHD Student Scholarship for Theological Studies",
        "body": """Dear ADDA Scholarship Committee,

I apologize for contacting you after any applicable deadline. My situation has developed very recently.

I am a 44-year-old US citizen with a formal ADHD diagnosis. I will be relocating to Toronto this September to enroll full-time in the Certificate in Theological Studies at Trinity College, University of Toronto.

I hold a JD and an LLM in Taxation and am returning to school as a mature, first-generation student. Please let me know about any current opportunities or 2027 cycle deadlines.

Thank you,
Charles Alan Prescott Jr.
charles@columbiataxlawyer.com"""
    },
    {
        "to": "info@legion-aux.org",
        "subject": "Late Inquiry — Non-Traditional Student Scholarship",
        "body": """Dear American Legion Auxiliary,

My father is a 100% VA-disabled US Army veteran. I am a South Carolina resident and a 44-year-old non-traditional student enrolling full-time in the Certificate in Theological Studies at Trinity College, University of Toronto starting September 2026.

I apologize for the late inquiry — my decision to pursue theological study was made very recently. I would be grateful to know about any late consideration possibilities or 2027 cycle dates.

Thank you,
Charles Alan Prescott Jr.
charles@columbiataxlawyer.com
150 Southwell Rd., Columbia, SC 29210"""
    },
    {
        "to": "info@dav.org",
        "subject": "Inquiry — Scholarship for Child of Disabled Veteran",
        "body": """Dear DAV,

My father is a 100% VA-disabled US Army veteran. I am a 44-year-old South Carolina resident enrolling full-time in the Certificate in Theological Studies at Trinity College, University of Toronto starting September 2026.

I hold a JD and an LLM in Taxation and am returning to school as a mature, first-generation student. Please let me know about any scholarship opportunities for children of disabled veterans.

Thank you,
Charles Alan Prescott Jr.
charles@columbiataxlawyer.com"""
    }
]

# Try multiple SMTP servers/ports to bypass ISP block
smtp_servers = [
    ("smtp.hostinger.com", 587, True),
    ("smtp.hostinger.com", 465, False),
]

for email in emails:
    msg = MIMEMultipart()
    msg["From"] = SENDER_EMAIL
    msg["To"] = email["to"]
    msg["Subject"] = email["subject"]
    msg.attach(MIMEText(email["body"], "plain"))
    
    sent = False
    for server, port, use_starttls in smtp_servers:
        try:
            if use_starttls:
                with smtplib.SMTP(server, port, timeout=10) as s:
                    s.ehlo()
                    s.starttls(context=ssl.create_default_context())
                    s.ehlo()
                    s.login(SENDER_EMAIL, PASSWORD)
                    s.sendmail(SENDER_EMAIL, email["to"], msg.as_string())
            else:
                ctx = ssl.create_default_context()
                with smtplib.SMTP_SSL(server, port, timeout=10, context=ctx) as s:
                    s.login(SENDER_EMAIL, PASSWORD)
                    s.sendmail(SENDER_EMAIL, email["to"], msg.as_string())
            print(f"✅ {email['to']}")
            sent = True
            break
        except Exception as e:
            pass
    
    if not sent:
        print(f"❌ {email['to']} — all ports blocked")

print("\nDone")
