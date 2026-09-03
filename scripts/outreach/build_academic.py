"""
ACADEMIC OUTREACH — University libraries, seminaries, religion departments.
July is the start of academic purchasing cycles for fall semester.
"""
import json
from pathlib import Path
OUT = Path("outputs/outreach")

ACADEMIC = [
    # ═══ DATA ARCHIVES (distributors) ═══
    {"org": "ARDA (Association of Religion Data Archives)", "email": "arda@psu.edu", "type": "Data Archive"},
    {"org": "ICPSR - Data Curation", "email": "data@icpsr.umich.edu", "type": "Data Archive"},
    {"org": "Harvard Dataverse", "email": "dataverse@harvard.edu", "type": "Data Archive"},
    {"org": "UK Data Service", "email": "data@ukdataservice.ac.uk", "type": "Data Archive"},

    # ═══ THEOLOGY SCHOOLS (top 15 US) ═══
    {"org": "Harvard Divinity School - Library", "email": "divlib@hds.harvard.edu", "type": "Seminary Library"},
    {"org": "Yale Divinity School - Library", "email": "divinity.library@yale.edu", "type": "Seminary Library"},
    {"org": "Princeton Theological Seminary - Library", "email": "library@ptsem.edu", "type": "Seminary Library"},
    {"org": "Duke Divinity School - Library", "email": "divref@duke.edu", "type": "Seminary Library"},
    {"org": "Union Theological Seminary (NYC)", "email": "library@uts.columbia.edu", "type": "Seminary Library"},
    {"org": "University of Chicago Divinity School", "email": "divinity@uchicago.edu", "type": "Seminary"},
    {"org": "Notre Dame - Theology Library", "email": "lib.theo@nd.edu", "type": "Seminary Library"},
    {"org": "Fuller Theological Seminary - Library", "email": "library@fuller.edu", "type": "Seminary Library"},
    {"org": "Boston University School of Theology", "email": "sthlib@bu.edu", "type": "Seminary Library"},
    {"org": "Columbia Theological Seminary", "email": "library@ctsnet.edu", "type": "Seminary Library"},
    {"org": "Emory Candler School of Theology", "email": "candler@emory.edu", "type": "Seminary"},
    {"org": "Southeastern Baptist Theological Seminary", "email": "library@sebts.edu", "type": "Seminary Library"},
    {"org": "Westminster Theological Seminary", "email": "library@wts.edu", "type": "Seminary Library"},
    {"org": "Dallas Theological Seminary", "email": "library@dts.edu", "type": "Seminary Library"},
    {"org": "Gordon-Conwell Theological Seminary", "email": "library@gordonconwell.edu", "type": "Seminary Library"},

    # ═══ ASSOCIATIONS ═══
    {"org": "Association of Theological Schools (ATS)", "email": "info@ats.edu", "type": "Association"},
    {"org": "American Theological Library Association (ATLA)", "email": "atla@atla.com", "type": "Association"},
    {"org": "American Academy of Religion (AAR)", "email": "info@aarweb.org", "type": "Association"},
    {"org": "Society for the Scientific Study of Religion (SSSR)", "email": "sssr@sociology.rutgers.edu", "type": "Association"},
    {"org": "Religious Research Association (RRA)", "email": "rra@rraweb.org", "type": "Association"},

    # ═══ TOP RELIGION DEPARTMENTS (sociology of religion) ═══
    {"org": "Pew Research Center - Data", "email": "info@pewresearch.org", "type": "Research"},
    {"org": "Baylor University - Religion Dept", "email": "religion@baylor.edu", "type": "Department"},
    {"org": "University of Notre Dame - Sociology of Religion", "email": "soc@nd.edu", "type": "Department"},
    {"org": "Penn State - Sociology of Religion", "email": "sociology@psu.edu", "type": "Department"},
    {"org": "Boston University - Religion Dept", "email": "religion@bu.edu", "type": "Department"},
    {"org": "University of Southern California - Religion", "email": "religion@usc.edu", "type": "Department"},
    {"org": "University of North Carolina - Religious Studies", "email": "relg@unc.edu", "type": "Department"},
    {"org": "University of Virginia - Religious Studies", "email": "religiousstudies@virginia.edu", "type": "Department"},
    {"org": "University of Toronto - Religion", "email": "religion@utoronto.ca", "type": "Department"},
    {"org": "Oxford University - Theology & Religion", "email": "admin@theology.ox.ac.uk", "type": "Department"},

    # ═══ CANADIAN THEOLOGY SCHOOLS ═══
    {"org": "University of Toronto - Trinity College", "email": "trinity.library@utoronto.ca", "type": "Seminary"},
    {"org": "McGill University - Religious Studies", "email": "religiousstudies@mcgill.ca", "type": "Department"},
    {"org": "Regent College (Vancouver)", "email": "library@regent-college.edu", "type": "Seminary Library"},
    {"org": "Wycliffe College (Toronto)", "email": "library@wycliffecollege.ca", "type": "Seminary Library"},

    # ═══ RELIGIOUS STUDIES DATABASES (would license/resell) ═══
    {"org": "ProQuest Religion Database", "email": "partners@proquest.com", "type": "Publisher"},
    {"org": "EBSCO Religion & Philosophy", "email": "content@ebsco.com", "type": "Publisher"},
    {"org": "JSTOR - Content Partnerships", "email": "participation@jstor.org", "type": "Publisher"},
    {"org": "Brill - Religious Studies", "email": "sales@brill.com", "type": "Publisher"},
    {"org": "De Gruyter - Theology", "email": "info@degruyter.com", "type": "Publisher"},
    {"org": "Oxford University Press - Digital", "email": "onlinesales@oup.com", "type": "Publisher"},
    {"org": "Cambridge University Press - Collections", "email": "online@cambridge.org", "type": "Publisher"},
]

json.dump(ACADEMIC, open(OUT/"academic_leads.json","w"), indent=2)
from collections import Counter
print(f"Academic leads: {len(ACADEMIC)}")
for t, n in Counter(l['type'] for l in ACADEMIC).most_common():
    print(f"  {t}: {n}")
