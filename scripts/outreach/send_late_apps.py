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
        "to": "scholarships@autismspeaks.org",
        "subject": "Late Inquiry — Higher Learning Scholarship for Theological Studies",
        "body": """Dear Autism Speaks Scholarship Committee,

I apologize for contacting you after the May 31 deadline for the Higher Learning Scholarship. My need has arisen very recently — I only made the decision to pursue theological studies in recent weeks, and I am writing to humbly inquire if any late consideration might still be possible.

I am a 44-year-old US citizen who will be relocating to Toronto this September to enroll full-time in the Certificate in Theological Studies at Trinity College, University of Toronto. I was formally diagnosed with ADHD and have probable autism, though I am seeking a formal evaluation.

I hold a JD and an LLM in Taxation and am returning to school as a mature, first-generation student. My legal career exposed me to deep questions about institutional morality that I believe theological study can help me answer. I am not pursuing a new career but deepening a spiritual calling.

My annual income is approximately $55,000 USD and I am not eligible for US federal student loans. I am seeking approximately $30,000 CAD to cover tuition and living expenses.

I understand the deadline has passed, but if any flexibility exists or if there are other opportunities within your organization, I would be most grateful.

Thank you,
Charles Alan Prescott Jr.
charles@columbiataxlawyer.com
843-504-4542"""
    },
    {
        "to": "info@limeconnect.com",
        "subject": "Inquiry — Scholarship Opportunities for Neurodivergent Graduate Student",
        "body": """Dear Lime Connect,

I am writing to inquire about scholarship opportunities for students with ADHD and neurodivergence pursuing graduate study.

I am a 44-year-old US citizen who will be relocating to Toronto this September to enroll full-time in the Certificate in Theological Studies at Trinity College, University of Toronto. I have a formal ADHD diagnosis and probable autism.

I hold a JD and an LLM in Taxation and am returning to school as a mature, first-generation student. My legal career taught me how institutions work; I am now pursuing theological study to understand how institutions should work — questions of morality, justice, and redemption in organizational contexts.

My annual income is approximately $55,000 USD. I am not eligible for US federal student loans.

I would be grateful to learn about any current or upcoming scholarship opportunities through Lime Connect that I might be eligible for. I am happy to join your network and provide any documentation needed.

Thank you,
Charles Alan Prescott Jr.
charles@columbiataxlawyer.com
843-504-4542"""
    },
    {
        "to": "scholarships@add.org",
        "subject": "Late Inquiry — ADHD Student Scholarship for Theological Studies",
        "body": """Dear ADDA Scholarship Committee,

I apologize for contacting you after any applicable deadline. My situation has developed very recently — I only decided to pursue theological studies in the past few weeks.

I am a 44-year-old US citizen with a formal ADHD diagnosis. I will be relocating to Toronto this September to enroll full-time in the Certificate in Theological Studies at Trinity College, University of Toronto.

I hold a JD and an LLM in Taxation and am returning to school as a mature, first-generation student. My annual income is approximately $55,000 USD and I am not eligible for US federal student loans.

I understand scholarship cycles may have closed, but I would be grateful to know:
1. Are there any current or upcoming scholarship opportunities I might apply for?
2. Is there any flexibility for late applications given the recent nature of my need?
3. What are the typical deadlines for your 2027 cycle?

Thank you for your understanding,
Charles Alan Prescott Jr.
charles@columbiataxlawyer.com
843-504-4542"""
    },
    {
        "to": "info@legion-aux.org",
        "subject": "Late Inquiry — Non-Traditional Student Scholarship (late application)",
        "body": """Dear American Legion Auxiliary Scholarship Committee,

I am writing to humbly inquire about the Non-Traditional Student Scholarship, even though I understand the March 1 deadline has passed.

My father is a 100% VA-disabled US Army veteran. I am a South Carolina resident and a 44-year-old non-traditional student who will be enrolling full-time in the Certificate in Theological Studies at Trinity College, University of Toronto starting September 2026.

I hold a JD and an LLM in Taxation and am returning to school after a long legal career as a mature, first-generation student. My decision to pursue theological study was made very recently, which is why I missed the application window.

I would be a strong candidate:
- Non-traditional student returning after years away
- Child of a 100% disabled veteran
- First-generation student
- Formal ADHD diagnosis
- Annual income ~$55,000 USD
- No federal loan eligibility

If any flexibility exists for late consideration, or if there are other opportunities I should watch for in the upcoming cycle, I would be most grateful.

Thank you,
Charles Alan Prescott Jr.
charles@columbiataxlawyer.com
843-504-4542
150 Southwell Rd., Columbia, SC 29210"""
    },
    {
        "to": "info@dav.org",
        "subject": "Inquiry — Scholarship Opportunities for Child of Disabled Veteran",
        "body": """Dear Disabled American Veterans,

I am writing to inquire about scholarship opportunities for adult children of disabled veterans pursuing higher education.

My father is a 100% VA-disabled US Army veteran. I am a 44-year-old South Carolina resident who will be enrolling full-time in the Certificate in Theological Studies at Trinity College, University of Toronto starting September 2026.

I hold a JD and an LLM in Taxation and am returning to school as a mature, first-generation student. My annual income is approximately $55,000 USD and I am not eligible for US federal student loans.

Could you please let me know:
1. What scholarship opportunities are available for children of disabled veterans?
2. What are the current deadlines and application requirements?
3. Is study at a Canadian institution eligible?

Thank you,
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

print("\n✅ All late applications sent!")
