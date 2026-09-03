"""Build faith-based hunger / food bank outreach leads."""
import json
from pathlib import Path
OUT = Path("outputs/outreach")

LEADS = [
    # ═══ NATIONAL NETWORKS ═══
    {"org": "Feeding America (National HQ)", "email": "info@feedingamerica.org", "sector": "Food Bank Network", "sub": "200 food banks, 60K+ church pantries"},
    {"org": "Meals on Wheels America", "email": "info@mealsonwheelsamerica.org", "sector": "Senior Meals", "sub": "5K+ local programs, mostly church-hosted"},
    {"org": "No Kid Hungry / Share Our Strength", "email": "info@strength.org", "sector": "Child Hunger", "sub": "National child hunger program"},
    {"org": "MAZON: A Jewish Response to Hunger", "email": "info@mazon.org", "sector": "Advocacy", "sub": "Jewish anti-hunger advocacy"},
    {"org": "Bread for the World", "email": "info@bread.org", "sector": "Advocacy", "sub": "Christian anti-hunger advocacy"},
    {"org": "Food Research & Action Center (FRAC)", "email": "info@frac.org", "sector": "Research", "sub": "Hunger policy research"},
    {"org": "USDA Food and Nutrition Service (partnerships)", "email": "usda@fns.usda.gov", "sector": "Government", "sub": "SNAP, school meals partnerships"},

    # ═══ FAITH-BASED HUNGER ORGS ═══
    {"org": "Catholic Charities USA", "email": "info@catholiccharitiesusa.org", "sector": "Catholic", "sub": "1,700+ local agencies, largest US social service"},
    {"org": "St. Vincent de Paul (National Council)", "email": "info@svdpusa.org", "sector": "Catholic", "sub": "4,400+ parish-based conferences"},
    {"org": "Society of St. Andrew", "email": "info@endhunger.org", "sector": "Christian", "sub": "Food rescue, gleaning network"},
    {"org": "Anglican Relief & Development", "email": "info@anglicanrelief.org", "sector": "Anglican", "sub": "Global hunger relief"},
    {"org": "Presbyterian Hunger Program", "email": "hunger@pcusa.org", "sector": "Mainline", "sub": "PCUSA hunger program"},
    {"org": "ELCA World Hunger", "email": "info@elca.org", "sector": "Lutheran", "sub": "ELCA hunger program"},
    {"org": "UMCOR (United Methodist Committee on Relief)", "email": "umcor@umcor.org", "sector": "Methodist", "sub": "UMC relief & hunger"},
    {"org": "LDS Welfare Services (Bishop's Storehouses)", "email": "welfare@churchofjesuschrist.org", "sector": "LDS", "sub": "LDS Bishop's Storehouses network"},
    {"org": "Islamic Relief USA", "email": "info@irusa.org", "sector": "Muslim", "sub": "US hunger relief"},
    {"org": "American Friends Service Committee", "email": "info@afsc.org", "sector": "Quaker", "sub": "Quaker social service"},
    {"org": "Baptist Global Response", "email": "info@gobgr.org", "sector": "Baptist", "sub": "SBC disaster hunger response"},
    {"org": "Cooperative Baptist Fellowship - Global Missions", "email": "info@cbf.net", "sector": "Baptist", "sub": "CBF hunger response"},
    {"org": "Church World Service", "email": "info@cwsglobal.org", "sector": "Ecumenical", "sub": "Ecumenical hunger relief, 37 denominations"},

    # ═══ CHURCH PARTNERSHIP ORGS ═══
    {"org": "Convoy of Hope", "email": "info@convoyofhope.org", "sector": "Disaster Food", "sub": "65K+ church partnerships"},
    {"org": "Operation Blessing", "email": "info@ob.org", "sector": "Disaster Food", "sub": "CBN's hunger/disaster arm"},
    {"org": "Food for the Poor", "email": "info@foodforthepoor.org", "sector": "International", "sub": "Christian hunger org, 50+ countries"},
    {"org": "World Vision US Programs", "email": "info@worldvision.org", "sector": "Child Feeding", "sub": "50K+ church partnerships"},
    {"org": "Hope for Hunger", "email": "info@hopeforhunger.org", "sector": "Food Rescue", "sub": "Church food rescue network"},
    {"org": "Kids Against Hunger", "email": "info@kidsagainsthunger.org", "sector": "Meal Packing", "sub": "Church-based meal packing"},
    {"org": "Feed My Starving Children", "email": "info@fmsc.org", "sector": "Meal Packing", "sub": "Church-based meal packing, 350K+ volunteers/yr"},
    {"org": "Rise Against Hunger", "email": "info@riseagainsthunger.org", "sector": "Meal Packing", "sub": "Formerly Stop Hunger Now"},
    {"org": "Blessings of Hope", "email": "info@blessingsofhope.org", "sector": "Food Rescue", "sub": "Food rescue to 750+ churches"},
    {"org": "OneDay Church Project", "email": "info@onedaychurchproject.com", "sector": "Church Network", "sub": "Church hunger mobilization"},

    # ═══ REGIONAL FOOD BANKS (top 20 by reach) ═══
    {"org": "Greater Chicago Food Depository", "email": "info@gcfd.org", "sector": "Regional Food Bank", "sub": "700+ church pantries"},
    {"org": "Houston Food Bank", "email": "info@houstonfoodbank.org", "sector": "Regional Food Bank", "sub": "1,500+ partners"},
    {"org": "Los Angeles Regional Food Bank", "email": "info@lafoodbank.org", "sector": "Regional Food Bank", "sub": "600+ partners"},
    {"org": "North Texas Food Bank (Dallas)", "email": "info@ntfb.org", "sector": "Regional Food Bank", "sub": "1,000+ partners"},
    {"org": "Atlanta Community Food Bank", "email": "info@acfb.org", "sector": "Regional Food Bank", "sub": "700+ partners"},
    {"org": "San Antonio Food Bank", "email": "info@safoodbank.org", "sector": "Regional Food Bank", "sub": "500+ partners"},
    {"org": "Second Harvest of Silicon Valley", "email": "info@shfb.org", "sector": "Regional Food Bank", "sub": "400+ partners"},
    {"org": "Phoenix Food Bank (St. Mary's)", "email": "info@stmarysfoodbank.org", "sector": "Regional Food Bank", "sub": "700+ partners"},
    {"org": "Gleaners Food Bank (Detroit)", "email": "info@gcfb.org", "sector": "Regional Food Bank", "sub": "500+ partners"},
    {"org": "Cincinnati Freestore Foodbank", "email": "info@freestorefoodbank.org", "sector": "Regional Food Bank", "sub": "400+ partners"},
    {"org": "Oregon Food Bank (Portland)", "email": "info@oregonfoodbank.org", "sector": "Regional Food Bank", "sub": "600+ partners"},
    {"org": "Food Bank For New York City", "email": "info@foodbanknyc.org", "sector": "Regional Food Bank", "sub": "1,000+ partners"},
    {"org": "Greater Boston Food Bank", "email": "info@gbfb.org", "sector": "Regional Food Bank", "sub": "500+ partners"},
    {"org": "Capital Area Food Bank (DC)", "email": "info@capitalareafoodbank.org", "sector": "Regional Food Bank", "sub": "400+ partners"},
    {"org": "Second Harvest Food Bank of Middle TN", "email": "info@secondharvestmidtn.org", "sector": "Regional Food Bank", "sub": "400+ partners"},
    {"org": "Alameda County Community Food Bank", "email": "info@accfb.org", "sector": "Regional Food Bank", "sub": "300+ partners"},
    {"org": "Tampa Bay Food Bank (Feeding Tampa Bay)", "email": "info@feedingtampabay.org", "sector": "Regional Food Bank", "sub": "400+ partners"},
    {"org": "Central Texas Food Bank (Austin)", "email": "info@centraltexasfoodbank.org", "sector": "Regional Food Bank", "sub": "300+ partners"},
    {"org": "Food Lifeline (Seattle)", "email": "info@foodlifeline.org", "sector": "Regional Food Bank", "sub": "300+ partners"},
    {"org": "Harvesters (Kansas City)", "email": "info@harvesters.org", "sector": "Regional Food Bank", "sub": "400+ partners"},
    {"org": "Second Harvest Food Bank (Orlando)", "email": "info@feedhopenow.org", "sector": "Regional Food Bank", "sub": "500+ partners"},
    {"org": "Florida Association of Food Banks", "email": "info@fafloridafoodbanks.org", "sector": "Regional Food Bank", "sub": "22 member food banks"},
]

import sqlite3
db = sqlite3.connect('churches.db')
db.row_factory = sqlite3.Row

us_churches = db.execute("SELECT COUNT(*) as n FROM churches WHERE country='US'").fetchone()['n']
# Find US churches in food desert counties / high food insecurity areas
# Broad query: churches with contact in the US (food banks can partner with these)
with_phone = db.execute("SELECT COUNT(DISTINCT cv.church_id) as n FROM church_contact_values cv JOIN churches c ON c.id=cv.church_id WHERE c.country='US' AND cv.contact_type='phone'").fetchone()['n']
db.close()

print(f"US churches: {us_churches:,}, with phone: {with_phone:,}")

json.dump(LEADS, open(OUT/"faith_hunger_leads.json","w"), indent=2)
from collections import Counter
for sector, count in Counter(l['sector'] for l in LEADS).most_common():
    print(f"  {sector}: {count}")
print(f"Total: {len(LEADS)}")
