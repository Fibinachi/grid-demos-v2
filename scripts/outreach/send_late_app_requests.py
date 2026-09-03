"""
Send late-application inquiries to closed scholarship programs.
Explains the PhD -> CTS deferral and asks about discretionary consideration.
"""
import os
import sys
import base64
import json
import time
from email.message import EmailMessage

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

SENDER_NAME = "Charles Prescott"
SENDER_EMAIL = "charlesaprescottjr@gmail.com"
GMAIL_USER = "me"
CREDENTIALS_FILE = os.path.join(SCRIPT_DIR, "gmail_credentials.json")
TOKEN_FILE = os.path.join(SCRIPT_DIR, "gmail_token.json")
SCOPES = ['https://www.googleapis.com/auth/gmail.modify']


def authenticate():
    creds = None
    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE, 'r') as f:
            creds = Credentials.from_authorized_user_info(json.load(f), SCOPES)
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
    if not creds or not creds.valid:
        flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
        creds = flow.run_local_server(port=0, open_browser=True)
        with open(TOKEN_FILE, 'w') as f:
            json.dump(json.loads(creds.to_json()), f)
    return creds


def send_email(service, to_email, subject, body):
    msg = EmailMessage()
    msg.set_content(body)
    msg['To'] = to_email
    msg['From'] = f"{SENDER_NAME} <{SENDER_EMAIL}>"
    msg['Subject'] = subject
    encoded = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    try:
        sent = service.users().messages().send(userId=GMAIL_USER, body={'raw': encoded}).execute()
        print(f"  ✓ Sent to {to_email} (id: {sent.get('id', '')})")
        return True
    except HttpError as e:
        print(f"  ✗ Failed to send to {to_email}: {e}")
        return False


# ── Email 1: Davis-Putter Scholarship Fund ───────────────────────────────

DAVIS_PUTTER_EMAIL = "davisputter@davisputter.org"
DAVIS_PUTTER_SUBJECT = "Inquiry Regarding Late Application — PhD Deferral to CTS Program"

DAVIS_PUTTER_BODY = """Dear Davis-Putter Scholarship Fund Team,

I am writing to inquire whether there is any possibility of submitting a late application for the 2026-27 award cycle.

My situation is somewhat unusual. I was originally admitted to a PhD program, but was subsequently deferred to the Certificate in Theological Studies program at Trinity College, University of Toronto — an institution founded in the Anglican tradition with a strong commitment to social justice. This deferral happened after your April 1 deadline, which is why I did not apply during the regular cycle.

I believe my background and trajectory may align with the Davis-Putter mission. I am a 44-year-old first-generation student who spent 15 years as a tax attorney — forming churches as an attorney, serving as Founding Director of the Midlands Light Opera Society, working with cancer charities, and providing pro bono legal representation for domestic violence survivors — before leaving legal practice to pursue theological education. My research focuses on theology of risk management: how institutions can be held morally accountable through the integration of game theory, ethics, and theological reflection.

Like many Davis-Putter grantees, my work has consistently been in service of progressive change — though my arena has been institutional reform and community organizing through legal and artistic channels, rather than traditional activism. I am now seeking to understand how theological ethics can inform the structural changes needed for genuine justice.

I recognize that your application deadline has passed, and I respect the integrity of your selection process. However, given that my change in academic status occurred after the deadline and was beyond my control, I wanted to ask whether there is any mechanism for discretionary or late consideration — whether a formal late application, a waiting list, or simply an opportunity to be considered should any funds remain unallocated.

I would be happy to provide a complete application packet, letters of recommendation, transcripts, and any other materials you might need within 48 hours.

Thank you for your consideration and for the vital work you do in supporting student activists.

Warm regards,
Charles Prescott
Columbia, SC
charlesaprescottjr@gmail.com
843-504-4542"""


# ── Email 2: American Legion Auxiliary Non-Traditional Student Scholarship ──

ALA_EMAIL = "alahq@alaforveterans.org"
ALA_SUBJECT = "Inquiry Regarding Non-Traditional Student Scholarship — Late Consideration"

ALA_BODY = """Dear American Legion Auxiliary Scholarship Committee,

I am writing to inquire whether there is any possibility of submitting a late application for the Non-Traditional Student Scholarship for the 2026 award year.

My educational path took an unexpected turn recently. I was originally admitted to a PhD program, but was subsequently deferred to the Certificate in Theological Studies program at Trinity College, University of Toronto, beginning Fall 2026. This change occurred after your March 1 deadline, which is why I was unable to apply during the regular cycle.

I am a 44-year-old non-traditional student — the first in my family to pursue graduate education. After 15 years practicing as a tax attorney (JD, Rutgers Law; LLM in Taxation, University of Alabama), I left legal practice to pursue theological education. I am the father of three children (two on the autism spectrum) and the son of a 100% disabled US Army veteran. My father's service and sacrifice have shaped my understanding of duty, community, and the importance of supporting those who serve.

As a non-traditional student returning to the classroom after a long career in law, I believe my circumstances align well with the purpose of this scholarship. I am pursuing theological studies to explore how institutions — legal, religious, and charitable — can be held morally accountable, work that I hope will serve both the church and the broader community.

I understand that your application window closed on March 1 and that this scholarship has significant demand. However, given that my change in academic plans was beyond my control and occurred after the deadline, I wanted to ask whether there is any avenue for late submission, a waiting list, or discretionary consideration should any funds remain unallocated after the primary awards are made.

I would be grateful for any guidance you can offer, and I am prepared to submit a complete application immediately if that is a possibility.

Thank you for your time and for the important work the Auxiliary does in supporting veterans' families and non-traditional students.

Respectfully,
Charles Prescott
Columbia, SC
charlesaprescottjr@gmail.com
843-504-4542"""


def main():
    print("=" * 60)
    print("Late Application Requests")
    print("=" * 60)

    print("\nAuthenticating with Gmail API...")
    creds = authenticate()
    service = build('gmail', 'v1', credentials=creds)
    print("  Authenticated.\n")

    # Send to Davis-Putter
    print(f"[1/2] Davis-Putter Scholarship Fund")
    print(f"      To: {DAVIS_PUTTER_EMAIL}")
    send_email(service, DAVIS_PUTTER_EMAIL, DAVIS_PUTTER_SUBJECT, DAVIS_PUTTER_BODY)
    time.sleep(5)

    # Send to ALA
    print(f"\n[2/2] American Legion Auxiliary Non-Traditional Student Scholarship")
    print(f"      To: {ALA_EMAIL}")
    send_email(service, ALA_EMAIL, ALA_SUBJECT, ALA_BODY)

    print("\n" + "=" * 60)
    print("Both emails sent. Check Gmail for replies.")
    print("=" * 60)


if __name__ == "__main__":
    main()
