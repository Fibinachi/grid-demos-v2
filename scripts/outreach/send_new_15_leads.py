"""
Send inquiries to 15 theological funding organizations.
References RA (Research Associate) status at Trinity College as institutional anchor.
"""
import os, sys, json, base64, time
from email.message import EmailMessage
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
TOKEN_FILE = os.path.join(SCRIPT_DIR, "gmail_token.json")
CREDENTIALS_FILE = os.path.join(SCRIPT_DIR, "gmail_credentials.json")
SCOPES = ['https://www.googleapis.com/auth/gmail.modify']
SENDER_NAME = "Charles Prescott"
SENDER_EMAIL = "charlesaprescottjr@gmail.com"

CURATED_LOG = os.path.join(SCRIPT_DIR, "curated_sent_log.txt")

LEADS = [
    ("Lilly Endowment (Religion Division)", "religion@lei.org",
     "Lilly Endowment's Religion Division has a historic commitment to theological education and clergy formation. As a Research Associate at Trinity College, University of Toronto, I am pursuing a Certificate in Theological Studies with a research focus on the theology of risk management — examining how institutions navigate moral and legal accountability through the lens of game theory and theological ethics."),
    
    ("Louisville Institute", "info@louisville-institute.org",
     "The Louisville Institute supports research at the intersection of church and academy. My Research Associate status at Trinity College, University of Toronto provides the institutional affiliation required for consideration. My research examines how theological ethics can speak to institutional moral failure — a theme I believe resonates with contemporary challenges facing the church."),
    
    ("Templeton Religion Trust", "info@templetonreligiontrust.org",
     "Templeton Religion Trust funds research on human flourishing, cognition, and ethics. My proposed research integrates game theory, moral psychology, and theological ethics to explore how institutions make decisions under conditions of moral and legal risk. As a Research Associate at Trinity College, University of Toronto — an institution founded in the Anglican tradition of reasoned faith — I have the institutional home to pursue this interdisciplinary work."),
    
    ("Calvin Institute of Christian Worship", "worship@calvin.edu",
     "The Calvin Institute of Christian Worship supports theological research and formation. As a Research Associate at Trinity College, University of Toronto, I am exploring how worship practices and theological commitments shape institutional ethics — work that sits at the intersection of liturgical theology and organizational behavior."),
    
    ("Forum for Theological Exploration (FTE)", "info@fteleaders.org",
     "FTE funds early-career theological scholars. As a Research Associate at Trinity College, University of Toronto — a first-generation graduate student who left a 15-year legal career to pursue theological study — I represent the kind of nontraditional path FTE supports. My research on the theology of risk management asks how institutions can be held morally accountable in a world of complex systems and competing loyalties."),
    
    ("Collegeville Institute", "info@collegevilleinstitute.org",
     "The Collegeville Institute supports writing and research residencies for theological scholars. My Research Associate status at Trinity College provides the institutional credibility for such a residency. I am developing a project on the theology of risk management — examining how institutions navigate moral and legal accountability — and would welcome the opportunity to pursue this work in a residential scholarly community."),
    
    ("McDonald Agape Foundation", "info@mcdonaldagape.org",
     "The McDonald Agape Foundation funds Christian scholarship and leadership development. As a Research Associate at Trinity College, University of Toronto, I am pursuing theological study after a 15-year career in law, with a focus on how Christian ethics can inform institutional leadership and moral accountability."),
    
    ("The Issachar Fund", "info@issacharfund.org",
     "The Issachar Fund supports Christian research on culture, ethics, and society. My background as a tax attorney who formed religious organizations, combined with my current theological research at Trinity College, positions me to examine how Christian ethical reasoning can speak to the moral challenges facing contemporary institutions."),
    
    ("The Carpenter Foundation", "info@carpenter-foundation.org",
     "The Carpenter Foundation supports religious and educational initiatives. As a Research Associate at Trinity College, University of Toronto, I am pursuing research on the theology of risk management — work that asks how institutions can be structured to serve both their stated missions and the common good with integrity."),
    
    ("The Kern Family Foundation", "info@kernfamilyfoundation.org",
     "The Kern Family Foundation funds character formation, ethics, and leadership development. My research on the theology of risk management directly engages questions of institutional character and moral leadership. As a Research Associate at Trinity College, I have the academic home to develop this work with rigor and depth."),
    
    ("The Duke Endowment (Religion Division)", "religion@dukeendowment.org",
     "The Duke Endowment's Religion Division funds clergy formation and theological education in the Carolinas. As a lifelong South Carolinian who will soon begin theological study as a Research Associate at Trinity College, University of Toronto, I represent the kind of nontraditional path to theological education that the Endowment's commitment to the region might support."),
    
    ("The Arthur Vining Davis Foundations (Religion)", "info@avdf.org",
     "The Arthur Vining Davis Foundations support interfaith and theological education. My Research Associate status at Trinity College provides the institutional anchor for my research on theological ethics and institutional accountability — work that spans Christian, Jewish, and secular frameworks of moral reasoning."),
    
    ("The H. E. Butt Foundation", "info@hebfdn.org",
     "The H. E. Butt Foundation funds Christian formation and leadership. As a Research Associate at Trinity College, University of Toronto, I am pursuing theological study that asks how Christian ethical traditions can inform institutional leadership in a complex and often morally ambiguous world."),
    
    ("The Trust for Theological Education", "contact@tte.org",
     "The Trust for Theological Education supports theological study and research. My Research Associate status at Trinity College satisfies the institutional requirement for consideration. I am a first-generation graduate student and former tax attorney pursuing research on the theology of risk management — how institutions navigate moral and legal accountability."),
]

