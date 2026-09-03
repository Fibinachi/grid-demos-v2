"""Name-based classification — compiled regex, batch updates, single transaction."""
import sqlite3, re, json
from datetime import datetime

DB = 'E:/grid/churches.db'
db = sqlite3.connect(DB, timeout=60)
c = db.cursor()
TOTAL = c.execute('SELECT COUNT(*) FROM churches').fetchone()[0]

RULES = [
    (re.compile(r'\bCATHOLIC\b', re.I), 'Roman Catholic Church', 'Catholic Churches', 'catholic'),
    (re.compile(r'\bBYZANTINE\s+CATHOLIC\b', re.I), 'Byzantine Catholic Church', 'Catholic Churches', 'byzantine_catholic'),
    (re.compile(r'\bMARONITE\b', re.I), 'Maronite Catholic Church', 'Catholic Churches', 'maronite'),
    (re.compile(r'\bGREEK\s+ORTHODOX\b', re.I), 'Greek Orthodox Archdiocese of America', 'Orthodox Churches', 'greek_orthodox'),
    (re.compile(r'\bRUSSIAN\s+ORTHODOX\b', re.I), 'Russian Orthodox Church', 'Orthodox Churches', 'russian_orthodox'),
    (re.compile(r'\bCOPTIC\s+ORTHODOX\b', re.I), 'Coptic Orthodox Church', 'Orthodox Churches', 'coptic_orthodox'),
    (re.compile(r'\bSERBIAN\s+ORTHODOX\b', re.I), 'Serbian Orthodox Church', 'Orthodox Churches', 'serbian_orthodox'),
    (re.compile(r'\bROMANIAN\s+ORTHODOX\b', re.I), 'Romanian Orthodox Church', 'Orthodox Churches', 'romanian_orthodox'),
    (re.compile(r'\bUKRAINIAN\s+ORTHODOX\b', re.I), 'Ukrainian Orthodox Church', 'Orthodox Churches', 'ukrainian_orthodox'),
    (re.compile(r'\bARMENIAN\s+(APOSTOLIC|ORTHODOX)\b', re.I), 'Armenian Apostolic Church', 'Orthodox Churches', 'armenian'),
    (re.compile(r'\bETHIOPIAN\s+ORTHODOX\b', re.I), 'Ethiopian Orthodox Tewahedo Church', 'Orthodox Churches', 'ethiopian_orthodox'),
    (re.compile(r'\bANTIOCHIAN\s+ORTHODOX\b', re.I), 'Antiochian Orthodox Christian Archdiocese', 'Orthodox Churches', 'antiochian_orthodox'),
    (re.compile(r'\bMALANKARA\s+ORTHODOX\b', re.I), 'Malankara Orthodox Syrian Church', 'Orthodox Churches', 'malankara'),
    (re.compile(r'\bSYRIAN\s+ORTHODOX\b', re.I), 'Malankara Orthodox Syrian Church', 'Orthodox Churches', 'syrian_orthodox'),
    (re.compile(r'\bORTHODOX\s+CHURCH\s+IN\s+AMERICA\b', re.I), 'Orthodox Church in America', 'Orthodox Churches', 'oca'),
    (re.compile(r'\bBULGARIAN\s+ORTHODOX\b', re.I), 'Bulgarian Orthodox Church', 'Orthodox Churches', 'bulgarian_orthodox'),
    (re.compile(r'\bWISCONSIN\s+(EVANGELICAL\s+)?LUTHERAN\b', re.I), 'Wisconsin Evangelical Lutheran Synod', 'Lutheran Churches', 'wels'),
    (re.compile(r'\bLUTHERAN\s+CHURCH.*MISSOURI\b', re.I), 'Lutheran Church - Missouri Synod', 'Lutheran Churches', 'lcms'),
    (re.compile(r'\bMISSOURI\s+SYNOD\b', re.I), 'Lutheran Church - Missouri Synod', 'Lutheran Churches', 'lcms_short'),
    (re.compile(r'\bEVANGELICAL\s+LUTHERAN\s+CHURCH\s+IN\s+AMERICA\b', re.I), 'Evangelical Lutheran Church in America', 'Lutheran Churches', 'elca'),
    (re.compile(r'\bEVANGELICAL\s+LUTHERAN\s+SYNOD\b', re.I), 'Evangelical Lutheran Synod', 'Lutheran Churches', 'els'),
    (re.compile(r'\bLUTHERAN\b', re.I), None, 'Lutheran Churches', 'lutheran'),
    (re.compile(r'\bPRESBYTERIAN\s+CHURCH\s*\(?\s*U\.?\s*S\.?\s*A\.?\s*\)?\b', re.I), 'Presbyterian Church (U.S.A.)', 'Presbyterian Churches', 'pcusa'),
    (re.compile(r'\bORTHODOX\s+PRESBYTERIAN\b', re.I), 'Orthodox Presbyterian Church', 'Orthodox Presbyterian Church', 'opc'),
    (re.compile(r'\bPRESBYTERIAN\s+CHURCH\s+IN\s+AMERICA\b', re.I), 'Presbyterian Church in America', 'Presbyterian Churches', 'pca'),
    (re.compile(r'\bCUMBERLAND\s+PRESBYTERIAN\b', re.I), 'Cumberland Presbyterian', 'Presbyterian Churches', 'cumberland'),
    (re.compile(r'\bASSOCIATE\s+REFORMED\s+PRESBYTERIAN\b', re.I), 'Associate Reformed Presbyterian Church', 'Presbyterian Churches', 'arp'),
    (re.compile(r'\bEVANGELICAL\s+PRESBYTERIAN\b', re.I), 'Evangelical Presbyterian Church', 'Presbyterian Churches', 'epc'),
    (re.compile(r'\bPRESBYTERIAN\b', re.I), None, 'Presbyterian Churches', 'presbyterian'),
    (re.compile(r'\bUNITED\s+METHODIST\b', re.I), 'United Methodist Church', 'United Methodist Church', 'umc'),
    (re.compile(r'\bAFRICAN\s+METHODIST\s+EPISCOPAL\s+ZION\b', re.I), 'African Methodist Episcopal Zion Church', 'Methodist Churches', 'amez'),
    (re.compile(r'\bAFRICAN\s+METHODIST\s+EPISCOPAL\b', re.I), 'African Methodist Episcopal Church', 'Methodist Churches', 'ame'),
    (re.compile(r'\bCHRISTIAN\s+METHODIST\s+EPISCOPAL\b', re.I), 'Christian Methodist Episcopal Church', 'Methodist Churches', 'cme'),
    (re.compile(r'\bFREE\s+METHODIST\b', re.I), 'Free Methodist Church', 'Methodist Churches', 'free_methodist'),
    (re.compile(r'\bMETHODIST\b', re.I), None, 'Methodist Churches', 'methodist'),
    (re.compile(r'\bSOUTHERN\s+BAPTIST\b', re.I), 'Southern Baptist Convention', 'Baptist Churches', 'sbc'),
    (re.compile(r'\bMISSIONARY\s+BAPTIST\b', re.I), 'Missionary Baptist', 'Baptist Churches', 'missionary_baptist'),
    (re.compile(r'\bPRIMITIVE\s+BAPTIST\b', re.I), 'Primitive Baptist', 'Baptist Churches', 'primitive_baptist'),
    (re.compile(r'\bFREE\s+WILL\s+BAPTIST\b', re.I), 'National Association of Free Will Baptists', 'Free Will Baptist', 'free_will_baptist'),
    (re.compile(r'\bREFORMED\s+BAPTIST\b', re.I), 'Reformed Baptist', 'Baptist Churches', 'reformed_baptist'),
    (re.compile(r'\bINDEPENDENT\s+BAPTIST\b', re.I), 'Independent Baptist', 'Baptist Churches', 'independent_baptist'),
    (re.compile(r'\bFULL\s+GOSPEL\s+BAPTIST\b', re.I), 'Full Gospel Baptist Church Fellowship', 'Baptist Churches', 'full_gospel_baptist'),
    (re.compile(r'\bNATIONAL\s+BAPTIST\b', re.I), None, 'Baptist Churches', 'national_baptist'),
    (re.compile(r'\bAMERICAN\s+BAPTIST\b', re.I), None, 'Baptist Churches', 'american_baptist'),
    (re.compile(r'\bBAPTIST\b', re.I), None, 'Baptist Churches', 'baptist'),
    (re.compile(r'\bASSEMBL[YI]ES\s+OF\s+GOD\b', re.I), 'Assemblies of God', 'Pentecostal Churches', 'ag'),
    (re.compile(r'\bCHURCH\s+OF\s+GOD\s+IN\s+CHRIST\b', re.I), 'Church of God in Christ', 'Pentecostal Churches', 'cogic'),
    (re.compile(r'\bCHURCH\s+OF\s+GOD\s+OF\s+PROPHECY\b', re.I), 'Church of God of Prophecy', 'Pentecostal Churches', 'cogop'),
    (re.compile(r'\bFOURSQUARE\b', re.I), 'Foursquare Church', 'Pentecostal Churches', 'foursquare'),
    (re.compile(r'\bUNITED\s+PENTECOSTAL\b', re.I), 'United Pentecostal Church International', 'Pentecostal Churches', 'upci'),
    (re.compile(r'\bPENTECOSTAL\s+ASSEMBLIES\s+OF\s+THE\s+WORLD\b', re.I), 'Pentecostal Assemblies of the World', 'Pentecostal Churches', 'paw'),
    (re.compile(r'\bPENTECOSTAL\s+HOLINESS\b', re.I), 'International Pentecostal Holiness Church', 'Pentecostal Churches', 'iphc'),
    (re.compile(r'\bPENTECOSTAL\b', re.I), None, 'Pentecostal Churches', 'pentecostal'),
    (re.compile(r'\bCHURCH\s+OF\s+GOD\s*\(?\s*CLEVELAND\b', re.I), 'Church of God (Cleveland, TN)', 'Church of God (Cleveland, TN)', 'cog_cleveland'),
    (re.compile(r'\bCHURCH\s+OF\s+GOD\s*\(?\s*ANDERSON\b', re.I), 'Church of God (Anderson, IN)', 'Holiness Churches', 'cog_anderson'),
    (re.compile(r'\bEPISCOPAL\s+CHURCH\b', re.I), 'Episcopal Church', 'Episcopal and Anglican Churches', 'episcopal_church'),
    (re.compile(r'\bANGLICAN\b', re.I), 'Anglican Church in North America', 'Episcopal and Anglican Churches', 'anglican'),
    (re.compile(r'\bEPISCOPAL\b', re.I), 'Episcopal Church', 'Episcopal and Anglican Churches', 'episcopal'),
    (re.compile(r'\bCHURCH\s+OF\s+CHRIST\b', re.I), 'Churches of Christ', 'Churches of Christ', 'church_of_christ'),
    (re.compile(r'\bDISCIPLES\s+OF\s+CHRIST\b', re.I), 'Christian Church (Disciples of Christ)', 'Christian and Restorationist Churches', 'disciples'),
    (re.compile(r'\bCHURCH\s+OF\s+THE\s+NAZARENE\b', re.I), 'Church of the Nazarene', 'Holiness Churches', 'nazarene'),
    (re.compile(r'\bNAZARENE\b', re.I), 'Church of the Nazarene', 'Holiness Churches', 'nazarene_short'),
    (re.compile(r'\bMENNONITE\b', re.I), None, 'Mennonite Churches', 'mennonite'),
    (re.compile(r'\bSEVENTH[\s-]*DAY\s+ADVENTIST\b', re.I), 'Seventh-day Adventist Church', 'Adventist Churches', 'sda'),
    (re.compile(r'\bADVENTIST\b', re.I), None, 'Adventist Churches', 'adventist'),
    (re.compile(r'\bLATTER[\s-]*DAY\s+SAINTS\b', re.I), 'LDS / Mormon', 'lds', 'lds'),
    (re.compile(r'\bMORMON\b', re.I), 'LDS / Mormon', 'lds', 'mormon'),
    (re.compile(r"\bJEHOVAH'?S?\s+WITNESS", re.I), "Jehovah's Witness", 'jehovahs_witness', 'jw'),
    (re.compile(r'\bCHABAD\b', re.I), 'Jewish (Chabad)', 'jewish', 'chabad'),
    (re.compile(r'\bSYNAGOGUE\b', re.I), None, 'jewish', 'synagogue'),
    (re.compile(r'\bTEMPLE\s+(BETH|B\'?NAI|ISRAEL|SHALOM|SINAI|EMANU?EL|JUDEA|ZION)\b', re.I), None, 'jewish', 'jewish_temple'),
    (re.compile(r'\bISLAMIC\b', re.I), None, 'Muslim', 'islamic'),
    (re.compile(r'\bMOSQUE\b', re.I), None, 'Muslim', 'mosque'),
    (re.compile(r'\bMASJID\b', re.I), None, 'Muslim', 'masjid'),
    (re.compile(r'\bMUSLIM\b', re.I), None, 'Muslim', 'muslim'),
    (re.compile(r'\bBUDDHIST\b', re.I), None, 'Buddhist', 'buddhist'),
    (re.compile(r'\bHINDU\b', re.I), None, 'Hindu', 'hindu'),
    (re.compile(r'\bSIKH\b', re.I), None, 'Sikh', 'sikh'),
    (re.compile(r'\bGURDWARA\b', re.I), None, 'Sikh', 'gurdwara'),
    (re.compile(r'\bQUAKER\b', re.I), 'Religious Society of Friends (Quakers)', 'Friends (Quaker) Churches', 'quaker'),
    (re.compile(r'\bSOCIETY\s+OF\s+FRIENDS\b', re.I), 'Religious Society of Friends (Quakers)', 'Friends (Quaker) Churches', 'friends'),
    (re.compile(r'\bUNITARIAN\b', re.I), 'Unitarian Universalist', 'Unitarian', 'unitarian'),
    (re.compile(r"\bBAHA[I']\s", re.I), 'Bahai (General)', 'Bahai', 'bahai'),
    (re.compile(r'\bSCIENTOLOGY\b', re.I), 'Class V Org', 'Scientology', 'scientology'),
    (re.compile(r'\bSALVATION\s+ARMY\b', re.I), 'Salvation Army', 'Holiness Churches', 'salvation_army'),
    (re.compile(r'\bMORAVIAN\b', re.I), 'Moravian Church in North America', 'Brethren Churches', 'moravian'),
    (re.compile(r'\bCHURCH\s+OF\s+THE\s+BRETHREN\b', re.I), 'Church of the Brethren', 'Brethren Churches', 'cob'),
    (re.compile(r'\bBRETHREN\b', re.I), None, 'Brethren Churches', 'brethren'),
    (re.compile(r'\bCHRISTIAN\s+SCIENCE\b', re.I), 'Christian Science (First Church of Christ, Scientist)', 'Other Churches', 'christian_science'),
    (re.compile(r'\bCHRIST\s*,\s*SCIENTIST\b', re.I), 'Christian Science (First Church of Christ, Scientist)', 'Other Churches', 'christ_scientist'),
    (re.compile(r'\bUNITED\s+CHURCH\s+OF\s+CHRIST\b', re.I), 'United Church of Christ', 'Congregational Churches', 'ucc'),
    (re.compile(r'\bCONGREGATIONAL\b', re.I), None, 'Congregational Churches', 'congregational'),
    (re.compile(r'\bCHRISTIAN\s+REFORMED\b', re.I), 'Christian Reformed Church in North America', 'Reformed Churches', 'crc'),
    (re.compile(r'\bREFORMED\s+CHURCH\s+IN\s+AMERICA\b', re.I), 'Reformed Church in America', 'Reformed Churches', 'rca'),
    (re.compile(r'\bREFORMED\b', re.I), None, 'Reformed Churches', 'reformed'),
    (re.compile(r'\bCALVARY\s+CHAPEL\b', re.I), 'Calvary Chapel', 'Other Churches', 'calvary_chapel'),
    (re.compile(r'\bVINEYARD\s+(CHURCH|CHRISTIAN|FELLOWSHIP|COMMUNITY)\b', re.I), 'Vineyard Churches', 'Other Churches', 'vineyard'),
    (re.compile(r'\bCHRISTIAN\s+AND\s+MISSIONARY\s+ALLIANCE\b', re.I), 'Christian and Missionary Alliance', 'Holiness Churches', 'cma'),
    (re.compile(r'\bEVANGELICAL\s+FREE\b', re.I), 'Evangelical Free Church of America', 'Other Churches', 'efca'),
    (re.compile(r'\bEVANGELICAL\s+COVENANT\b', re.I), 'Evangelical Covenant Church', 'Other Churches', 'ecc'),
    (re.compile(r'\bWESLEYAN\b', re.I), 'Wesleyan Church', 'wesleyan', 'wesleyan'),
    (re.compile(r'\bCOMMUNITY\s+OF\s+CHRIST\b', re.I), 'Community of Christ', 'Other Churches', 'community_of_christ'),
    (re.compile(r'\bMETROPOLITAN\s+COMMUNITY\s+CHURCH\b', re.I), 'Metropolitan Community Churches', 'Other Churches', 'mcc'),
]

