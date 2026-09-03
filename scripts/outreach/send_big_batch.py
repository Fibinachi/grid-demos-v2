import smtplib
import ssl
import os
import socket
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

socket.setdefaulttimeout(15)

SENDER = "charles@columbiataxlawyer.com"
PASS = os.environ.get("EMAIL_PASSWORD")
if not PASS:
    print("❌ EMAIL_PASSWORD not set")
    exit(1)

# Core essay to use in all
story = """I am a 44-year-old US citizen with a formal ADHD diagnosis, relocating to Toronto this September to enroll full-time in the Certificate in Theological Studies at Trinity College, University of Toronto. I hold a JD and an LLM in Taxation and am returning to school as a mature, first-generation student after a legal career. My annual income is approximately $55,000 USD and I am not eligible for US federal student loans. I am a member of Emmaus Church (Methodist tradition)."""

emails = [
    # VETERAN-DEPENDENT
    ("scholarships@fisherhouse.org", "Fisher House - Scholarships for Military Children", f"Dear Fisher House,\n\nMy father is a 100% VA-disabled US Army veteran. {story}\n\nPlease let me know about the Scholarships for Military Children program and whether late applications are possible.\n\nThank you,\nCharles Alan Prescott Jr.\ncharles@columbiataxlawyer.com"),
    ("info@militaryfamily.org", "NMFA - Military Spouse Scholarships", f"Dear NMFA,\n\nAs the child of a 100% VA-disabled veteran, I am writing about scholarship opportunities. {story}\n\nThank you,\nCharles Alan Prescott Jr."),
    
    # DISABILITY / NEURODIVERGENT
    ("info@chadd.org", "CHADD - ADHD Scholarship Info", f"Dear CHADD,\n\nI have a formal ADHD diagnosis. {story}\n\nPlease let me know about any scholarship opportunities for adults with ADHD pursuing graduate education.\n\nThank you,\nCharles Alan Prescott Jr."),
    ("info@ncld.org", "NCLD - Learning Disability Scholarships", f"Dear NCLD,\n\nI have a formal ADHD diagnosis. {story}\n\nPlease inform me about scholarship opportunities for students with learning disabilities/ADHD.\n\nThank you,\nCharles Alan Prescott Jr."),
    ("info@understood.org", "Understood - Adult Learner Grants", f"Dear Understood,\n\nAs an adult with ADHD returning to education, {story}\n\nThank you,\nCharles Alan Prescott Jr."),
    
    # FAITH / THEOLOGICAL
    ("info@pcusa.org", "PCUSA - Theological Scholarships", f"Dear Presbyterian Church (USA),\n\n{story}\n\nPlease let me know about any scholarship opportunities for theological study.\n\nThank you,\nCharles Alan Prescott Jr."),
    ("info@elca.org", "ELCA - Theological Education Scholarships", f"Dear ELCA,\n\n{story}\n\nPlease inform me about theological education scholarship opportunities.\n\nThank you,\nCharles Alan Prescott Jr."),
    ("info@rca.org", "Reformed Church in America - Scholarships", f"Dear RCA,\n\n{story}\n\nThank you,\nCharles Alan Prescott Jr."),
    ("info@americanbible.org", "American Bible Society - Scholarships", f"Dear American Bible Society,\n\n{story}\n\nThank you,\nCharles Alan Prescott Jr."),
    ("info@biblegateway.com", "Bible Gateway - Scholarship Inquiry", f"Dear Bible Gateway,\n\n{story}\n\nThank you,\nCharles Alan Prescott Jr."),
    
    # FOUNDATIONS
    ("scholarships@horatioalger.org", "Horatio Alger - Graduate Scholarship Inquiry", f"Dear Horatio Alger Association,\n\n{story}\n\nPlease advise on any graduate scholarship opportunities.\n\nThank you,\nCharles Alan Prescott Jr."),
    ("info@sctfoundation.org", "SCT Foundation - Scholarship Inquiry", f"Dear SCT Foundation,\n\n{story}\n\nThank you,\nCharles Alan Prescott Jr."),
    ("info@wsf.org", "Washington Scholarship Fund - Inquiry", f"Dear Washington Scholarship Fund,\n\n{story}\n\nThank you,\nCharles Alan Prescott Jr."),
    ("info@cfnc.org", "Community Foundation of NC - Scholarship Inquiry", f"Dear Community Foundation,\n\n{story}\n\nThank you,\nCharles Alan Prescott Jr."),
    ("info@bostonfoundation.org", "Boston Foundation - Scholarship Inquiry", f"Dear Boston Foundation,\n\n{story}\n\nThank you,\nCharles Alan Prescott Jr."),
    ("info@fndpa.org", "Florida Nonprofit Alliance - Scholarship Inquiry", f"Dear FNDPA,\n\n{story}\n\nThank you,\nCharles Alan Prescott Jr."),
    ("info@ecmc.org", "ECMC Foundation - Scholarship Inquiry", f"Dear ECMC,\n\n{story}\n\nThank you,\nCharles Alan Prescott Jr."),

    # CANADIAN / U of T
    ("awards@utoronto.ca", "U of T - General Bursaries & Awards", f"Dear U of T Awards Office,\n\n{story}\n\nPlease let me know about any bursaries or awards available to international students in theological studies.\n\nThank you,\nCharles Alan Prescott Jr."),
    ("international.centre@utoronto.ca", "U of T - International Student Funding", f"Dear U of T International Centre,\n\n{story}\n\nPlease advise on funding resources for US citizens studying at U of T.\n\nThank you,\nCharles Alan Prescott Jr."),
    ("info@univcan.ca", "Universities Canada - Scholarship Inquiry", f"Dear Universities Canada,\n\n{story}\n\nPlease let me know about any scholarship programs for international students at Canadian universities.\n\nThank you,\nCharles Alan Prescott Jr."),
    ("info@cmec.ca", "CMEC - Canadian Education Scholarships", f"Dear CMEC,\n\n{story}\n\nThank you,\nCharles Alan Prescott Jr."),
    
    # GENERAL EDUCATION
    ("info@collegeboard.org", "College Board - Scholarship Search Inquiry", f"Dear College Board,\n\n{story}\n\nThank you,\nCharles Alan Prescott Jr."),
    ("info@act.org", "ACT - Scholarship Inquiry", f"Dear ACT,\n\n{story}\n\nThank you,\nCharles Alan Prescott Jr."),
    ("info@aacrao.org", "AACRAO - International Education Scholarships", f"Dear AACRAO,\n\n{story}\n\nThank you,\nCharles Alan Prescott Jr."),
    ("info@nafusa.org", "NAFSA - International Student Scholarships", f"Dear NAFSA,\n\n{story}\n\nThank you,\nCharles Alan Prescott Jr."),
    ("info@iie.org", "IIE - Scholarship Programs", f"Dear IIE,\n\n{story}\n\nPlease let me know about any scholarship programs for US citizens studying abroad.\n\nThank you,\nCharles Alan Prescott Jr."),

    # SOUTH CAROLINA SPECIFIC
    ("info@che.sc.gov", "SC Commission on Higher Ed - Scholarships", f"Dear SC CHE,\n\nI am a SC resident. {story}\n\nPlease advise on any state scholarship opportunities.\n\nThank you,\nCharles Alan Prescott Jr."),
    ("info@scstudentloan.org", "SC Student Loan - Scholarship Inquiry", f"Dear SC Student Loan,\n\n{story}\n\nThank you,\nCharles Alan Prescott Jr."),

    # FIRST GENERATION
    ("info@firstgenfoundation.org", "First Gen Foundation - Scholarship", f"Dear First Gen Foundation,\n\nAs a first-generation graduate student, {story}\n\nThank you,\nCharles Alan Prescott Jr."),
    ("info@imfirst.org", "I'm First - Scholarship Inquiry", f"Dear I'm First,\n\n{story}\n\nThank you,\nCharles Alan Prescott Jr."),

    # ADULT LEARNER
    ("info@ahea.org", "AHEA - Adult Higher Education Scholarships", f"Dear AHEA,\n\nAs an adult returning learner, {story}\n\nThank you,\nCharles Alan Prescott Jr."),
    ("info@upcea.edu", "UPCEA - Continuing Education Scholarships", f"Dear UPCEA,\n\n{story}\n\nThank you,\nCharles Alan Prescott Jr."),

    # INTERNATIONAL STUDY
    ("info@goabroad.com", "GoAbroad - Scholarship Inquiry", f"Dear GoAbroad,\n\n{story}\n\nThank you,\nCharles Alan Prescott Jr."),
    ("info@studyabroad.com", "StudyAbroad - Funding Inquiry", f"Dear StudyAbroad.com,\n\n{story}\n\nThank you,\nCharles Alan Prescott Jr."),
    ("info@iesabroad.org", "IES Abroad - Scholarship Inquiry", f"Dear IES Abroad,\n\n{story}\n\nThank you,\nCharles Alan Prescott Jr."),
]

