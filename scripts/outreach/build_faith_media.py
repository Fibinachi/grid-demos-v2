"""Build faith-based media outreach leads — film studios, streaming, TV, publishing."""
import json
from pathlib import Path
OUT = Path("outputs/outreach")

LEADS = [
    # ═══ FILM STUDIOS ═══
    {"org": "Pure Flix / Pinnacle Peak Pictures", "email": "info@pureflix.com", "sector": "Film Studio", "sub": "Christian film production & streaming"},
    {"org": "Angel Studios", "email": "press@angel.com", "sector": "Film Studio", "sub": "The Chosen, streaming platform"},
    {"org": "Kingdom Story Company", "email": "info@kingdomstorycompany.com", "sector": "Film Studio", "sub": "Jesus Revolution, I Can Only Imagine"},
    {"org": "Sony Affirm Films", "email": "info@affirmfilms.com", "sector": "Film Studio", "sub": "Christian film distribution"},
    {"org": "Provident Films", "email": "info@providentfilms.com", "sector": "Film Studio", "sub": "Christian film distribution (Sony)"},
    {"org": "Milk & Honey Pictures", "email": "info@milkandhoneypics.com", "sector": "Film Studio", "sub": "Faith-based film production"},
    {"org": "Visible Pictures", "email": "info@visiblepictures.com", "sector": "Film Studio", "sub": "Faith film distribution"},

    # ═══ STREAMING ═══
    {"org": "RightNow Media", "email": "support@rightnowmedia.com", "sector": "Streaming", "sub": "Church video curriculum (60K+ churches)"},
    {"org": "Minno", "email": "hello@minno.com", "sector": "Streaming", "sub": "Christian kids streaming"},
    {"org": "Pray.com", "email": "info@pray.com", "sector": "Streaming", "sub": "Prayer app & content platform"},
    {"org": "Master's Voice (BibleProject)", "email": "info@bibleproject.com", "sector": "Streaming", "sub": "BibleProject content distribution"},
    {"org": "Faithlife / Logos Bible Software", "email": "sales@faithlife.com", "sector": "Publishing", "sub": "Biblical research platform, 1M+ users"},
    {"org": "Dwell (Scripture Audio)", "email": "hello@dwellapp.io", "sector": "Streaming", "sub": "Bible audio app"},
    {"org": "Glorify", "email": "hello@glorify-app.com", "sector": "Streaming", "sub": "Christian devotional app"},
    {"org": "Cross.tv", "email": "info@cross.tv", "sector": "Streaming", "sub": "Christian social media & streaming"},

    # ═══ TV / BROADCAST NETWORKS ═══
    {"org": "Trinity Broadcasting Network (TBN)", "email": "comments@tbn.org", "sector": "TV Network", "sub": "Largest Christian TV network"},
    {"org": "Christian Broadcasting Network (CBN)", "email": "info@cbn.org", "sector": "TV Network", "sub": "The 700 Club"},
    {"org": "Daystar Television Network", "email": "feedback@daystar.com", "sector": "TV Network", "sub": "Christian TV network"},
    {"org": "EWTN (Eternal Word Television Network)", "email": "viewer@ewtn.com", "sector": "TV Network", "sub": "Catholic TV network"},
    {"org": "BYUtv", "email": "info@byutv.org", "sector": "TV Network", "sub": "LDS television network"},
    {"org": "3ABN (Three Angels Broadcasting Network)", "email": "info@3abn.org", "sector": "TV Network", "sub": "Adventist TV network"},
    {"org": "Hope Channel", "email": "info@hopetv.org", "sector": "TV Network", "sub": "Adventist international TV"},
    {"org": "NRB (National Religious Broadcasters)", "email": "info@nrb.org", "sector": "Association", "sub": "1,000+ member broadcasters"},
    {"org": "Salem Media Group", "email": "info@salemmedia.com", "sector": "Radio", "sub": "Largest Christian radio group (100+ stations)"},
    {"org": "Bott Radio Network", "email": "info@bottradionetwork.com", "sector": "Radio", "sub": "80+ Christian radio stations"},

    # ═══ PUBLISHING ═══
    {"org": "HarperCollins Christian Publishing", "email": "info@harpercollinschristian.com", "sector": "Publishing", "sub": "Thomas Nelson, Zondervan"},
    {"org": "David C. Cook", "email": "info@davidccook.org", "sector": "Publishing", "sub": "Curriculum & books"},
    {"org": "Lifeway Christian Resources", "email": "customerservice@lifeway.com", "sector": "Publishing", "sub": "SBC curriculum, books, events"},
    {"org": "Group Publishing", "email": "info@group.com", "sector": "Publishing", "sub": "Church curriculum & VBS"},
    {"org": "Gospel Light / Regal Books", "email": "info@gospellight.com", "sector": "Publishing", "sub": "Church curriculum"},
    {"org": "Our Daily Bread Ministries", "email": "info@odb.org", "sector": "Publishing", "sub": "Devotional publishing"},
    {"org": "Broadman & Holman (B&H Publishing)", "email": "info@bhpublishing.com", "sector": "Publishing", "sub": "SBC academic publisher"},
    {"org": "InterVarsity Press", "email": "info@ivpress.com", "sector": "Publishing", "sub": "Academic Christian publishing"},
    {"org": "Baker Publishing Group", "email": "info@bakerpublishinggroup.com", "sector": "Publishing", "sub": "Christian trade publisher"},
    {"org": "Eerdmans Publishing", "email": "info@eerdmans.com", "sector": "Publishing", "sub": "Academic theology publishing"},
    {"org": "Fortress Press", "email": "info@fortresspress.com", "sector": "Publishing", "sub": "Academic religion publishing"},
    {"org": "Westminster John Knox Press", "email": "info@wjkbooks.com", "sector": "Publishing", "sub": "Mainline Protestant publisher"},
    {"org": "Augsburg Fortress", "email": "info@augsburgfortress.org", "sector": "Publishing", "sub": "ELCA publishing house"},
    {"org": "Concordia Publishing House", "email": "info@cph.org", "sector": "Publishing", "sub": "LCMS publishing house"},

    # ═══ CURRICULUM / CHURCH GROWTH ═══
    {"org": "Ministry Pass", "email": "support@ministrypass.com", "sector": "Curriculum", "sub": "Video curriculum for churches"},
    {"org": "Church of the Highlands — Grow + Vision15", "email": "info@churchofthehighlands.com", "sector": "Curriculum", "sub": "Church growth resources"},
    {"org": "Orange (The reThink Group)", "email": "info@thinkorange.com", "sector": "Curriculum", "sub": "Youth & family ministry curriculum"},
    {"org": "Awana", "email": "info@awana.org", "sector": "Curriculum", "sub": "Children's ministry (40K+ churches)"},
    {"org": "Gospel for Asia (GFA World)", "email": "info@gfa.org", "sector": "Curriculum", "sub": "Mission resource distribution"},
]

