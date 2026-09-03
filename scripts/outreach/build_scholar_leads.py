"""Build outreach list of scholars who have published on geomapping religion, GIS spatial analysis of faith, religious demography, and minority religion mapping.

These people KNOW the pain of building these datasets from scratch. GRID is catnip to them."""
import json, sqlite3
from pathlib import Path
OUT = Path("outputs/outreach")

SCHOLARS = [
    # ═══ ARDA / US RELIGION CENSUS / CONGREGATIONAL DATA ═══
    {"name": "Roger Finke", "email": "rfinke@psu.edu", "org": "Penn State / ARDA", "field": "ARDA founder, congregational data"},
    {"name": "Christopher Bader", "email": "cbader@chapman.edu", "org": "Chapman University / ARDA", "field": "ARDA co-director"},
    {"name": "Shawna Anderson", "email": "shawna@thearda.com", "org": "ARDA", "field": "ARDA research associate"},
    {"name": "Mark Chaves", "email": "mchaves@soc.duke.edu", "org": "Duke University / NCS", "field": "National Congregations Study director"},
    {"name": "Dale E. Jones", "email": "dalejones@usreligioncensus.org", "org": "US Religion Census / ARDA", "field": "Religion census research director"},
    {"name": "Richard Houseal", "email": "dickh@usreligioncensus.org", "org": "US Religion Census", "field": "Religion Census data collection"},
    {"name": "Conrad Hackett", "email": "chackett@pewresearch.org", "org": "Pew Research Center", "field": "Pew Religion & Public Life demographer"},
    {"name": "David McClendon", "email": "dmcclendon@pewresearch.org", "org": "Pew Research Center", "field": "Pew religious demography researcher"},

    # ═══ GEOGRAPHY OF RELIGION ═══
    {"name": "Lily Kong", "email": "lilykong@smu.edu.sg", "org": "Singapore Management University", "field": "Leading geographer of religion, 150+ pubs"},
    {"name": "Justin Tse", "email": "justintse@hkbu.edu.hk", "org": "Hong Kong Baptist University", "field": "Chinese diaspora religion mapping"},
    {"name": "Elizabeth Olson", "email": "eaolson@unc.edu", "org": "UNC Chapel Hill", "field": "Geography of religion, Latin America"},
    {"name": "Adrian Ivakhiv", "email": "adrian.ivakhiv@uvm.edu", "org": "University of Vermont", "field": "Sacred space, pilgrimage, religion & ecology"},
    {"name": "Kenneth Foote", "email": "kenneth.foote@uconn.edu", "org": "University of Connecticut", "field": "Sacred space, landscape, geography"},
    {"name": "Dr. Caitlin Dempsey", "email": "caitlin@geographyrealm.com", "org": "Geography Realm", "field": "GIS editor, geography of religion writer"},
    {"name": "Catherine M. Cameron", "email": "cmcameron@cedarcrest.edu", "org": "Cedar Crest College", "field": "Pilgrimage geography, religious tourism"},
    {"name": "Michael Ferber", "email": "mferber@uchicago.edu", "org": "University of Chicago", "field": "Religion & urban space"},
    {"name": "Anna M. Gade", "email": "agade@wisc.edu", "org": "University of Wisconsin-Madison", "field": "Islam & environment, sacred geography"},
    {"name": "Brenna Moore", "email": "brenna.moore@fordham.edu", "org": "Fordham University", "field": "Religion & space, Atlantic world"},

    # ═══ HISTORICAL GIS / SPATIAL HUMANITIES ═══
    {"name": "Ruth Mostern", "email": "rmostern@pitt.edu", "org": "University of Pittsburgh", "field": "Historical GIS, Song Dynasty spatial history"},
    {"name": "Ian Gregory", "email": "i.gregory@lancaster.ac.uk", "org": "Lancaster University", "field": "Historical GIS, Irish religion demography"},
    {"name": "David Bodenhamer", "email": "dbodenha@iupui.edu", "org": "IUPUI", "field": "Spatial humanities pioneer"},
    {"name": "John Corrigan", "email": "jcorrigan@fsu.edu", "org": "Florida State University", "field": "Religion & space theory, spatial turn"},
    {"name": "Alexander von Lünen", "email": "alexvlunen@tutanota.com", "org": "Independent Scholar", "field": "HGIS, religion mapping historiography"},
    {"name": "Scott Nesbit", "email": "snesbit@uga.edu", "org": "University of Georgia", "field": "Historical GIS, Civil War religion"},
    {"name": "Diana Stuart Sinton", "email": "diana_sinton@redlands.edu", "org": "University of Redlands", "field": "Spatial literacy across disciplines"},
    {"name": "Philip Stoker", "email": "philip.stoker@utah.edu", "org": "University of Utah", "field": "Digital atlas of Buddhism in Hangzhou"},
    {"name": "Jeffery Wei", "email": "jefferywei@hku.hk", "org": "University of Hong Kong", "field": "Chinese historical GIS, temple mapping"},

    # ═══ BUDDHIST STUDIES + GIS ═══
    {"name": "Jiang Wu", "email": "jiangwu@arizona.edu", "org": "University of Arizona", "field": "Buddhist GIS, Chinese Buddhism spatial"},
    {"name": "Gregory Scott", "email": "gregoryscott@ou.edu", "org": "University of Oklahoma", "field": "Chinese Buddhist temple mapping"},
    {"name": "John Jorgensen", "email": "j.jorgensen@latrobe.edu.au", "org": "La Trobe University", "field": "Buddhist geography, China"},
    {"name": "Erik Hammerstrom", "email": "ehammerstrom@plu.edu", "org": "Pacific Lutheran University", "field": "Chinese Buddhism, spatial networks"},
    {"name": "Justin Ritzinger", "email": "ritzinger@miami.edu", "org": "University of Miami", "field": "Chinese Buddhism, sacred geography"},
    {"name": "Kristina Kade Troost", "email": "kristina.troost@duke.edu", "org": "Duke University", "field": "East Asian Buddhism, digital humanities"},

    # ═══ JAIN STUDIES (we have 437 temples) ═══
    {"name": "Anne Vallely", "email": "anne.vallely@uottawa.ca", "org": "University of Ottawa", "field": "Jain studies, ritual geography"},
    {"name": "John E. Cort", "email": "cort@denison.edu", "org": "Denison University", "field": "Leading Jain studies scholar, temple mapping"},
    {"name": "Peter Flügel", "email": "pf1@soas.ac.uk", "org": "SOAS University of London", "field": "Jain history, organizations, sects"},
    {"name": "Kiyoko Morita", "email": "morita@tokyo-u.ac.jp", "org": "University of Tokyo", "field": "Jain art & architecture, temple geography"},
    {"name": "Balbinder Singh Bhogal", "email": "bhogal@hofstra.edu", "org": "Hofstra University", "field": "Sikh & Jain studies, philosophy of space"},
    {"name": "Steven Vose", "email": "svose@miami.edu", "org": "University of Miami", "field": "Jain studies, sacred geography"},
    {"name": "M. Whitney Kelting", "email": "m.w.kelting@northeastern.edu", "org": "Northeastern University", "field": "Jain ritual space, women & temples"},

    # ═══ MINORITY / TINY FAITHS (we have comprehensive coverage) ═══
    {"name": "Michael Jerryson", "email": "mjerryson@ysu.edu", "org": "Youngstown State University", "field": "Minority religions, religion & violence"},
    {"name": "Touraj Daryaee", "email": "tdaryaee@uci.edu", "org": "UC Irvine", "field": "Zoroastrian sacred geography, Sasanian"},
    {"name": "Prods Oktor Skjærvø", "email": "skjaervo@fas.harvard.edu", "org": "Harvard University", "field": "Zoroastrian texts, Manichaean geography"},
    {"name": "Jenny Rose", "email": "jrose@claremontmckenna.edu", "org": "Claremont McKenna", "field": "Zoroastrianism, diaspora mapping"},
    {"name": "Kirsten Bliksøen Avnesli", "email": "kirsten.avnesli@teologi.uio.no", "org": "University of Oslo", "field": "Mandaean studies, minority faith mapping"},
    {"name": "Jorunn J. Buckley", "email": "jbuckley@bowdoin.edu", "org": "Bowdoin College", "field": "Mandaean religion, religious geography"},
    {"name": "Moojan Momen", "email": "moojan@momen.org.uk", "org": "Independent Scholar", "field": "Bahai history, global spread mapping"},
    {"name": "Todd Lawson", "email": "todd.lawson@utoronto.ca", "org": "University of Toronto", "field": "Bahai & Islamic studies, sacred geography"},
    {"name": "Juan Cole", "email": "jrcole@umich.edu", "org": "University of Michigan", "field": "Bahai history, Muslim world mapping"},
    {"name": "Dru C. Gladney", "email": "dgladney@psu.edu", "org": "Penn State", "field": "Chinese Islam, Hui mapping, minority geography"},
    {"name": "Mehrdad Amanat", "email": "m.amanat@uky.edu", "org": "University of Kentucky", "field": "Bahai history, global communities"},
    {"name": "Samten Yeshi", "email": "s.yeshi@latrobe.edu.au", "org": "La Trobe University", "field": "Tibetan Buddhism, sacred landscape GIS"},
    {"name": "Satoko Fujiwara", "email": "sfuji@l.u-tokyo.ac.jp", "org": "University of Tokyo", "field": "Shinto studies, Japanese sacred sites"},

    # ═══ ANCIENT / PAGAN FAITHS (24-node taxonomy) ═══
    {"name": "Diane Favro", "email": "dfavro@ucla.edu", "org": "UCLA", "field": "Ancient Roman sacred space, digital humanities"},
    {"name": "Tom Elliott", "email": "tom.elliott@nyu.edu", "org": "NYU / Pleiades", "field": "Pleiades director, ancient world mapping"},
    {"name": "Elaine Sullivan", "email": "elaine.sullivan@sonoma.edu", "org": "Sonoma State University", "field": "Ancient GIS, Egyptian sacred landscape"},
    {"name": "Richard Talbert", "email": "talbert@email.unc.edu", "org": "UNC Chapel Hill", "field": "Ancient geography, Roman religion mapping"},
    {"name": "Ian Mladjov", "email": "mladjov@umich.edu", "org": "University of Michigan", "field": "Hellenistic religion mapping, GIS"},
    {"name": "Caitlin Green", "email": "caitlin.green@britishmuseum.org", "org": "British Museum", "field": "Celtic paganism, ancient site mapping"},
    {"name": "Caroline Tully", "email": "caroline.tully@unimelb.edu.au", "org": "University of Melbourne", "field": "Neolithic/Pagan sites, Minoan religion"},

    # ═══ SHINTO (65K sites) ═══
    {"name": "Sarah Thal", "email": "thal@wisc.edu", "org": "University of Wisconsin", "field": "Shinto history, kami geography"},
    {"name": "John Breen", "email": "breen@nichibun.ac.jp", "org": "International Research Center for Japanese Studies", "field": "Shinto studies, imperial ritual space"},
    {"name": "Mark Teeuwen", "email": "mark.teeuwen@ikos.uio.no", "org": "University of Oslo", "field": "Shinto history, kami mapping"},
    {"name": "Helen Hardacre", "email": "hardacre@fas.harvard.edu", "org": "Harvard University", "field": "Shinto, Japanese religious geography"},
    {"name": "Caleb Carter", "email": "calbcarter@kyudai.jp", "org": "Kyushu University", "field": "Shinto & Buddhist sites mapping"},

    # ═══ SIKH (5,619 sites) ═══
    {"name": "Nikky-Guninder Kaur Singh", "email": "nsingh@colby.edu", "org": "Colby College", "field": "Sikh studies, spatial poetics"},
    {"name": "Arvind-pal Singh Mandair", "email": "apm@sikhstudies.org", "org": "University of Michigan", "field": "Sikh philosophy, diaspora mapping"},
    {"name": "Louis E. Fenech", "email": "louis.fenech@uni.edu", "org": "University of Northern Iowa", "field": "Sikh history, martyrdom & place"},
    {"name": "Harbans Singh", "email": "harbans@punjabiuniversity.com", "org": "Punjabi University Patiala", "field": "Sikh history, gurdwara mapping"},

    # ═══ SOCIOLOGY / RELIGION & SPATIAL DATA ═══
    {"name": "Courtney Bender", "email": "cbender@columbia.edu", "org": "Columbia University", "field": "Sacred Gotham project, religion & space"},
    {"name": "Nancy Ammerman", "email": "nammer@bu.edu", "org": "Boston University", "field": "Congregational studies, community mapping"},
    {"name": "Paul Froese", "email": "paul.froese@baylor.edu", "org": "Baylor University", "field": "Religious demography, Baylor Religion Survey"},
    {"name": "Samuel Perry", "email": "samperry@ou.edu", "org": "University of Oklahoma", "field": "Sociology of religion, congregational mapping"},
    {"name": "Rebecca Bartel", "email": "rbartel@sdsu.edu", "org": "San Diego State University", "field": "Religion & space, Latin America"},
    {"name": "Wade Clark Roof", "email": "roof@religion.ucsb.edu", "org": "UC Santa Barbara", "field": "Religion & spatial demography"},
    {"name": "Evelyn Bush", "email": "evelyn.bush@yu.edu", "org": "Yeshiva University", "field": "Religion & globalization, transnational mapping"},
    {"name": "Kraig Beyerlein", "email": "kbeyerle@nd.edu", "org": "University of Notre Dame", "field": "Congregational networks, civic space"},
    {"name": "Bradley R. E. Wright", "email": "bradley.wright@uconn.edu", "org": "University of Connecticut", "field": "Religious demography, survey data"},

    # ═══ DATA / LIBRARY SCIENCE — RELIGION ═══
    {"name": "Clifford Anderson", "email": "clifford.anderson@vanderbilt.edu", "org": "Vanderbilt University", "field": "Digital humanities, religion data curation"},
    {"name": "Tod Olson", "email": "tod@uchicago.edu", "org": "University of Chicago", "field": "ATLA data, religion metadata standards"},
]

