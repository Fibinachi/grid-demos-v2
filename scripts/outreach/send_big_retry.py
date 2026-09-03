import smtplib, ssl, os, time, socket
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

socket.setdefaulttimeout(10)
SENDER = "charles@columbiataxlawyer.com"
PASS = os.environ.get("EMAIL_PASSWORD")
if not PASS:
    print("❌ EMAIL_PASSWORD not set"); exit(1)

STORY = "I am a 44-year-old US citizen with a formal ADHD diagnosis, relocating to Toronto this September to enroll full-time in the Certificate in Theological Studies at Trinity College, University of Toronto. I hold a JD and an LLM in Taxation and am returning to school as a mature, first-generation student after a legal career. My annual income is approximately $55,000 USD and I am not eligible for US federal student loans. I am a member of Emmaus Church (Methodist tradition)."

emails = [
    ("scholarships@fisherhouse.org", "Fisher House - Scholarships for Military Children", f"Dear Fisher House,\n\nMy father is a 100% VA-disabled US Army veteran. {STORY}\n\nPlease let me know about the Scholarships for Military Children program.\n\nThank you,\nCharles Alan Prescott Jr."),
    ("info@militaryfamily.org", "NMFA - Scholarship Opportunities", f"Dear NMFA,\n\n{STORY}\n\nThank you,\nCharles Alan Prescott Jr."),
    ("info@chadd.org", "CHADD - ADHD Scholarship Inquiry", f"Dear CHADD,\n\n{STORY}\n\nPlease advise on scholarship opportunities for adults with ADHD.\n\nThank you,\nCharles Alan Prescott Jr."),
    ("info@ncld.org", "NCLD - Learning Disability Scholarships", f"Dear NCLD,\n\n{STORY}\n\nThank you,\nCharles Alan Prescott Jr."),
    ("info@understood.org", "Understood - Adult Learner Support", f"Dear Understood,\n\n{STORY}\n\nThank you,\nCharles Alan Prescott Jr."),
    ("info@pcusa.org", "PCUSA - Theological Education Scholarships", f"Dear PCUSA,\n\n{STORY}\n\nThank you,\nCharles Alan Prescott Jr."),
    ("info@elca.org", "ELCA - Theological Scholarships", f"Dear ELCA,\n\n{STORY}\n\nThank you,\nCharles Alan Prescott Jr."),
    ("info@americanbible.org", "American Bible Society - Scholar Inquiry", f"Dear American Bible Society,\n\n{STORY}\n\nThank you,\nCharles Alan Prescott Jr."),
    ("scholarships@horatioalger.org", "Horatio Alger - Graduate Scholarship Inquiry", f"Dear Horatio Alger,\n\n{STORY}\n\nThank you,\nCharles Alan Prescott Jr."),
    ("info@sctfoundation.org", "SCT Foundation - Scholarship Inquiry", f"Dear SCT Foundation,\n\n{STORY}\n\nThank you,\nCharles Alan Prescott Jr."),
    ("info@ecmc.org", "ECMC Foundation - Scholarship Inquiry", f"Dear ECMC,\n\n{STORY}\n\nThank you,\nCharles Alan Prescott Jr."),
    ("awards@utoronto.ca", "U of T - Bursaries & Awards", f"Dear U of T Awards,\n\n{STORY}\n\nPlease advise on bursaries for international students.\n\nThank you,\nCharles Alan Prescott Jr."),
    ("international.centre@utoronto.ca", "U of T International - Funding Resources", f"Dear U of T International Centre,\n\n{STORY}\n\nThank you,\nCharles Alan Prescott Jr."),
    ("info@univcan.ca", "Universities Canada - Scholarship Inquiry", f"Dear Universities Canada,\n\n{STORY}\n\nThank you,\nCharles Alan Prescott Jr."),
    ("info@cmec.ca", "CMEC - Canadian Education Scholarships", f"Dear CMEC,\n\n{STORY}\n\nThank you,\nCharles Alan Prescott Jr."),
    ("info@iie.org", "IIE - US Study Abroad Scholarships", f"Dear IIE,\n\n{STORY}\n\nPlease advise on scholarships for US citizens studying in Canada.\n\nThank you,\nCharles Alan Prescott Jr."),
    ("info@che.sc.gov", "SC CHE - State Scholarship Inquiry", f"Dear SC Commission on Higher Ed,\n\n{STORY}\n\nThank you,\nCharles Alan Prescott Jr."),
    ("info@firstgenfoundation.org", "First Gen Foundation - Scholarship", f"Dear First Gen Foundation,\n\nAs a first-generation student, {STORY}\n\nThank you,\nCharles Alan Prescott Jr."),
    ("info@imfirst.org", "I'm First - Scholarship Inquiry", f"Dear I'm First,\n\n{STORY}\n\nThank you,\nCharles Alan Prescott Jr."),
    ("info@ahea.org", "AHEA - Adult Higher Education", f"Dear AHEA,\n\nAs an adult returning learner, {STORY}\n\nThank you,\nCharles Alan Prescott Jr."),
    ("info@upcea.edu", "UPCEA - Continuing Ed Scholarships", f"Dear UPCEA,\n\n{STORY}\n\nThank you,\nCharles Alan Prescott Jr."),
    ("info@goabroad.com", "GoAbroad - Scholarship Inquiry", f"Dear GoAbroad,\n\n{STORY}\n\nThank you,\nCharles Alan Prescott Jr."),
    ("info@iesabroad.org", "IES Abroad - Scholarship Inquiry", f"Dear IES Abroad,\n\n{STORY}\n\nThank you,\nCharles Alan Prescott Jr."),
    ("info@nafusa.org", "NAFSA - Intl Student Scholarships", f"Dear NAFSA,\n\n{STORY}\n\nThank you,\nCharles Alan Prescott Jr."),
    ("info@collegeboard.org", "College Board - Scholarship Search", f"Dear College Board,\n\n{STORY}\n\nThank you,\nCharles Alan Prescott Jr."),
]

total = len(emails)
sent = 0

for idx, (to, subj, body) in enumerate(emails, 1):
    msg = MIMEMultipart()
    msg["From"] = SENDER; msg["To"] = to; msg["Subject"] = subj
    msg.attach(MIMEText(body, "plain"))
    
    for attempt in range(1, 31):  # 30 retries per email
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
                print(f"✅ [{sent}/{total}] {to} (attempt {attempt})")
                break
            except: pass
        else:
            if attempt < 30:
                print(f"⏳ [{idx}/{total}] {to} failed attempt {attempt}, retrying in 30s...")
                time.sleep(30)
                continue
            print(f"❌ [{idx}/{total}] {to} - all 30 attempts failed")
        break  # break retry loop if sent
    
    time.sleep(2)  # small delay between different emails

print(f"\n✅ Done! Sent: {sent}/{total}")
