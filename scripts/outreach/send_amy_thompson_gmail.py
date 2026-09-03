"""Send SBC pitch to Amy Thompson via Gmail API."""
import os, sys, base64, json
from email.message import EmailMessage

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

SENDER_NAME = "Charles Prescott"
SENDER_EMAIL = "charlesaprescottjr@gmail.com"
TOKEN_FILE = os.path.join(SCRIPT_DIR, "..", "..", "data", "gmail_token.json")
CREDENTIALS_FILE = os.path.join(SCRIPT_DIR, "..", "..", "data", "gmail_credentials.json")
SCOPES = ['https://www.googleapis.com/auth/gmail.modify']

TO = "athompson@sbc.net"
SUBJECT = "A data tool that could help SBC churches in high-poverty areas"

text_body = """Hi Amy,

I've been building a national church database (385K records) cross-referenced against ACS poverty and income data, and thought your team at the EC might find this useful. It's designed to help denominations identify where their churches are serving in the highest-need areas — not as a critique, but as a practical tool for targeting revitalization, planting, and grant resources effectively.

Here's a sample: 25 SBC churches in the highest-poverty ZIP codes in America — neighborhoods where the poverty rate exceeds 47% and median income is below $20,000:

 1. LAKE WASHINGTON FIRST BAPTIST CHURCH — Glen Allan, MS — 57.9% poverty, $19,194 med. income
 2. RAY OF HOPE MINISTRIES — Cleveland, OH — 57.4% poverty, $19,247
 3. KING'S CROSS CHURCH — Cleveland, OH — 57.4% poverty, $19,247
 4. GATEWAY CHURCH DOWNTOWN CLEVELAND — Cleveland, OH — 57.4% poverty, $19,247
 5. ORRVILLE — Orrville, AL — 57.3% poverty, $30,608
 6. IGLESIA BAUTISTA DEL CENTRO — El Paso, TX — 54.5% poverty, $14,142
 7. SAINT FRANCIS BAPTIST CHURCH — Saint Francis, AR — 54.5% poverty, $43,750
 8. LA PRIMERA IGLESIA BAUTISTA — Toledo, OH — 54.2% poverty, $16,651
 9. FIRST BAPTIST CHURCH OF MAGDALENA — Magdalena, NM — 53.9% poverty, $26,920
10. TURTLETOWN MISSIONARY BAPTIST CHURCH — Farner, TN — 53.3% poverty, $30,029
11. NEW ZION BAPTIST CHURCH — Farner, TN — 53.3% poverty, $30,029
12. ROSE HILL BAPTIST CHURCH — Gunnsion, MS — 52.4% poverty, $23,000
13. SECOND MISSIONARY BAPTIST CHURCH — Waco, TX — 52.2% poverty, $19,966
14. LAPLANT BAPTIST CHURCH — La Plant, SD — 51.8% poverty, $26,750
15. COTTON PLANT FIRST BAPTIST CHURCH — Cotton Plant, AR — 51.5% poverty, $17,063
16. LIVINGSTON BAPTIST CHURCH — Livingston, KY — 50.9% poverty, $23,621
17. PRIMERA IGLESIA GARCIASVILLE — Garciasville, TX — 50.6% poverty, $11,125
18. HOUSE OF HOPE MINISTRIES — Cleveland, OH — 50.6% poverty, $21,333
19. JESUS WAY BAPTIST CHURCH — Houston, TX — 50.4% poverty, $30,750
20. FIRST BAPTIST CHURCH OF MONROE — Monroe, OK — 50.4% poverty, $33,750
21. CHRIST'S COMMUNITY CHURCH — Memphis, TN — 50.3% poverty, $19,844
22. IGLESIA BAUTISTA LA HERMOSA — Presidio, TX — 50.2% poverty, $19,650
23. IDEAL BAPTIST CHURCH, INC. — Ideal, GA — 50.2% poverty, $24,539
24. WATERBURY BAPTIST MINISTRIES — Waterbury, CT — 48.3% poverty, $14,852
25. FIRST BAPTIST CHURCH ROSEDALE — Rosedale, MS — 47.8% poverty, $18,542

And here are the 25 SBC churches in South Carolina serving in the highest-poverty ZIPs:

 1. MAITIAN CHINESE BAPTIST CHURCH — Columbia — 39.8% poverty, $33,561
 2. PALMETTO LIFE CHURCH — Columbia — 39.8% poverty, $33,561
 3. BEAR SWAMP — Lake View — 36.5% poverty, $37,727
 4. VILLAGE CHURCH OF PENDLETON — Clemson — 36.3% poverty, $50,348
 5. ID CHURCH DOWNTOWN — Spartanburg — 33.3% poverty, $35,439
 6. SPARTANBURG FIRST BAPTIST CHURCH — Spartanburg — 33.3% poverty, $35,439
 7. GOVAN FIRST BAPTIST CHURCH — Olar — 31.6% poverty, $50,170
 8. CITY OF REFUGE CHURCH — Columbia — 28.8% poverty, $39,015
 9. GREATER FAITH UNITED BAPTIST CHURCH — Columbia — 28.8% poverty, $39,015
10. BERMUDA BAPTIST CHURCH — Dillon — 28.7% poverty, $42,835
11. ALLIANCE BAPTIST MISSION — Johnsonville — 27.9% poverty, $57,660
12. NORTHWOOD BAPTIST EAST BAY — Charleston — 27.0% poverty, $62,281
13. READY CHURCH — N Charleston — 25.7% poverty, $45,797
14. COMUNIDADE BATISTA DE CHARLESTON — N Charleston — 25.7% poverty, $45,797
15. BROCK'S MILL BAPTIST CHURCH — Cheraw — 24.9% poverty, $40,724
16. MOUNT ZION, HAMER — Hamer — 23.6% poverty, $44,413
17. FIRE ON THE MOUNTAIN CHURCH — Greenville — 23.4% poverty, $45,291
18. CHRIST THE REDEEMER — Greenville — 23.4% poverty, $45,291
19. HILLCREST CHURCH — Gaston — 22.6% poverty, $50,534
20. PINE PLEASANT BAPTIST CHURCH — Saluda — 22.5% poverty, $39,607
21. GREELEYVILLE BAPTIST CHURCH — Greeleyville — 21.9% poverty, $42,197
22. LOVE SPRINGS BAPTIST CHURCH — Cowpens — 21.9% poverty, $53,762
23. DRAYTONVILLE BAPTIST CHURCH — Gaffney — 21.9% poverty, $40,242
24. EAST GAFFNEY BAPTIST CHURCH — Gaffney — 21.9% poverty, $40,242
25. ELKO BAPTIST CHURCH — Williston — 21.6% poverty, $43,934

Altogether, 4,940 SBC directory churches (21% of the total) are in ZIPs where poverty exceeds 20% — these are churches already on the front lines in hard places, and the data can help tell that story and target support.

Currently this is ZIP-level analysis because the SBC directory doesn't include street addresses (which is totally normal for a directory). If addresses were available, I could drill down to the census tract level — neighborhood-sized — which captures the kind of micro-targeting that makes grant applications and strategic plans really compelling.

This is a service I'm offering — no obligation, no pitch beyond this email. If it's useful, I'd be glad to run specific queries for your team. If not, no hard feelings at all.

Best,
Charles Prescott"""


def get_gmail_service():
    creds = None
    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            from google_auth_oauthlib.flow import InstalledAppFlow
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(TOKEN_FILE, 'w') as token:
            token.write(creds.to_json())
    return build('gmail', 'v1', credentials=creds)


def main():
    service = get_gmail_service()

    msg = EmailMessage()
    msg.set_content(text_body)
    msg['To'] = TO
    msg['From'] = SENDER_EMAIL
    msg['Subject'] = SUBJECT

    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    response = service.users().messages().send(
        userId='me',
        body={'raw': raw}
    ).execute()

    print(f"Sent! Message ID: {response.get('id')}")
    print(f"From: {SENDER_EMAIL}")
    print(f"To: {TO}")
    print(f"Subject: {SUBJECT}")


if __name__ == '__main__':
    main()
