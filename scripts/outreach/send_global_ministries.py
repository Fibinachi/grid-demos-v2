import smtplib
import ssl
import os
import socket
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

socket.setdefaulttimeout(60)

SMTP_SERVER = "smtp.hostinger.com"
SENDER_EMAIL = "charles@columbiataxlawyer.com"
RECIPIENT_EMAIL = "info@umcmission.org"
PASSWORD = os.environ.get("EMAIL_PASSWORD")

subject = "Inquiry — World Communion Scholarship for Theological Studies at Trinity College, Toronto (Fall 2026)"

body = """Dear Global Ministries Scholarship Committee,

I am writing to inquire about the World Communion Scholarship and/or Leadership Development Scholarship for graduate theological study.

I am a US citizen who will be relocating to Toronto, Canada this September to enroll full-time in the Certificate in Theological Studies at Trinity College, University of Toronto.

About me:
I hold a JD and an LLM in Taxation and have spent years practicing law. After a long career, I am returning to school as a mature, first-generation student. My legal work exposed me to the inner workings of institutions — their structures, their failures, and their moral complexities. Over time, I found myself drawn to deeper questions: institutional morality, the meaning of sin in an institutional context, and how systems shape or wound the human soul. These are questions the law could frame but never answer. I believe theological study can.

I wish to attend Trinity College — a foreign institution in Canada — not to pursue a new career, but to deepen my spiritual journey. This is a personal calling, not a vocational pivot, and I am seeking support to make it possible.

My spiritual path:
I was raised Baptist leaning Pentecostal. Over time, I grew to deeply value the Methodist tradition of action — a faith that moves into the world. I am drawn to the Methodist commitment to justice, service, and discipleship in daily life. While I have chosen Trinity College for its Anglican roots, my heart is rooted in the Methodist emphasis on faith in action. I am committed to connecting with a United Methodist congregation in Toronto upon arrival and would welcome a referral or recommendation to one.

My situation:
- Full-time student starting September 2026
- First-generation student and mature student returning after many years
- US citizen studying outside the US
- I have ADHD (and probable autism)
- My father is a 100% VA-disabled US Army veteran
- Annual income approximately $55,000 USD
- Not eligible for US federal student loans
- Seeking approximately $30,000 CAD to cover tuition and living expenses

My questions:
1. Am I eligible for the World Communion or Leadership Development Scholarship as a US citizen studying outside the US?
2. Can I apply if I will be connecting with a United Methodist church in Toronto but am not yet a formal member?
3. Is Trinity College (University of Toronto) an approved institution for these scholarships?
4. Do you have any recommendations for United Methodist congregations in Toronto?
5. What documentation would you need from me by the July 20 deadline?

Thank you for your time and for the vital work you do in supporting theological education around the world.

In faith,
Charles Alan Prescott Jr.
charles@columbiataxlawyer.com
843-504-4542
150 Southwell Rd., Columbia, SC 29210 USA"""

msg = MIMEMultipart()
msg["From"] = SENDER_EMAIL
msg["To"] = RECIPIENT_EMAIL
msg["Subject"] = subject
msg.attach(MIMEText(body, "plain"))

if not PASSWORD:
    print("❌ EMAIL_PASSWORD environment variable not set.")
    exit(1)

for port, use_starttls in [(587, True), (465, False)]:
    try:
        print(f"Trying port {port}...", end=" ")
        if use_starttls:
            with smtplib.SMTP(SMTP_SERVER, port) as server:
                server.ehlo()
                server.starttls(context=ssl.create_default_context())
                server.ehlo()
                server.login(SENDER_EMAIL, PASSWORD)
                server.sendmail(SENDER_EMAIL, RECIPIENT_EMAIL, msg.as_string())
        else:
            context = ssl.create_default_context()
            with smtplib.SMTP_SSL(SMTP_SERVER, port, context=context) as server:
                server.login(SENDER_EMAIL, PASSWORD)
                server.sendmail(SENDER_EMAIL, RECIPIENT_EMAIL, msg.as_string())
        print("✅ Sent!")
        break
    except Exception as e:
        print(f"Failed: {e}")
else:
    print("❌ All SMTP ports failed. ISP is blocking outbound SMTP.")
