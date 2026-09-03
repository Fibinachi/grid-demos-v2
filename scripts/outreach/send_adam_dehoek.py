"""Send the ELCA pitch to Adam DeHoek via Gmail API."""
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

TO = "adam.dehoek@elca.org"
SUBJECT = "25 ELCA churches in food deserts — data-driven opportunity"

BODY = """Hi Adam,

I've been building a national church database (385K records across every denomination) and cross-referencing it against USDA food access data and ACS poverty data. I wanted to share something I found that might prove the capability.

Here are 25 ELCA churches sitting in high-need food deserts where our web scraping found no food pantry reference — a data gap that's worth investigating:

```
 #  Church                                   City, State        Poverty  Income      No Car
--- ---------------------------------------- ------------------ -------- ----------- ------
 1  HOPE LUTHERAN CHURCH                     Bangor, ME          47.2%   $30,839     YES
 2  ST PAUL LUTHERAN CHURCH                  Berlin, NH          30.1%   $45,278     YES
 3  ST LUKES EVANGELICAL LUTHERAN CHURCH     Amsterdam, NY       39.6%   $35,000     YES
 4  CHRIST THE KING LUTHERAN CHURCH          Vestal, NY          31.5%   $88,581     YES
 5  NORTH AMERICAN LUTHERAN CHURCH           Atlantic City, NJ   32.7%   $32,734     YES
 6  TRINITY EVANGELICAL LUTHERAN CHURCH      Springfield, MA     22.0%   $61,250     YES
 7  SAINT PETERS LUTHERAN CHURCH             Holyoke, MA         22.3%   $68,125     YES
 8  SAINT MARKS LUTHERAN CHURCH              Hudson, NY          19.4%   $41,638     YES
 9  MESSIAH EVANGELICAL LUTHERAN CHURCH      Rochester, NY       14.2%   $63,088     YES
10  GUSTAV ADOLPH LUTHERAN CHURCH            New Sweden, ME      18.7%   $49,417     no
11  TRINITY EVANGELICAL LUTHERAN CHURCH      Stockholm, ME       18.7%   $49,417     no
12  TRINITY LUTHERAN CHURCH                  Brattleboro, VT     11.9%   $59,063     YES
13  ST STEPHEN LUTHERAN CHURCH               Brooklyn, NY        31.8%   $48,039     YES
14  CHRIST ASSEMBLY LUTHERAN CHURCH          Staten Island, NY   27.9%   $69,688     YES
15  OUR SAVIOUR LUTHERAN CHURCH              Staten Island, NY   27.9%   $69,688     YES
16  NAZARETH LUTHERAN CHURCH                 Buffalo, NY         42.3%   $29,955     YES
17  HANAHIAH LUTHERAN CHURCH                 Buffalo, NY         31.7%   $38,906     YES
18  ST STEPHEN LUTHERAN CHURCH               Woodbury, NJ        30.1%   $38,906     YES
19  SAINT PAUL LUTHERAN CHURCH               Raritan, NJ          8.5%   $66,858     YES
20  ST PAUL EVANGELICAL LUTHERAN CHURCH      East Windsor, NJ    10.7%   $77,625     YES
21  OUR SAVIOR CHURCH LUTHERAN               Niagara Falls, NY   13.8%   $51,123     no
22  ST JOHNS LUTHERAN CHURCH                 Fort Plain, NY      21.2%   $51,500     YES
23  GOOD SHEPHERD LUTHERAN CHURCH            Laconia, NH         15.3%   $64,485     no
24  EMANUEL EVANGELICAL LUTHERAN CHURCH      Worcester, MA       13.5%   $70,268     YES
25  EVANGELICAL LUTHERAN CHURCH              Brockton, MA        12.1%   $75,833     YES
```

All 25 are in USDA-identified low-income, low-access food desert tracts. 84% lack vehicle access. None had a food pantry detected in our web scraping — whether that means they don't have one, or just don't advertise it online, is the kind of question the data surfaces.

The full database can do this for any denomination, any geography, any combination of data layers — food access, poverty, demographics, ARDA religious adherence, FCC broadcast coverage, election data, school locations, you name it.

This is tract-level data, not county-level smoothing. Each church's neighborhood is analyzed individually.

Happy to show you more or run a specific query for your team.

Best,
Charles Prescott
"""

def get_service():
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
        with open(TOKEN_FILE, 'w') as f:
            f.write(creds.to_json())
    return build('gmail', 'v1', credentials=creds)

def send():
    service = get_service()
    msg = EmailMessage()
    msg.set_content(BODY)
    msg['To'] = TO
    msg['From'] = SENDER_EMAIL
    msg['Subject'] = SUBJECT
    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    service.users().messages().send(userId='me', body={'raw': raw}).execute()
    print(f"Sent to {TO}")

if __name__ == '__main__':
    send()