# Also save to a file
with open("email_batch_body.txt", "w") as f:
    for to, subj, body in emails:
        f.write(f"=== {to} === {subj} ===\n{body}\n\n===\n\n")

print(f"📝 {len(emails)} emails written. Sending now...")

sent_count = 0
for to, subj, body in emails:
    msg = MIMEMultipart()
    msg["From"] = SENDER
    msg["To"] = to
    msg["Subject"] = subj
    msg.attach(MIMEText(body, "plain"))
    
    for port, tls in [(587, True), (465, False)]:
        try:
            if tls:
                with smtplib.SMTP("smtp.hostinger.com", port) as s:
                    s.ehlo()
                    s.starttls(context=ssl.create_default_context())
                    s.ehlo()
                    s.login(SENDER, PASS)
                    s.sendmail(SENDER, to, msg.as_string())
            else:
                ctx = ssl.create_default_context()
                with smtplib.SMTP_SSL("smtp.hostinger.com", port, ctx=ctx) as s:
                    s.login(SENDER, PASS)
                    s.sendmail(SENDER, to, msg.as_string())
            print(f"✅ {to}")
            sent_count += 1
            break
        except:
            pass
    else:
        print(f"❌ {to}")

print(f"\n✅ Sent: {sent_count} / {len(emails)}")
print(f"📄 Full text saved to email_batch_body.txt")