import sqlite3
db = sqlite3.connect('churches.db')
db.row_factory = sqlite3.Row

# Stats for pitch
us_churches = db.execute("SELECT COUNT(*) as n FROM churches WHERE country='US'").fetchone()['n']
traditions = db.execute("SELECT COUNT(DISTINCT tradition) as n FROM churches WHERE tradition IS NOT NULL").fetchone()['n']
faiths = db.execute("SELECT COUNT(DISTINCT faith) as n FROM churches WHERE faith IS NOT NULL").fetchone()['n']
with_contact = db.execute("SELECT COUNT(DISTINCT c.id) as n FROM churches c JOIN church_contact_values cv ON c.id=cv.church_id WHERE c.country='US'").fetchone()['n']
with_phone = db.execute("SELECT COUNT(DISTINCT cv.church_id) as n FROM church_contact_values cv JOIN churches c ON c.id=cv.church_id WHERE c.country='US' AND cv.contact_type='phone'").fetchone()['n']
with_email = db.execute("SELECT COUNT(DISTINCT cv.church_id) as n FROM church_contact_values cv JOIN churches c ON c.id=cv.church_id WHERE c.country='US' AND cv.contact_type='email'").fetchone()['n']
traditions = db.execute("SELECT COUNT(DISTINCT tradition) as n FROM churches WHERE tradition IS NOT NULL").fetchone()['n']
db.close()

print(f"US churches: {us_churches:,}, {faiths} faiths, {traditions} traditions")
print(f"With contact info: {with_contact:,} (phone {with_phone:,}, email {with_email:,})")

json.dump(LEADS, open(OUT/"faith_media_leads.json","w"), indent=2)
from collections import Counter
for sector, count in Counter(l['sector'] for l in LEADS).most_common():
    print(f"  {sector}: {count}")
print(f"Total: {len(LEADS)}")
