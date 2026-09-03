import smtplib, ssl, os, time, socket
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

socket.setdefaulttimeout(10)
SENDER = "charles@columbiataxlawyer.com"
PASS = os.environ.get("EMAIL_PASSWORD")
if not PASS:
    print("❌ EMAIL_PASSWORD not set"); exit(1)

STORY = "I am a 44-year-old US citizen who scored 143 (99.8th percentile) on the WAIS-III at age 10. I also have formal ADHD and MDD diagnoses. I earned a BA in Political Science from Coastal Carolina University (2009), my JD from Rutgers Law School (David Delgones Award), and my LLM in Taxation from the University of Alabama School of Law. I have served as Founding Director of the Midlands Light Opera Society, formed churches as an attorney, founded Healthy Connections (a health nonprofit), and taught CLEs. I am relocating to Toronto this September to enroll full-time in the Certificate in Theological Studies at Trinity College, University of Toronto, returning as a mature, first-generation student. Income ~$55K USD, no federal loan eligibility. Member of Emmaus Church (Methodist tradition). Father is a 100% VA-disabled US Army veteran. Father of three children, two diagnosed with autism."

emails = [
    # MENSA
    ("info@americanmensa.org", "American Mensa - Scholarship/Member Support Inquiry", f"Dear American Mensa,\n\nI have recently verified that my WAIS-III IQ score of 143 qualifies me for Mensa membership (99.8th percentile). Before formally joining, I wanted to inquire about any scholarship or education support programs available to members or prospective members, particularly for mature students pursuing theological studies.\n\n{STORY}\n\nPlease advise on:\n1. I understand the $107 annual membership fee — are there any reduced-fee options for students?\n2. Are there scholarships or grants available through Mensa or the Mensa Foundation for which I could apply?\n3. Are there any member referral programs or financial aid for new members?\n\nThank you,\nCharles Alan Prescott Jr.\ncharles@columbiataxlawyer.com\n843-504-4542"),
    
    # INTERTEL (top 1% - IQ 135+)
    ("contact@intertel-iq.org", "Intertel - Education Support Inquiry", f"Dear Intertel,\n\nI have recently learned that my WAIS-III IQ score of 143 (99.8th percentile) may qualify me for Intertel membership (top 1%). I am writing to inquire about any education support, scholarships, or fellowship programs available to members.\n\n{STORY}\n\nI would be honored to join a community of individuals with demonstrated high intellectual ability, and I am particularly interested in any programs that support members pursuing advanced education.\n\nPlease let me know if there are any scholarship or grant opportunities I should be aware of.\n\nThank you,\nCharles Alan Prescott Jr.\ncharles@columbiataxlawyer.com\n843-504-4542"),
    
    # SC MENSA LOCAL CHAPTER
    ("sc@mensa.org", "South Carolina Mensa - Scholarship Inquiry", f"Dear South Carolina Mensa,\n\nI am a South Carolina resident who has recently qualified for Mensa membership with a WAIS-III IQ score of 143. I am writing to ask about any local scholarship programs, education grants, or member support available through the South Carolina chapter.\n\n{STORY}\n\nAs a South Carolina native from a family that has been here since the earliest colonial days, I would appreciate any guidance on local resources or opportunities for members.\n\nThank you,\nCharles Alan Prescott Jr.\ncharles@columbiataxlawyer.com\n843-504-4542"),
    
    # MENSA FOUNDATION - direct email (supplemental to AwardSpring portal)
    ("foundation@mensafoundation.org", "Mensa Foundation - Scholarship Eligibility Inquiry", f"Dear Mensa Foundation,\n\nI am a prospective Mensa member (WAIS-III IQ 143, 99.8th percentile) and I understand your foundation awards over $200,000 annually in scholarships. I plan to apply through the AwardSpring portal, but wanted to also inquire directly about any scholarship programs that might be available for mature, first-generation students pursuing theological education.\n\n{STORY}\n\nPlease let me know if there are specific funds or programs you would recommend I explore.\n\nThank you,\nCharles Alan Prescott Jr.\ncharles@columbiataxlawyer.com\n843-504-4542"),
]

total = len(emails)
sent = 0

print(f"📝 Sending {total} high-IQ society inquiries...")
print(f"   ⚠ SMTP must be unblocked — will retry every 30s up to 30 attempts per target")

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
            print(f"❌ [{idx}/{total}] {to} — all 30 attempts failed")
        break

print(f"\n✅ Sent: {sent}/{total}")