b_denom = c.execute("SELECT COUNT(*) FROM churches WHERE denomination IS NULL OR denomination = ''").fetchone()[0]
b_family = c.execute("SELECT COUNT(*) FROM churches WHERE family IS NULL OR family = ''").fetchone()[0]
print(f'Before: undenominated={b_denom:,} unfamilied={b_family:,}')

c.execute("SELECT id, name FROM churches WHERE (denomination IS NULL OR denomination = '') OR (family IS NULL OR family = '')")
rows = c.fetchall()
print(f'Candidates: {len(rows):,}')

denom_updates = []
family_updates = []

for church_id, name in rows:
    if not name:
        continue
    for pattern, denom, family, rule_name in RULES:
        if pattern.search(name):
            if denom:
                denom_updates.append((denom, family, rule_name, church_id))
            else:
                family_updates.append((family, rule_name, church_id))
            break

print(f'Matched: {len(denom_updates):,} denom, {len(family_updates):,} family-only')

# Temp table approach (much faster than 42K individual UPDATEs)
print('Applying via temp table...')
c.execute('BEGIN')
c.execute('CREATE TEMP TABLE _classify (id INTEGER PRIMARY KEY, denomination TEXT, family TEXT, source TEXT)')
if denom_updates:
    c.executemany("INSERT INTO _classify VALUES (?,?,?,?)", [(cid, d, f, s) for d, f, s, cid in denom_updates])
