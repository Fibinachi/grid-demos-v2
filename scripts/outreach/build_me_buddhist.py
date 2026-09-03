"""
MIDDLE EAST GOVERNMENT + BUDDHIST outreach leads.
For the 361K global Muslim dataset — governments manage thousands of mosques.
"""
import json
from pathlib import Path
OUT = Path("outputs/outreach")

LEADS = [
    # ═══ SAUDI ARABIA ═══
    {"org": "Saudi Ministry of Islamic Affairs (MOIA)", "email": "info@mou.gov.sa", "faith": "Islam", "sector": "Government"},
    {"org": "Saudi Ministry of Hajj and Umrah", "email": "info@haj.gov.sa", "faith": "Islam", "sector": "Government"},
    {"org": "Saudi General Presidency of Haramain", "email": "info@gph.gov.sa", "faith": "Islam", "sector": "Government"},
    {"org": "King Faisal Center for Research & Islamic Studies", "email": "info@kfcris.com", "faith": "Islam", "sector": "Research"},
    {"org": "Islamic University of Madinah", "email": "info@iu.edu.sa", "faith": "Islam", "sector": "Academic"},
    {"org": "Umm al-Qura University", "email": "info@uqu.edu.sa", "faith": "Islam", "sector": "Academic"},

    # ═══ UAE ═══
    {"org": "UAE General Authority of Islamic Affairs", "email": "info@awqaf.gov.ae", "faith": "Islam", "sector": "Government"},
    {"org": "UAE Ministry of Tolerance & Coexistence", "email": "info@tolerance.gov.ae", "faith": "Islam", "sector": "Government"},
    {"org": "Mohammed bin Rashid Al Maktoum Foundation", "email": "info@mbrfoundation.ae", "faith": "Islam", "sector": "Foundation"},
    {"org": "Abu Dhabi Islamic Authority", "email": "info@adkia.gov.ae", "faith": "Islam", "sector": "Government"},

    # ═══ QATAR ═══
    {"org": "Qatar Ministry of Awqaf & Islamic Affairs", "email": "info@islam.gov.qa", "faith": "Islam", "sector": "Government"},
    {"org": "Qatar International Center for Interfaith Dialogue", "email": "info@dohacentre.com", "faith": "Islam", "sector": "Nonprofit"},
    {"org": "Hamad Bin Khalifa University - Islamic Studies", "email": "info@hbku.edu.qa", "faith": "Islam", "sector": "Academic"},

    # ═══ KUWAIT ═══
    {"org": "Kuwait Ministry of Awqaf & Islamic Affairs", "email": "info@awqaf.gov.kw", "faith": "Islam", "sector": "Government"},
    {"org": "International Islamic Charitable Organization", "email": "info@iico.org.kw", "faith": "Islam", "sector": "Nonprofit"},

    # ═══ EGYPT ═══
    {"org": "Egypt Ministry of Awqaf (Religious Endowments)", "email": "info@awkaf.org.eg", "faith": "Islam", "sector": "Government"},
    {"org": "Al-Azhar University", "email": "info@azhar.edu.eg", "faith": "Islam", "sector": "Academic"},
    {"org": "Dar al-Ifta al-Misriyyah (Egyptian Fatwa House)", "email": "info@dar-alifta.org", "faith": "Islam", "sector": "Religious"},

    # ═══ TURKEY ═══
    {"org": "Diyanet (Presidency of Religious Affairs, Turkiye)", "email": "info@diyanet.gov.tr", "faith": "Islam", "sector": "Government"},
    {"org": "Turkiye Diyanet Foundation", "email": "info@tdv.org", "faith": "Islam", "sector": "Nonprofit"},
    {"org": "Istanbul University - Theology", "email": "info@istanbul.edu.tr", "faith": "Islam", "sector": "Academic"},

    # ═══ JORDAN ═══
    {"org": "Jordan Ministry of Awqaf & Islamic Affairs", "email": "info@awqaf.gov.jo", "faith": "Islam", "sector": "Government"},
    {"org": "Royal Aal al-Bayt Institute", "email": "info@aalalbayt.org", "faith": "Islam", "sector": "Research"},
    {"org": "Prince Alwaleed bin Talal Center for Muslim-Christian Understanding", "email": "info@acmcu.georgetown.edu", "faith": "Islam", "sector": "Academic"},

    # ═══ OMAN ═══
    {"org": "Oman Ministry of Awqaf & Religious Affairs", "email": "info@mara.gov.om", "faith": "Islam", "sector": "Government"},

    # ═══ MOROCCO ═══
    {"org": "Morocco Ministry of Habous & Islamic Affairs", "email": "info@habous.gov.ma", "faith": "Islam", "sector": "Government"},
    {"org": "Mohammed VI Institute for Imam Training", "email": "info@imaminstitute.ma", "faith": "Islam", "sector": "Academic"},

    # ═══ BUDDHIST (Japan/Asia governments) ═══
    {"org": "Japan Agency for Cultural Affairs (Buddhist temples)", "email": "info@bunka.go.jp", "faith": "Buddhist", "sector": "Government"},
    {"org": "Thai Ministry of Religious Affairs", "email": "info@mora.go.th", "faith": "Buddhist", "sector": "Government"},
    {"org": "Myanmar Ministry of Religious Affairs", "email": "info@mora.gov.mm", "faith": "Buddhist", "sector": "Government"},
    {"org": "Sri Lanka Ministry of Buddhasasana", "email": "info@buddhasasana.gov.lk", "faith": "Buddhist", "sector": "Government"},
    {"org": "Bhutan Ministry of Interior & Cultural Affairs", "email": "info@mohca.gov.bt", "faith": "Buddhist", "sector": "Government"},
    {"org": "Mongolia Ministry of Culture (Buddhist monasteries)", "email": "info@mcc.gov.mn", "faith": "Buddhist", "sector": "Government"},

    # ═══ ADDITIONAL BUDDHIST ORGS (not in earlier list) ═══
    {"org": "World Fellowship of Buddhists", "email": "info@wfb-hq.org", "faith": "Buddhist", "sector": "Umbrella"},
    {"org": "International Buddhist Confederation", "email": "info@ibcworld.org", "faith": "Buddhist", "sector": "Umbrella"},
    {"org": "Buddhist Association of China", "email": "info@buddhism.org.cn", "faith": "Buddhist", "sector": "Umbrella"},
    {"org": "Jodo Shinshu Hongwanji-ha", "email": "info@hongwanji.or.jp", "faith": "Buddhist", "sector": "Umbrella"},
]

# Merge with existing Buddhist leads
existing = json.load(open(OUT/"buddhist_sikh_bahai_leads.json"))
all_emails = {l['email'] for l in existing}
new = [l for l in LEADS if l['email'] not in all_emails]
combined = existing + new

json.dump(combined, open(OUT/"buddhist_sikh_bahai_leads.json","w"), indent=2)
print(f"Existing Buddhist/Sikh/Bahai: {len(existing)}")
print(f"New ME gov + Buddhist: {len(new)}")
print(f"Combined: {len(combined)}")

from collections import Counter
for faith, count in Counter(l['faith'] for l in combined).most_common():
    print(f"  {faith}: {count}")
for sector, count in Counter(l['sector'] for l in combined).most_common():
    print(f"  {sector}: {count}")
