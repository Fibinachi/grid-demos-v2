import smtplib
import ssl
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

SMTP_SERVER = "smtp.hostinger.com"
SENDER_EMAIL = "charles@columbiataxlawyer.com"
PASSWORD = os.environ.get("EMAIL_PASSWORD")

emails = [
    {
        "to": "info@umcmission.org",
        "subject": "Follow-up — Emmaus Church Membership / World Communion Scholarship",
        "body": """Dear Global Ministries Scholarship Committee,

I am following up on my previous inquiry to share that I am now a member of Emmaus Church (schismatic Methodist tradition). I wanted to update my application status accordingly.

I will be enrolling full-time in the Certificate in Theological Studies at Trinity College, University of Toronto starting September 2026. I am a US citizen studying outside the US, pursuing theological study to deepen my understanding of institutional morality and spiritual formation — not as a career pivot, but as a personal calling.

Please let me know if this membership qualifies me for the World Communion or Leadership Development Scholarship programs, and what documentation you would need from me by the July 20 deadline.

Thank you,
Charles Alan Prescott Jr.
charles@columbiataxlawyer.com
843-504-4542"""
    },
    {
        "to": "info@methodistfoundation.org",
        "subject": "Scholarship Inquiry — Theological Studies at Trinity College, Toronto",
        "body": """Dear Methodist Foundation,

I am writing to inquire about scholarship opportunities for theological study.

I am a member of Emmaus Church (schismatic Methodist tradition) and will be enrolling full-time in the Certificate in Theological Studies at Trinity College, University of Toronto starting September 2026.

I hold a JD and an LLM in Taxation and am returning to school as a mature, first-generation student at age 44. I have a formal ADHD diagnosis. My annual income is approximately $55,000 USD and I am not eligible for US federal student loans.

My legal career exposed me to deep questions about institutional morality that I believe theological study can help me answer. I am drawn to the Methodist tradition of faith in action.

Could you please let me know:
1. What scholarship opportunities are available for graduate theological study?
2. What are the application requirements and deadlines?
3. Is study at a Canadian institution eligible?

Thank you,
Charles Alan Prescott Jr.
charles@columbiataxlawyer.com
843-504-4542"""
    },
    {
        "to": "info@rotarycolumbiasc.org",
        "subject": "Scholarship Inquiry — Adult Learner / Theological Studies",
        "body": """Dear Rotary Club of Columbia,

I am writing to inquire about scholarship opportunities for adult learners pursuing higher education.

I am a Columbia, SC resident and will be enrolling full-time in the Certificate in Theological Studies at Trinity College, University of Toronto starting September 2026.

I hold a JD and an LLM in Taxation and am returning to school as a mature, first-generation student at age 44. I have a formal ADHD diagnosis. My annual income is approximately $55,000 USD and I am not eligible for US federal student loans.

I would be grateful for any information about Rotary scholarships or local funding opportunities for adult learners returning to education.

Thank you,
Charles Alan Prescott Jr.
charles@columbiataxlawyer.com
843-504-4542
150 Southwell Rd., Columbia, SC 29210"""
    }
]

if not PASSWORD:
    print("❌ EMAIL_PASSWORD environment variable not set.")
    exit(1)

for email in emails:
    msg = MIMEMultipart()
    msg["From"] = SENDER_EMAIL
    msg["To"] = email["to"]
    msg["Subject"] = email["subject"]
    msg.attach(MIMEText(email["body"], "plain"))
    
    for port, use_starttls in [(587, True), (465, False)]:
        try:
            print(f"Sending to {email['to']}...", end=" ")
            if use_starttls:
                with smtplib.SMTP(SMTP_SERVER, port) as server:
                    server.ehlo()
                    server.starttls(context=ssl.create_default_context())
                    server.ehlo()
                    server.login(SENDER_EMAIL, PASSWORD)
                    server.sendmail(SENDER_EMAIL, email["to"], msg.as_string())
            else:
                context = ssl.create_default_context()
                with smtplib.SMTP_SSL(SMTP_SERVER, port, context=context) as server:
                    server.login(SENDER_EMAIL, PASSWORD)
                    server.sendmail(SENDER_EMAIL, email["to"], msg.as_string())
            print("✅")
            break
        except Exception as e:
            print(f"port {port} failed: {str(e)[:50]}...")
    else:
        print(f"❌ Could not send to {email['to']}")

print("\n✅ Batch 2 complete!")
