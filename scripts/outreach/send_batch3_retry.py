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
    # MORE VETERAN
    ("info@vfw.org", "VFW - Veteran Family Scholarships", f"Dear VFW,\n\nMy father is a 100% VA-disabled US Army veteran. {STORY}\n\nThank you,\nCharles Alan Prescott Jr."),
    ("scholarships@military.com", "Military.com - Scholarship Inquiry", f"Dear Military.com,\n\n{STORY}\n\nThank you,\nCharles Alan Prescott Jr."),
    ("info@operationhomefront.org", "Operation Homefront - Scholarships", f"Dear Operation Homefront,\n\n{STORY}\n\nThank you,\nCharles Alan Prescott Jr."),
    
    # MORE DISABILITY
    ("info@aapd.com", "AAPD - Disability Scholarship", f"Dear AAPD,\n\n{STORY}\n\nThank you,\nCharles Alan Prescott Jr."),
    ("info@disabledscholar.org", "Disabled Scholar Fund", f"Dear Disabled Scholar Fund,\n\n{STORY}\n\nThank you,\nCharles Alan Prescott Jr."),
    ("contact@myspectrumsuite.com", "Spectrum Suite - Neurodiversity Scholarship", f"Dear Spectrum Suite,\n\n{STORY}\n\nThank you,\nCharles Alan Prescott Jr."),
    
    # MORE FAITH
    ("info@crcna.org", "CRCNA - Education Scholarships", f"Dear CRCNA,\n\n{STORY}\n\nThank you,\nCharles Alan Prescott Jr."),
    ("info@cofchrist.org", "Community of Christ - Scholarships", f"Dear Community of Christ,\n\n{STORY}\n\nThank you,\nCharles Alan Prescott Jr."),
    ("info@eccenter.org", "Evangelical Council - Scholarship Inquiry", f"Dear Evangelical Council,\n\n{STORY}\n\nThank you,\nCharles Alan Prescott Jr."),
    
    # MORE FOUNDATIONS
    ("info@craigshospital.org", "Craig Hospital - Scholarship Inquiry", f"Dear Craig Hospital,\n\n{STORY}\n\nThank you,\nCharles Alan Prescott Jr."),
    ("info@lillyendowment.org", "Lilly Endowment - Scholarship Inquiry", f"Dear Lilly Endowment,\n\n{STORY}\n\nPlease advise on any programs supporting theological students.\n\nThank you,\nCharles Alan Prescott Jr."),
    ("info@templeton.org", "Templeton Foundation - Scholarship Inquiry", f"Dear Templeton Foundation,\n\n{STORY}\n\nThank you,\nCharles Alan Prescott Jr."),
    ("info@teaglefoundation.org", "Teagle Foundation - Scholarship Inquiry", f"Dear Teagle Foundation,\n\n{STORY}\n\nThank you,\nCharles Alan Prescott Jr."),
    ("info@mellon.org", "Mellon Foundation - Scholarship Inquiry", f"Dear Mellon Foundation,\n\n{STORY}\n\nThank you,\nCharles Alan Prescott Jr."),
    ("info@ncf.org", "National Christian Foundation - Scholarship", f"Dear NCF,\n\n{STORY}\n\nThank you,\nCharles Alan Prescott Jr."),
    ("info@mustardseed.org", "Mustard Seed Foundation - Scholarship", f"Dear Mustard Seed Foundation,\n\n{STORY}\n\nThank you,\nCharles Alan Prescott Jr."),
    ("info@baughman.org", "Baughman Foundation - Scholarship Inquiry", f"Dear Baughman Foundation,\n\n{STORY}\n\nThank you,\nCharles Alan Prescott Jr."),
    ("info@walmartfoundation.org", "Walmart Foundation - Scholarship Inquiry", f"Dear Walmart Foundation,\n\n{STORY}\n\nThank you,\nCharles Alan Prescott Jr."),
    ("info@coca-colafoundation.org", "Coca-Cola Foundation - Scholarship Inquiry", f"Dear Coca-Cola Foundation,\n\n{STORY}\n\nThank you,\nCharles Alan Prescott Jr."),
    
    # MORE ADULT LEARNER
    ("info@adultstudent.org", "Adult Student - Scholarship Inquiry", f"Dear Adult Student,\n\n{STORY}\n\nThank you,\nCharles Alan Prescott Jr."),
    ("info@backtoschool.org", "Back to School - Scholarship Inquiry", f"Dear Back to School,\n\n{STORY}\n\nThank you,\nCharles Alan Prescott Jr."),
    
    # US STUDYING IN CANADA
    ("info@canada.ca", "Government of Canada - International Scholarships", f"Dear Government of Canada,\n\n{STORY}\n\nPlease advise on any scholarship programs for international students at Canadian universities.\n\nThank you,\nCharles Alan Prescott Jr."),
    ("info@ontario.ca", "Government of Ontario - Scholarship Programs", f"Dear Government of Ontario,\n\n{STORY}\n\nThank you,\nCharles Alan Prescott Jr."),
    ("info@toronto.ca", "City of Toronto - Education Grants", f"Dear City of Toronto,\n\n{STORY}\n\nThank you,\nCharles Alan Prescott Jr."),
    
    # JEWISH/INTERFAITH (since he's studying theology)
    ("info@ifcj.org", "IFCJ - Scholarship Inquiry", f"Dear IFCJ,\n\n{STORY}\n\nThank you,\nCharles Alan Prescott Jr."),
    ("info@abrahamic.org", "Abrahamic Foundation - Scholarship", f"Dear Abrahamic Foundation,\n\n{STORY}\n\nThank you,\nCharles Alan Prescott Jr."),
    
    # ADDITIONAL
    ("info@youngfoundation.org", "Young Foundation - Scholarship Inquiry", f"Dear Young Foundation,\n\n{STORY}\n\nThank you,\nCharles Alan Prescott Jr."),
    ("info@dysonfoundation.com", "Dyson Foundation - Scholarship Inquiry", f"Dear Dyson Foundation,\n\n{STORY}\n\nThank you,\nCharles Alan Prescott Jr."),
    ("info@moeckerfoundation.com", "Moecker Foundation - Scholarship", f"Dear Moecker Foundation,\n\n{STORY}\n\nThank you,\nCharles Alan Prescott Jr."),
    ("info@laughlintorokfoundation.org", "Laughlin-Torok Foundation - Scholarship", f"Dear Laughlin-Torok Foundation,\n\n{STORY}\n\nThank you,\nCharles Alan Prescott Jr."),
]

total = len(emails)
sent = 0

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
                time.sleep(30)
                continue
            print(f"❌ [{idx}/{total}] {to}")
        break
    
    time.sleep(2)

print(f"\n✅ Done! Sent: {sent}/{total}")
print(f"🏆 TOTAL SENT ACROSS ALL BATCHES: {12 + 25 + sent}")