if family_updates:
    c.executemany("INSERT INTO _classify(id,family,source) VALUES (?,?,?)", [(cid, f, s) for f, s, cid in family_updates])
# Single joined UPDATE
c.execute("""UPDATE churches SET 
    denomination = COALESCE(_classify.denomination, churches.denomination),
    family = _classify.family,
    classification_source = _classify.source
FROM _classify WHERE churches.id = _classify.id""")
c.execute('DROP TABLE _classify')
c.execute('COMMIT')
print('Committed.')

# Provenance (separate transaction — won't rollback classification)
NOW = datetime.utcnow().isoformat()
total = len(denom_updates) + len(family_updates)
c.execute("""INSERT INTO provenance_log (source,script_name,started_at,completed_at,churches_updated,churches_inserted,fields_populated,parameters,records_attempted,records_matched,status,notes) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
    ('name_classification','classify_by_name_v2',NOW,NOW,total,0,'denomination,family,classification_source',json.dumps({'rules':len(RULES),'denom':len(denom_updates),'family':len(family_updates)}),len(rows),total,'completed',f'{len(denom_updates)} denom, {len(family_updates)} family-only'))
try:
    c.execute("""INSERT INTO enrichment_change_log (church_id,field_name,old_value,new_value,change_source,enrichment_version,changed_at) VALUES (0,'denomination,family','(empty)',?,'classify_by_name','2.0',?)""", (f'mass:{total}_churches',NOW))
except:
    pass  # may fail if church_id is strict NOT NULL
db.commit()
print('Committed.')

a_denom = c.execute("SELECT COUNT(*) FROM churches WHERE denomination IS NULL OR denomination = ''").fetchone()[0]
a_family = c.execute("SELECT COUNT(*) FROM churches WHERE family IS NULL OR family = ''").fetchone()[0]
print(f'\nDenominated: {TOTAL-a_denom:,} (+{b_denom-a_denom:,})')
print(f'Familied: {TOTAL-a_family:,} (+{b_family-a_family:,})')
print(f'Still undenominated: {a_denom:,}')
print(f'Still unfamilied: {a_family:,}')
print(f'provenance_log: {c.execute("SELECT COUNT(*) FROM provenance_log").fetchone()[0]}')
print(f'Integrity: {c.execute("PRAGMA integrity_check").fetchone()[0]}')
db.close()
print('Done.')
