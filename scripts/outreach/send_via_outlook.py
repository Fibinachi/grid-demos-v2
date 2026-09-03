import smtplib
import ssl
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

SMTP_SERVER = "smtp.office365.com"
SMTP_PORT = 587
SENDER_EMAIL = "charlesaprescott@outlook.com"
PASSWORD = os.environ.get("OUTLOOK_PASSWORD")

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
charlesaprescott@outlook.com"""
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
charlesaprescott@outlook.com"""
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
charlesaprescott@outlook.com"""
    },
    {
        "to": "info@legion-aux.org",
        "subject": "Late Inquiry — Non-Traditional Student Scholarship",
        "body": """Dear American Legion Auxiliary,

My father is a 100% VA-disabled US Army veteran. I am a South Carolina resident and a 44-year-old non-traditional student enrolling full-time in the Certificate in Theological Studies at Trinity College, University of Toronto starting September 2026.

I apologize for the late inquiry — my decision to pursue theological study was made very recently. I would be grateful to know about any late consideration possibilities or 2027 cycle dates.

Thank you,
Charles Alan Prescott Jr.
charlesaprescott@outlook.com
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
charlesaprescott@outlook.com"""
    }
]

if not PASSWORD:
    print("❌ OUTLOOK_PASSWORD environment variable not set.")
    exit(1)

for email in emails:
    msg = MIMEMultipart()
    msg["From"] = SENDER_EMAIL
    msg["To"] = email["to"]
    msg["Subject"] = email["subject"]
    msg.attach(MIMEText(email["body"], "plain"))
    
    try:
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT, timeout=15) as server:
            server.ehlo()
            server.starttls(context=ssl.create_default_context())
            server.ehlo()
            server.login(SENDER_EMAIL, PASSWORD)
            server.sendmail(SENDER_EMAIL, email["to"], msg.as_string())
        print(f"✅ {email['to']}")
    except Exception as e:
        print(f"❌ {email['to']}: {str(e)[:60]}")

print("\n✅ Batch complete!")
