import smtplib, ssl, os, time, socket
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

socket.setdefaulttimeout(10)
SENDER = "charles@columbiataxlawyer.com"
PASS = os.environ.get("EMAIL_PASSWORD")
if not PASS:
    print("❌ EMAIL_PASSWORD not set"); exit(1)

STORY = "I am a 44-year-old father of three children, two of whom have been diagnosed with autism. I am a US citizen with formal ADHD and MDD diagnoses. I earned a BA in Political Science from Coastal Carolina University (2009), my JD from Rutgers Law School (David Delgones Award), and my LLM in Taxation from the University of Alabama School of Law. I scored 143 (99.8th percentile) on the WAIS-III at age 10. I have served as Founding Director of the Midlands Light Opera Society, formed churches as an attorney, and founded health and cancer charities. I am relocating to Toronto this September for the Certificate in Theological Studies at Trinity College, U of T, returning as a mature, first-generation student. Income ~$55K USD, no federal loan eligibility. Member of Emmaus Church. My father is a 100% VA-disabled US Army veteran."

emails = [
    # AUTISM PARENT SUPPORT
    ("info@flutiefoundation.org", "Doug Flutie Jr. Foundation - Family Grant Inquiry", f"Dear Flutie Foundation,\n\nI am the father of two children with autism and am reaching out to inquire about any family grants or education support programs that might help a parent pursuing higher education while caring for autistic children.\n\n{STORY}\n\nPlease let me know about any grant programs for which I might be eligible.\n\nThank you,\nCharles Alan Prescott Jr."),
    
    ("info@act-today.org", "Autism Care Today - Family Grant Inquiry", f"Dear ACT Today!,\n\nI am writing to inquire about family grant programs. I am a father of two children with autism, returning to school for theological studies.\n\n{STORY}\n\nPlease advise on any available grants or scholarships.\n\nThank you,\nCharles Alan Prescott Jr."),
    
    ("info@tacanow.org", "TACA - Family Support Grant Inquiry", f"Dear TACA,\n\nI am a father of two children with autism seeking information about family support programs or education grants for parents.\n\n{STORY}\n\nThank you,\nCharles Alan Prescott Jr."),
    
    ("research@researchautism.org", "OAR - Family Support Programs Inquiry", f"Dear Organization for Autism Research,\n\nI am writing to inquire about any programs or grants supporting parents of children with autism who are pursuing higher education.\n\n{STORY}\n\nThank you,\nCharles Alan Prescott Jr."),
    
    ("naa@nationalautismassociation.org", "National Autism Association - Family Grant Inquiry", f"Dear National Autism Association,\n\nI am the father of two children diagnosed with autism. I am inquiring about any family assistance or education grant programs available.\n\n{STORY}\n\nThank you,\nCharles Alan Prescott Jr."),
    
    ("info@autism-society.org", "Autism Society - Education Support Inquiry", f"Dear Autism Society of America,\n\nI am writing to ask about any scholarship, grant, or education support programs for parents of children with autism who are pursuing their own education.\n\n{STORY}\n\nThank you,\nCharles Alan Prescott Jr."),
    
    ("info@hussmanfoundation.org", "Hussman Foundation - Family Support Inquiry", f"Dear Hussman Foundation,\n\nI am a father of two children with autism seeking information about programs supporting parents pursuing education.\n\n{STORY}\n\nThank you,\nCharles Alan Prescott Jr."),
    
    ("info@nlmfoundation.org", "Nancy Lurie Marks Foundation - Grant Inquiry", f"Dear Nancy Lurie Marks Family Foundation,\n\nI am writing to inquire about any grant programs that might support a parent of autistic children pursuing theological education.\n\n{STORY}\n\nThank you,\nCharles Alan Prescott Jr."),
    
    ("info@khgfoundation.org", "Kelly Heinz-Grundy Foundation - Family Grant Inquiry", f"Dear Kelly Heinz-Grundy Foundation,\n\nI am the father of two children with autism. I am writing to inquire about any family grant or education support programs.\n\n{STORY}\n\nThank you,\nCharles Alan Prescott Jr."),
    
    ("info@gracefoundation.com", "Grace Foundation - Autism Family Support Inquiry", f"Dear Grace Foundation,\n\nI am writing to inquire about any grant or scholarship programs for parents of children with autism pursuing higher education.\n\n{STORY}\n\nThank you,\nCharles Alan Prescott Jr."),
    
    # DISABILITY PARENT SUPPORT
    ("info@thearc.org", "The Arc - Parent Education Grants Inquiry", f"Dear The Arc,\n\nI am a father of two children with disabilities (autism) and am writing to ask about any education grants or scholarship programs for parents of children with disabilities.\n\n{STORY}\n\nThank you,\nCharles Alan Prescott Jr."),
    
    ("info@504foundation.org", "504 Foundation - Parent Education Grant Inquiry", f"Dear 504 Foundation,\n\nI am the father of two children with autism and am writing to ask about any grant programs for parents pursuing higher education.\n\n{STORY}\n\nThank you,\nCharles Alan Prescott Jr."),
    
    ("info@childrensdisabilityfoundation.org", "Children's Disability Foundation - Education Grant Inquiry", f"Dear Children's Disability Foundation,\n\nI am writing to ask about any grant programs supporting parents of children with disabilities who are pursuing their own education.\n\n{STORY}\n\nThank you,\nCharles Alan Prescott Jr."),
    
    # SC AUTISM RESOURCES
    ("info@scautism.org", "SC Autism Society - Education Support Inquiry", f"Dear SC Autism Society,\n\nI am a South Carolina native and father of two children with autism. I am writing to ask about any scholarship, grant, or education support programs for parents of autistic children.\n\n{STORY}\n\nThank you,\nCharles Alan Prescott Jr."),
]

total = len(emails)
sent = 0

print(f"📝 Sending {total} autism/parent of disabled children inquiries...")
print(f"   ⚠ SMTP must be unblocked — retrying every 30s up to 30 attempts each")

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