FOOTER = """
If your organization considers funding from individual scholars or has a process for supporting research and study at the graduate level, I would be grateful for any guidance on eligibility, application procedures, or upcoming opportunities. I am happy to provide a project description, CV, or any additional materials.

Thank you for your time and for your organization's commitment to theological scholarship.

Warm regards,
Charles Prescott
JD, LLM in Taxation
Research Associate, Trinity College, University of Toronto
Columbia, South Carolina
charlesaprescottjr@gmail.com
843-504-4542"""


def authenticate():
    creds = None
    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE) as f:
            creds = Credentials.from_authorized_user_info(json.load(f), SCOPES)
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
    if not creds or not creds.valid:
        flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
        creds = flow.run_local_server(port=0, open_browser=True)
        with open(TOKEN_FILE, 'w') as f:
            json.dump(json.loads(creds.to_json()), f)
    return creds


def send_email(service, name, email, hook):
    subject = "Inquiry Regarding Theological Research Funding — Research Associate, Trinity College"
    body = f"Dear {name} Team,\n\n{hook}\n{FOOTER}"
    
    msg = EmailMessage()
    msg.set_content(body)
    msg['To'] = email
    msg['From'] = f"{SENDER_NAME} <{SENDER_EMAIL}>"
    msg['Subject'] = subject
    encoded = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    
    try:
        sent = service.users().messages().send(userId='me', body={'raw': encoded}).execute()
        with open(CURATED_LOG, 'a') as f:
            from datetime import datetime
            f.write(f"{name}|{email}|Theology Foundation|{datetime.now().isoformat()}|{sent.get('id','')}\n")
        print(f"  ✅ {name[:50]:50s} -> {email}")
        return True
    except HttpError as e:
        print(f"  ❌ {name} — {e}")
        return False


def main():
    print("=" * 60)
    print("Sending 15 New Theological Foundation Inquiries")
    print("=" * 60)
    
    # Check which have already been sent
    sent_emails = set()
    if os.path.exists(CURATED_LOG):
        with open(CURATED_LOG) as f:
            for line in f:
                parts = line.strip().split('|')
                if len(parts) >= 2:
                    sent_emails.add(parts[1].strip().lower())
    
    print(f"\nAuthentication...")
    creds = authenticate()
    service = build('gmail', 'v1', credentials=creds)
    print(f"✅ Authenticated\n")
    
    sent_count = 0
    skip_count = 0
    
    for name, email, hook in LEADS:
        email_lower = email.strip().lower()
        if email_lower in sent_emails:
            print(f"  ⏭️  {name[:50]:50s} — already sent")
            skip_count += 1
            continue
        
        send_email(service, name, email, hook)
        sent_count += 1
        time.sleep(5)  # Small delay between sends
    
    print(f"\n{'='*50}")
    print(f"Done! Sent: {sent_count}, Skipped (already sent): {skip_count}")
    print(f"Log: {CURATED_LOG}")


if __name__ == "__main__":
    main()
