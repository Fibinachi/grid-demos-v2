import smtplib
import ssl
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# Email configuration
SMTP_SERVER = "smtp.hostinger.com"
SMTP_PORT = 465  # SSL
SENDER_EMAIL = "charles@columbiataxlawyer.com"
RECIPIENT_EMAIL = "foundation@anglicanfoundation.org"
PASSWORD = os.environ.get("EMAIL_PASSWORD")

# Email content
subject = "Bursary Inquiry — Certificate in Theological Studies, Trinity College (Fall 2026)"

body = """Dear Anglican Foundation of Canada,

I am writing to inquire about the Bursary for Theological Education and to introduce myself as a prospective applicant.

I am a US citizen who will be relocating to Toronto this September to enroll full-time in the Certificate in Theological Studies at Trinity College, University of Toronto.

My journey to this point:
I hold a JD and an LLM in Taxation and have spent years practicing law. After a long career, I am returning to school as a mature, first-generation student. My legal work exposed me to the inner workings of institutions — their structures, their failures, and their moral complexities. Over time, I found myself drawn to deeper questions: institutional morality, the meaning of sin in an institutional context, and how systems shape or wound the human soul. These are questions the law could frame but never answer. I believe theological study can.

My spiritual path:
I was raised Baptist leaning Pentecostal, and I carry those roots with me. Over time, I grew to deeply value the Methodist tradition of action — a faith that moves into the world. And I have found that the Anglican tradition of acceptance and liturgical beauty suits my particular soul. I am eager to study at Trinity College, rooted in that tradition.

My situation:
- Full-time student starting September 2026
- First-generation student and mature student returning after many years
- US citizen moving to Canada specifically for this program
- I have ADHD (and probable autism) — I will be registering with U of T's Accessibility Services
- My father is a 100% VA-disabled US Army veteran (Chapter 35 DEA benefits have since expired)
- Annual income approximately $55,000 USD
- Seeking approximately $30,000 CAD to cover tuition and living expenses

I do not yet have a home parish in Toronto, but I would very much love to connect with an Anglican community upon arrival. If you have any recommendations or connections, I would be most grateful.

I would be honored to be considered for the Bursary for Theological Education and welcome any guidance on the application process. I am happy to provide references, a statement of purpose, or any other documentation required.

Thank you for your time and for supporting theological education.

Warmly,
Charles Alan Prescott Jr.
charles@columbiataxlawyer.com
843-504-4542
150 Southwell Rd., Columbia, SC 29210 USA"""

# Build message
msg = MIMEMultipart()
msg["From"] = SENDER_EMAIL
msg["To"] = RECIPIENT_EMAIL
msg["Subject"] = subject
msg.attach(MIMEText(body, "plain"))

# Send
if not PASSWORD:
    print("❌ EMAIL_PASSWORD environment variable not set.")
    print("   Run: [Environment]::SetEnvironmentVariable('EMAIL_PASSWORD', 'yourpassword', 'User')")
    exit(1)

try:
    context = ssl.create_default_context()
    with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT, context=context) as server:
        server.login(SENDER_EMAIL, PASSWORD)
        server.sendmail(SENDER_EMAIL, RECIPIENT_EMAIL, msg.as_string())
    print("\n✅ Email sent successfully to foundation@anglicanfoundation.org!")
except Exception as e:
    print(f"\n❌ Failed to send email: {e}")
