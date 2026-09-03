"""
7-Day Follow-Up Email Script
Run this 7 days after the initial sends to double response rates.
Sends a polite "checking in" follow-up to all 43+ recipients.

Usage: python follow_up_day7.py
"""
import smtplib, ssl, os, sys, time

PASS = os.environ.get("EMAIL_PASSWORD")
if not PASS:
    print("ERROR: EMAIL_PASSWORD not set"); sys.exit(1)

SENDER = "charles@columbiataxlawyer.com"

# All 43+ targets that were sent
follow_ups = [
    # Mensa/High-IQ (4)
    ("info@americanmensa.org", "American Mensa - Follow-up"),
    ("foundation@mensafoundation.org", "Mensa Foundation - Follow-up"),
    ("contact@intertel-iq.org", "Intertel - Follow-up"),
    ("sc@mensa.org", "SC Mensa - Follow-up"),
    
    # Autism Parent (14)
    ("info@flutiefoundation.org", "Flutie Foundation - Follow-up"),
    ("info@act-today.org", "ACT Today - Follow-up"),
    ("info@tacanow.org", "TACA - Follow-up"),
    ("research@researchautism.org", "OAR - Follow-up"),
    ("naa@nationalautismassociation.org", "NAA - Follow-up"),
    ("info@autism-society.org", "Autism Society - Follow-up"),
    ("info@hussmanfoundation.org", "Hussman Foundation - Follow-up"),
    ("info@nlmfoundation.org", "NLMF - Follow-up"),
    ("info@khgfoundation.org", "KHG Foundation - Follow-up"),
    ("info@gracefoundation.com", "Grace Foundation - Follow-up"),
    ("info@thearc.org", "The Arc - Follow-up"),
    ("info@504foundation.org", "504 Foundation - Follow-up"),
    ("info@childrensdisabilityfoundation.org", "Children's Disability - Follow-up"),
    ("info@scautism.org", "SC Autism - Follow-up"),
    
    # Film Industry (8)
    ("info@mptf.com", "MPTF - Follow-up"),
    ("info@filmindependent.org", "Film Independent - Follow-up"),
    ("info@hpaonline.com", "HPA - Follow-up"),
    ("info@oscars.org", "Academy - Follow-up"),
    ("info@sagaftra.foundation", "SAG-AFTRA - Follow-up"),
    ("info@documentary.org", "IDA - Follow-up"),
    ("info@sundance.org", "Sundance - Follow-up"),
    ("info@nabef.org", "NABEF - Follow-up"),
    
    # Arts/Nonprofit/Community (24)
    ("alumni@coastal.edu", "CCU Alumni - Follow-up"),
    ("info@shubertfoundation.org", "Shubert - Follow-up"),
    ("info@operaamerica.org", "Opera America - Follow-up"),
    ("info@tcg.org", "TCG - Follow-up"),
    ("info@arts.gov", "NEA - Follow-up"),
    ("info@southcarolinaarts.org", "SC Arts - Follow-up"),
    ("info@boardsource.org", "BoardSource - Follow-up"),
    ("info@independentcharity.org", "Independent Charity - Follow-up"),
    ("info@cancerresearch.org", "Cancer Research - Follow-up"),
    ("info@alexslivinghope.org", "Alex's Lemonade - Follow-up"),
    ("info@stbaldricks.org", "St. Baldrick's - Follow-up"),
    ("info@ali.org", "ALI - Follow-up"),
    ("info@americanbar.org", "ABA - Follow-up"),
    ("info@ducks.org", "Ducks Unlimited - Follow-up"),
    ("info@rmef.org", "RMEF - Follow-up"),
    ("info@nwtf.org", "NWTF - Follow-up"),
    ("info@joincca.org", "CCA - Follow-up"),
    ("info@deltafoundation.org", "Delta Waterfowl - Follow-up"),
    ("scholarships@ua.edu", "UA Alumni - Follow-up"),
    ("alumni@law.ua.edu", "Alabama Law - Follow-up"),
    ("alumni@law.rutgers.edu", "Rutgers Law - Follow-up"),
    ("scholarships@unionplus.org", "Union Plus - Follow-up"),
    ("info@healthfoundation.org", "Health Foundation - Follow-up"),
    ("info@floridastudentfinancialaid.org", "FL Student Aid - Follow-up"),
    
    # Lineage/Heritage (6)
    ("info@southcarolinasc.org", "SC Society - Follow-up"),
    ("info@nsdar.org", "DAR - Follow-up"),
    ("info@scphilanthropy.org", "SC Philanthropy - Follow-up"),
    ("info@sc-education.org", "SC Education - Follow-up"),
    ("info@scpreservation.org", "SC Preservation - Follow-up"),
    ("info@huguenotsociety.org", "Huguenot Society - Follow-up"),
    
    # Already sent (12) - from earlier
    ("foundation@anglicanfoundation.org", "Anglican Foundation - Follow-up"),
    ("info@umcmission.org", "Global Ministries - Follow-up"),
    ("umscholar@gbhem.org", "GBHEM - Follow-up"),
    ("scholarships@united-church.ca", "UCC Foundation - Follow-up"),
    ("info@methodistfoundation.org", "Methodist Foundation - Follow-up"),
    ("info@rotarycolumbiasc.org", "Rotary Columbia - Follow-up"),
    ("scholarships@autismspeaks.org", "Autism Speaks - Follow-up"),
    ("info@limeconnect.com", "Lime Connect - Follow-up"),
    ("scholarships@add.org", "ADDA - Follow-up"),
    ("info@legion-aux.org", "AL Auxiliary - Follow-up"),
    ("info@dav.org", "DAV - Follow-up"),
]