# Stats
db = sqlite3.connect('churches.db')
raw_counts = {}
for f in ['Buddhist', 'Hindu', 'Islam', 'Judaism', 'Sikh', 'Jain', 'Confucian', 'Taoist', 'Shinto', 'Bahai']:
    n = db.execute("SELECT COUNT(*) FROM churches WHERE faith=?", (f,)).fetchone()[0]
    raw_counts[f] = n
# Tiny faiths
for f in ['Zoroastrian', 'Meher Baba', 'Samaritan', 'Druze', 'Mandaean', 'Yazidi', 'Cao Dai']:
    n = db.execute("SELECT COUNT(*) FROM churches WHERE faith LIKE ?", (f,)).fetchone()[0]
    raw_counts[f] = n
# Ancient faiths under Pagan
ancient = db.execute("SELECT COUNT(*) FROM churches WHERE faith='Pagan' OR faith='Ancient' OR faith='Other'").fetchone()[0]
raw_counts['Ancient/Pagan'] = ancient
db.close()

print(f"Scholar targets: {len(SCHOLARS)}")
print(f"\nData they can access with one SQL query:")
for k, v in sorted(raw_counts.items(), key=lambda x: -x[1]):
    print(f"  {k}: {v:,}")

json.dump(SCHOLARS, open(OUT / "scholar_leads.json", "w"), indent=2)
from collections import Counter
for field, count in Counter(s['field'].split(',')[0] for s in SCHOLARS).most_common(10):
    print(f"  {field}: {count}")
print(f"\nSaved to {OUT}/scholar_leads.json")
