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
        "to": "umscholar@gbhem.org",
        "subject": "Inquiry — GRASP International Scholarship for Theological Studies at Trinity College (2027)",
        "body": """Dear GBHEM Scholarship Office,

I am writing to inquire about the International Grants and Scholarships Program (GRASP) for the 2027 cycle.

I am a member of Emmaus Church (schismatic Methodist tradition) and will be enrolling full-time in the Certificate in Theological Studies at Trinity College, University of Toronto starting September 2026.

About me:
I hold a JD and an LLM in Taxation and am returning to school as a mature, first-generation student at age 44. I have a formal ADHD diagnosis and my father is a 100% VA-disabled US Army veteran. My annual income is approximately $55,000 USD and I am not eligible for US federal student loans.

My spiritual journey has led me from Baptist roots through Methodist action to Anglican liturgy. I am drawn to questions of institutional morality and the meaning of sin in institutional contexts — questions the law could frame but never answer.

My questions:
1. Am I eligible for the GRASP program as a US citizen studying in Canada?
2. Does Trinity College qualify as a Methodist-related institution for GRASP purposes?
3. What is the typical award range and application deadline for 2027?

I would be happy to provide any documentation needed.

Thank you,
Charles Alan Prescott Jr.
charles@columbiataxlawyer.com
843-504-4542"""
    },
    {
        "to": "scholarships@united-church.ca",
        "subject": "Inquiry — Scholarship Opportunities for Theological Studies at Trinity College",
        "body": """Dear United Church of Canada Foundation,

I am writing to inquire about scholarship and bursary opportunities for theological studies.

I am a US citizen who will be relocating to Toronto this September to enroll full-time in the Certificate in Theological Studies at Trinity College, University of Toronto. While I am not a member of the United Church of Canada, I deeply value the Methodist tradition of action from which the UCC emerged, and I am a member of Emmaus Church (schismatic Methodist).

About me:
I hold a JD and an LLM in Taxation and am returning to school as a mature, first-generation student at age 44. I have a formal ADHD diagnosis. My annual income is approximately $55,000 USD and I am not eligible for US federal student loans. I am seeking approximately $30,000 CAD to cover tuition and living expenses.

I note that the 2026 scholarship cycle has closed, but I would appreciate guidance on:
1. What opportunities might be available for the 2027 cycle?
2. Are there any awards open to non-members or those from Methodist-heritage traditions?
3. When do applications typically open?

Thank you for your time.

Warmly,
Charles Alan Prescott Jr.
charles@columbiataxlawyer.com
843-504-4542"""
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
            print(f"Sending to {email['to']} via port {port}...", end=" ")
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
            print("✅ Sent!")
            break
        except Exception as e:
            print(f"Failed: {e}")
    else:
        print(f"❌ Could not send to {email['to']}")

print("\n✅ Batch complete!")
