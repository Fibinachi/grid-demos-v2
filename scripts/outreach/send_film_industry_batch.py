import smtplib, ssl, os, time, socket
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

socket.setdefaulttimeout(10)
SENDER = "charles@columbiataxlawyer.com"
PASS = os.environ.get("EMAIL_PASSWORD")
if not PASS:
    print("❌ EMAIL_PASSWORD not set"); exit(1)

STORY = """I am a 44-year-old US citizen with an IMDb credit in film distribution, a WAIS-III score of 143 (99.8th percentile, tested at age 10), and formal ADHD and MDD diagnoses. I am the father of three children, two diagnosed with autism. I earned a BA in Political Science from Coastal Carolina University (2009), my JD from Rutgers Law School (David Delgones Award), and my LLM in Taxation from the University of Alabama School of Law. I have served as Founding Director of the Midlands Light Opera Society, formed churches as an attorney, founded health nonprofits, and taught CLEs. I am relocating to Toronto this September for the Certificate in Theological Studies at Trinity College, U of T, returning as a mature, first-generation student. Income ~$55K USD, no federal loan eligibility. Member of Emmaus Church. Father is a 100% VA-disabled US Army veteran."""

emails = [
    # MOTION PICTURE & TELEVISION FUND
    ("info@mptf.com", "MPTF - Education Support Inquiry", f"Dear MPTF,\n\nI have an IMDb credit in film distribution and am writing to inquire about any education support, scholarship, or grant programs available to entertainment industry workers and their families.\n\n{STORY}\n\nPlease let me know about any programs for which I might be eligible.\n\nThank you,\nCharles Alan Prescott Jr.\ncharles@columbiataxlawyer.com\n843-504-4542"),
    
    # FILM INDEPENDENT
    ("info@filmindependent.org", "Film Independent - Education Grant Inquiry", f"Dear Film Independent,\n\nI am writing to inquire about any grants, scholarships, or education support programs available to members of the independent film community.\n\n{STORY}\n\nI have an IMDb credit in film distribution and am interested in any programs that support industry members pursuing further education.\n\nThank you,\nCharles Alan Prescott Jr.\ncharles@columbiataxlawyer.com\n843-504-4542"),
    
    # HOLLYWOOD PROFESSIONAL ASSOCIATION FOUNDATION
    ("info@hpaonline.com", "HPA Foundation - Scholarship Inquiry", f"Dear HPA Foundation,\n\nI have an IMDb credit in film distribution and am writing to ask about any scholarship or education support programs for entertainment industry professionals pursuing higher education.\n\n{STORY}\n\nThank you,\nCharles Alan Prescott Jr.\ncharles@columbiataxlawyer.com\n843-504-4542"),
    
    # ACADEMY OF MOTION PICTURE ARTS & SCIENCES
    ("info@oscars.org", "Academy Foundation - Education Grant Inquiry", f"Dear Academy Foundation,\n\nI am writing to inquire about any grant or education support programs for individuals with film industry experience. I have an IMDb credit in distribution work and am returning to school for theological studies.\n\n{STORY}\n\nPlease advise on any programs that might be available.\n\nThank you,\nCharles Alan Prescott Jr.\ncharles@columbiataxlawyer.com\n843-504-4542"),
    
    # SAG-AFTRA FOUNDATION (if union work)
    ("info@sagaftra.foundation", "SAG-AFTRA Foundation - Education Program Inquiry", f"Dear SAG-AFTRA Foundation,\n\nI have an IMDb credit in film distribution and am writing to inquire about any education support or scholarship programs available through the Foundation.\n\n{STORY}\n\nPlease let me know about any programs for which I might be eligible.\n\nThank you,\nCharles Alan Prescott Jr.\ncharles@columbiataxlawyer.com\n843-504-4542"),
    
    # INTERNATIONAL DOCUMENTARY ASSOCIATION
    ("info@documentary.org", "IDA - Education Grant Inquiry", f"Dear International Documentary Association,\n\nI am writing to inquire about any education support or grant programs for film industry professionals pursuing further education.\n\n{STORY}\n\nThank you,\nCharles Alan Prescott Jr.\ncharles@columbiataxlawyer.com\n843-504-4542"),
    
    # SUNDANCE INSTITUTE
    ("info@sundance.org", "Sundance Institute - Education Support Inquiry", f"Dear Sundance Institute,\n\nI am writing to inquire about any education or fellowship programs that might support an industry professional returning to school.\n\n{STORY}\n\nThank you,\nCharles Alan Prescott Jr.\ncharles@columbiataxlawyer.com\n843-504-4542"),
    
    # NAB EDUCATION FOUNDATION
    ("info@nabef.org", "NAB Education Foundation - Scholarship Inquiry", f"Dear NAB Education Foundation,\n\nI am writing to inquire about any scholarship or education grant programs for media and entertainment industry professionals.\n\n{STORY}\n\nThank you,\nCharles Alan Prescott Jr.\ncharles@columbiataxlawyer.com\n843-504-4542"),
]

total = len(emails)
sent = 0

print(f"📝 Sending {total} film/entertainment industry inquiries...")
print(f"   ⚠ Retrying every 30s up to 30 attempts each")

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
                print(f"✅ [{sent}/{total}] {to} (attempt {attempt})")
                break
            except: pass
        else:
            if attempt < 30:
                if attempt == 1:
                    print(f"⏳ SMTP blocked, retrying every 30s...")
                time.sleep(30)
                continue
            print(f"❌ [{idx}/{total}] {to} — all 30 failed")
        break

print(f"\n✅ Sent: {sent}/{total}")
