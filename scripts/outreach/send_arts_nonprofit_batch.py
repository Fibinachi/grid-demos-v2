import smtplib, ssl, os, time, socket
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

socket.setdefaulttimeout(10)
SENDER = "charles@columbiataxlawyer.com"
PASS = os.environ.get("EMAIL_PASSWORD")
if not PASS:
    print("❌ EMAIL_PASSWORD not set"); exit(1)

STORY = """I am a 44-year-old US citizen who earned a BA in Political Science from Coastal Carolina University (2009), my JD from Rutgers Law School (David Delgones Award), and my LLM in Taxation from the University of Alabama School of Law. I scored 143 (99.8th percentile) on the WAIS-III at age 10. I have served as Founding Director of the Midlands Light Opera Society, formed churches as an attorney, founded Healthy Connections (health nonprofit, Myrtle Beach), founded a cancer kid charity, and taught CLEs. I have an IMDb credit in film distribution and formal ADHD and MDD diagnoses. I am the father of three children, two diagnosed with autism. My father is a 100% VA-disabled US Army veteran. I am relocating to Toronto this September for the Certificate in Theological Studies at Trinity College, University of Toronto, returning as a mature, first-generation student. Income ~$55K USD, no federal loan eligibility. Member of Emmaus Church (Methodist tradition)."""