FOLLOW_UP_BODY = """Dear [Organization],

I wanted to follow up on my inquiry below — I understand how busy you must be. If there's a more appropriate contact or application process, I'd be grateful for any direction.

To recap briefly: I am a 44-year-old US citizen, first-generation college graduate, father of three (two autistic). I hold a JD from Rutgers Law School (David Delgones Award) and an LLM in Taxation from the University of Alabama. I am relocating to Toronto this September to study theology at Trinity College, University of Toronto. I am seeking approximately $30,000 CAD to fund this transition.

Thank you again for your time and consideration.

Warm regards,
Charles Alan Prescott Jr.
charles@columbiataxlawyer.com
843-504-4542"""

def send_followup(to, subject):
    body = FOLLOW_UP_BODY
    msg = "From: %s\r\nTo: %s\r\nSubject: %s\r\nContent-Type: text/plain; charset=UTF-8\r\n\r\n%s" % (SENDER, to, subject, body)
    try:
        s = smtplib.SMTP("smtp.hostinger.com", 587, timeout=30)
        s.ehlo()
        s.starttls(context=ssl.create_default_context())
        s.ehlo()
        s.login(SENDER, PASS)
        s.sendmail(SENDER, to, msg.encode("utf-8"))
        s.quit()
        return True
    except Exception as e:
        return False

print("=== 7-DAY FOLLOW-UP SCRIPT ===")
print("Targets: %d" % len(follow_ups))
print()

sent = 0
failed = 0
for i, (to, subj) in enumerate(follow_ups, 1):
    print("[%d/%d] %s..." % (i, len(follow_ups), to), end=" ")
    sys.stdout.flush()
    if send_followup(to, subj):
        sent += 1
        print("SENT")
    else:
        failed += 1
        print("FAILED")
    
    if i % 10 == 0:
        print("  Progress: %d sent, %d failed" % (sent, failed))
    
    # 30s delay between follow-ups
    if i < len(follow_ups):
        time.sleep(30)

print()
print("=== DONE ===")
print("Sent:   %d" % sent)
print("Failed: %d" % failed)
print("Total:  %d" % len(follow_ups))