emails = [
    # CCU ALUMNI
    ("alumni@coastal.edu", "Coastal Carolina University - Alumni Continuing Education Grant", f"Dear CCU Alumni Association,\n\nI am a 2009 graduate of Coastal Carolina University (BA Political Science). I am writing to ask about any alumni scholarship or continuing education grant programs for CCU graduates pursuing further studies in theology.\n\n{STORY}\n\nThank you,\nCharles Alan Prescott Jr.\ncharles@columbiataxlawyer.com\n843-504-4542"),
    
    # ARTS / THEATER
    ("info@shubertfoundation.org", "Shubert Foundation - Education Grant Inquiry", f"Dear Shubert Foundation,\n\nI am the Founding Director of the Midlands Light Opera Society and am writing to inquire about any education grants or scholarship programs for individuals with theater/opera leadership experience who are pursuing further education.\n\n{STORY}\n\nThank you,\nCharles Alan Prescott Jr.\ncharles@columbiataxlawyer.com\n843-504-4542"),
    
    ("info@operaamerica.org", "Opera America - Education Support Inquiry", f"Dear Opera America,\n\nI served as Founding Director of the Midlands Light Opera Society and am writing to ask about any scholarship, grant, or education programs for opera/theater leaders pursuing further education.\n\n{STORY}\n\nThank you,\nCharles Alan Prescott Jr.\ncharles@columbiataxlawyer.com\n843-504-4542"),
    
    ("info@tcg.org", "Theatre Communications Group - Grant Inquiry", f"Dear TCG,\n\nAs the Founding Director of the Midlands Light Opera Society, I am writing to inquire about any professional development or education support programs for theater practitioners seeking to expand their studies.\n\n{STORY}\n\nThank you,\nCharles Alan Prescott Jr.\ncharles@columbiataxlawyer.com\n843-504-4542"),
    
    ("info@arts.gov", "National Endowment for the Arts - Grant Inquiry", f"Dear NEA,\n\nI am the Founding Director of the Midlands Light Opera Society and an attorney who formed churches and nonprofits. I am writing to ask about any grant or fellowship programs that support individuals with arts leadership experience pursuing education in theology and ethics.\n\n{STORY}\n\nThank you,\nCharles Alan Prescott Jr.\ncharles@columbiataxlawyer.com\n843-504-4542"),
    
    ("info@southcarolinaarts.org", "SC Arts Commission - Scholarship Inquiry", f"Dear SC Arts Commission,\n\nAs the Founding Director of the Midlands Light Opera Society and a lifelong South Carolina native, I am writing to inquire about any scholarship or grant programs for arts leaders pursuing further education.\n\n{STORY}\n\nThank you,\nCharles Alan Prescott Jr.\ncharles@columbiataxlawyer.com\n843-504-4542"),
    
    # NONPROFIT LEADERSHIP
    ("info@boardsource.org", "BoardSource - Nonprofit Leader Scholarship Inquiry", f"Dear BoardSource,\n\nI have founded multiple nonprofits (Healthy Connections, cancer kid charity, Midlands Light Opera Society) and formed churches as an attorney. I am writing to ask about any education support or scholarship programs for nonprofit leaders pursuing further education.\n\n{STORY}\n\nThank you,\nCharles Alan Prescott Jr.\ncharles@columbiataxlawyer.com\n843-504-4542"),
    
    ("info@independentcharity.org", "Independent Charity - Nonprofit Education Grant", f"Dear Independent Charity,\n\nAs a nonprofit founder (Healthy Connections, cancer kid charity), I am writing to inquire about any grants or scholarships for nonprofit leaders pursuing theological education.\n\n{STORY}\n\nThank you,\nCharles Alan Prescott Jr.\ncharles@columbiataxlawyer.com\n843-504-4542"),
    
    # HEALTH / CANCER CHARITY
    ("info@cancerresearch.org", "Cancer Research Institute - Education Grant Inquiry", f"Dear Cancer Research Institute,\n\nI founded a cancer kid charity and a health nonprofit (Healthy Connections in Myrtle Beach). I am writing to ask about any scholarship or education support programs for individuals with a background in health/charity work who are pursuing further education.\n\n{STORY}\n\nThank you,\nCharles Alan Prescott Jr.\ncharles@columbiataxlawyer.com\n843-504-4542"),
    
    ("info@alexslivinghope.org", "Alex's Lemonade Stand - Childhood Cancer Charity Support", f"Dear Alex's Lemonade Stand,\n\nAs someone who founded a cancer kid charity, I am writing to inquire about any education grants or scholarship programs for individuals with a background in childhood cancer charity work.\n\n{STORY}\n\nThank you,\nCharles Alan Prescott Jr.\ncharles@columbiataxlawyer.com\n843-504-4542"),
    
    ("info@stbaldricks.org", "St. Baldrick's Foundation - Grant Inquiry", f"Dear St. Baldrick's Foundation,\n\nI founded a cancer kid charity and am writing to ask about any education support programs for individuals dedicated to childhood cancer causes who are pursuing further education.\n\n{STORY}\n\nThank you,\nCharles Alan Prescott Jr.\ncharles@columbiataxlawyer.com\n843-504-4542"),
    
    # LEGAL EDUCATION / CLE
    ("info@ali.org", "American Law Institute - CLE Instructor Scholarship", f"Dear American Law Institute,\n\nAs a CLE instructor and Rutgers Law graduate (David Delgones Award), I am writing to inquire about any scholarship or education support programs for legal educators pursuing further studies in theology and ethics.\n\n{STORY}\n\nThank you,\nCharles Alan Prescott Jr.\ncharles@columbiataxlawyer.com\n843-504-4542"),
    
    ("info@americanbar.org", "American Bar Association - Education Grant Inquiry", f"Dear ABA,\n\nI am a Rutgers Law graduate (David Delgones Award), CLE instructor, and practicing attorney who formed churches and nonprofits. I am writing to ask about any scholarship or grant programs for attorneys pursuing theological education.\n\n{STORY}\n\nThank you,\nCharles Alan Prescott Jr.\ncharles@columbiataxlawyer.com\n843-504-4542"),
    
    # OUTDOOR / CONSERVATION (hunt, fish, scuba)
    ("info@ducks.org", "Ducks Unlimited - Conservation Education Grant Inquiry", f"Dear Ducks Unlimited,\n\nI am an avid hunter and fisherman and am writing to inquire about any education grants or scholarship programs for outdoor conservation enthusiasts pursuing further education in theology and ethics.\n\n{STORY}\n\nThank you,\nCharles Alan Prescott Jr.\ncharles@columbiataxlawyer.com\n843-504-4542"),
    
    ("info@rmef.org", "Rocky Mountain Elk Foundation - Scholarship Inquiry", f"Dear RMEF,\n\nAs a hunter and conservation-minded outdoorsman, I am writing to inquire about any scholarship or education grant programs for members/supporters pursuing further education.\n\n{STORY}\n\nThank you,\nCharles Alan Prescott Jr.\ncharles@columbiataxlawyer.com\n843-504-4542"),
    
    ("info@nwtf.org", "National Wild Turkey Federation - Education Grant", f"Dear NWTF,\n\nI am an avid hunter and outdoorsman. I am writing to ask about any scholarship or education grant programs for hunters/conservationists pursuing further education.\n\n{STORY}\n\nThank you,\nCharles Alan Prescott Jr.\ncharles@columbiataxlawyer.com\n843-504-4542"),
    
    ("info@joincca.org", "Coastal Conservation Association - Scholarship Inquiry", f"Dear CCA,\n\nI am an avid fisherman and certified scuba diver. I am writing to inquire about any scholarship or education grant programs for members pursuing further education.\n\n{STORY}\n\nThank you,\nCharles Alan Prescott Jr.\ncharles@columbiataxlawyer.com\n843-504-4542"),
    
    ("info@deltafoundation.org", "Delta Waterfowl - Education Grant Inquiry", f"Dear Delta Waterfowl,\n\nAs a hunter and outdoorsman, I am writing to ask about any scholarship or education grant programs for members pursuing advanced education.\n\n{STORY}\n\nThank you,\nCharles Alan Prescott Jr.\ncharles@columbiataxlawyer.com\n843-504-4542"),
    
    # UNIVERSITY OF ALABAMA ALUMNI
    ("scholarships@ua.edu", "University of Alabama - Alumni Continuing Education Scholarship", f"Dear University of Alabama,\n\nI earned my LLM in Taxation from the University of Alabama School of Law. I am writing to inquire about any alumni scholarship or continuing education grant programs for Alabama graduates pursuing further studies.\n\n{STORY}\n\nThank you,\nCharles Alan Prescott Jr.\ncharles@columbiataxlawyer.com\n843-504-4542"),
    
    ("alumni@law.ua.edu", "Alabama Law Alumni - Continuing Education Support", f"Dear Alabama Law Alumni Association,\n\nI earned my LLM in Taxation from the University of Alabama School of Law. I am writing to ask about any scholarship or grant programs for alumni pursuing advanced degrees or certificates in other fields.\n\n{STORY}\n\nThank you,\nCharles Alan Prescott Jr.\ncharles@columbiataxlawyer.com\n843-504-4542"),
    
    # RUTGERS ALUMNI
    ("alumni@law.rutgers.edu", "Rutgers Law Alumni - Continuing Education Scholarship", f"Dear Rutgers Law Alumni Association,\n\nI am a Rutgers Law graduate (JD, David Delgones Award). I am writing to ask about any alumni scholarship or continuing education grant programs for Rutgers Law graduates pursuing further studies.\n\n{STORY}\n\nThank you,\nCharles Alan Prescott Jr.\ncharles@columbiataxlawyer.com\n843-504-4542"),
    
    # HEALTHY CONNECTIONS / COMMUNITY HEALTH
    ("info@healthfoundation.org", "Health Foundation - Community Health Leader Grant", f"Dear Health Foundation,\n\nI founded Healthy Connections, a health nonprofit in Myrtle Beach, and a cancer kid charity. I am writing to inquire about any education grants or scholarship programs for community health leaders pursuing further education in theology and ethics.\n\n{STORY}\n\nThank you,\nCharles Alan Prescott Jr.\ncharles@columbiataxlawyer.com\n843-504-4542"),
    
    # UNION / ALCOA FAMILY
    ("scholarships@unionplus.org", "Union Plus Scholarship - USW Grandfather Descendant Inquiry", f"Dear Union Plus Education Foundation,\n\nMy grandfather worked at Alcoa and was a proud member of the United Steelworkers (USW). I am writing to inquire about eligibility for the Union Plus Scholarship Program as a descendant of a union family. I understand the 2027 application opens at the end of June 2026 and awards range from $1,000 to $4,000.\n\n{STORY}\n\nPlease let me know about eligibility requirements and how to apply.\n\nThank you,\nCharles Alan Prescott Jr.\ncharles@columbiataxlawyer.com\n843-504-4542"),
    
    # FLORIDA-BORN (state native scholarships)
    ("info@floridastudentfinancialaid.org", "Florida Native - State Scholarship Inquiry", f"Dear Florida Student Financial Aid,\n\nI was born in Florida and am writing to inquire about any scholarship or grant programs for Florida natives/former residents who are pursuing higher education.\n\n{STORY}\n\nThank you,\nCharles Alan Prescott Jr.\ncharles@columbiataxlawyer.com\n843-504-4542"),
]

total = len(emails)
sent = 0

print(f"📝 Sending {total} arts/nonprofit/community/legal education inquiries...")
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
