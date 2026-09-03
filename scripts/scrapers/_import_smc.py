"""Import SMC churches collected from Playwright sessions."""
import json, sqlite3

# Combined data from 3 conferences
all_data = []

# Eastern (42 churches) - from the longer extract
eastern = json.loads('[{"name":"The Worship Center","address":"3075 Livingston Road","city":"Bryans Road","state":"MD","zip":"20616"},{"name":"Prospect Church","address":"6020 Prospect Road","city":"Monroe","state":"NC","zip":"28112"},{"name":"Bethesda Southern Methodist Church","address":"1713 Hwy 38 West","city":"Latta","state":"SC","zip":"29565"},{"name":"Bethlehem Southern Methodist Church","address":"237 Bethlehem Road","city":"Holly Hill","state":"SC","zip":"29059"},{"name":"Bowman Southern Methodist Church","address":"310 Reevesville Rd.","city":"Bowman","state":"SC","zip":"29018"},{"name":"Camden Southern Methodist Church","address":"2388 Haile St. Ext.","city":"Camden","state":"SC","zip":"29020"},{"name":"Cameron Southern Methodist Church","address":"5346 Cameron Road","city":"Cameron","state":"SC","zip":"29030"},{"name":"Charlestowne Southern Methodist Church","address":"1405 Miles Drive","city":"Charleston","state":"SC","zip":"29407"},{"name":"Clydes Chapel Southern Methodist Church","address":"2001 Spann Road","city":"Batesburg","state":"SC","zip":"29006"},{"name":"Cool Springs Southern Methodist Church","address":"3051 Hwy. 319","city":"Aynor","state":"SC","zip":"29511"},{"name":"Denny Memorial Southern Methodist Church","address":"1605 Old State Road","city":"Gaston","state":"SC","zip":"29053"},{"name":"Ebenezer Southern Methodist Church","address":"112 Ebenezer Road","city":"Leesville","state":"SC","zip":"29070"},{"name":"Ebenezer Southern Methodist Church","address":"1048 Dudley Road","city":"Marion","state":"SC","zip":"29571"},{"name":"Ehrhardt Southern Methodist Church","address":"13667 Broxton Bridge Road (Hwy 601 S)","city":"Ehrhardt","state":"SC","zip":"29081"},{"name":"First Southern Methodist Church","address":"9715 Miles Jamison Road","city":"Summerville","state":"SC","zip":"29485"},{"name":"First Southern Methodist Church","address":"6176 West Market Street Ext.","city":"Cheraw","state":"SC","zip":"29520"},{"name":"First Southern Methodist Church","address":"2017 Fork Shoals Road","city":"Greenville","state":"SC","zip":"29605"},{"name":"First Southern Methodist Church","address":"820 Lakeview Blvd.","city":"Hartsville","state":"SC","zip":"29550"},{"name":"First Southern Methodist Church","address":"2456 Broughton Street","city":"Orangeburg","state":"SC","zip":"29118"},{"name":"First Southern Methodist Church","address":"321 Miller Road","city":"Sumter","state":"SC","zip":"29150"},{"name":"Givhans Southern Methodist Church","address":"1553 Highway 61","city":"Ridgeville","state":"SC","zip":"29472"},{"name":"Harleyville Southern Methodist Church","address":"138 2nd Bend Road","city":"Harleyville","state":"SC","zip":"29448"},{"name":"Hebron Southern Methodist Church","address":"654 Hebron Road","city":"Neeses","state":"SC","zip":"29107"},{"name":"Hilda Southern Methodist Church","address":"228 Old Salem Road","city":"Hilda","state":"SC","zip":"29813"},{"name":"Hopewell Southern Methodist Church","address":"319 Kurt Poole Road","city":"North","state":"SC","zip":"29112"},{"name":"Huggins Chapel Southern Methodist Church","address":"341 Melvin Road","city":"Hemingway","state":"SC","zip":"29554"},{"name":"Johns Island Southern Methodist Church","address":"3209 Maybank Highway","city":"Johns Island","state":"SC","zip":"29457"},{"name":"Latta Southern Methodist Church","address":"401 East Main Street","city":"Latta","state":"SC","zip":"29565"},{"name":"Leesville Southern Methodist Church","address":"2252 Leesville Church Road","city":"Laurens","state":"SC","zip":"29360"},{"name":"Morris Chapel Southern Methodist Church","address":"1189 New Hope Road","city":"Pomaria","state":"SC","zip":"29126"},{"name":"Newman Swamp Southern Methodist Church","address":"1798 Andrews Mill Road","city":"Lamar","state":"SC","zip":"29069"},{"name":"North Augusta Southern Methodist Church","address":"615 W. Martintown Road","city":"North Augusta","state":"SC","zip":"29841"},{"name":"Pee Dee Southern Methodist Church","address":"401 Highway 301 N.","city":"Marion","state":"SC","zip":"29571"},{"name":"Philadelphia Southern Methodist Church","address":"1665 Philadelphia Street","city":"Darlington","state":"SC","zip":"29532"},{"name":"Prospect Southern Methodist Church","address":"585 Waterspring Road","city":"Orangeburg","state":"SC","zip":"29115"},{"name":"Prospect Southern Methodist Church","address":"344 Flatwoods Road","city":"Bowman","state":"SC","zip":"29018"},{"name":"Red Hill Southern Methodist Church","address":"14400 Pee Dee Hwy S","city":"Galivants Ferry","state":"SC","zip":"29544"},{"name":"Ridgeville Southern Methodist Church","address":"414 School Street","city":"Ridgeville","state":"SC","zip":"29472"},{"name":"The Southern Methodist Church of Summerton","address":"1107 Felton Street","city":"Summerton","state":"SC","zip":"29148"},{"name":"Timmonsville Southern Methodist Church","address":"Byrd Street","city":"Timmonsville","state":"SC","zip":"29161"},{"name":"Turbeville Southern Methodist Church","address":"1642 Main Street","city":"Turbeville","state":"SC","zip":"29162"},{"name":"Will of Faith Southern Methodist Church","address":"Hibiscus Road","city":"Timmonsville","state":"SC","zip":"29161"},{"name":"Zion Southern Methodist Church","address":"5915 Ora Road","city":"Mullins","state":"SC","zip":"29574"}]')

midsouth = json.loads('[{"name":"Antioch Southern Methodist Church","address":"11441 Centerhill Martin Road","city":"Collinsville","state":"MS","zip":"39325"},{"name":"Bethel Southern Methodist Church","address":"1871 Bethel Church Road","city":"Bailey","state":"MS","zip":"39320"},{"name":"Community Southern Methodist Church","address":"1093 Dyess Bridge Road","city":"Waynesboro","state":"MS","zip":"39367"},{"name":"Lewis Chapel Southern Methodist Church","address":"1289 Denham Progress Road","city":"Bukatunna","state":"MS","zip":"39322"},{"name":"Pine Springs Southern Methodist Church","address":"8256 Pine Springs Road","city":"Meridian","state":"MS","zip":"39305"},{"name":"Southern Methodist Church of Waynesboro","address":"1306 Fairview Avenue","city":"Waynesboro","state":"MS","zip":"39367"},{"name":"Wesley Southern Methodist Church","address":"1002 N. Bennett Street","city":"Crystal Springs","state":"MS","zip":"39059"},{"name":"Wesley Southern Methodist Church","address":"223 North 19th Avenue","city":"Hattiesburg","state":"MS","zip":"39401"},{"name":"Craigfield Southern Methodist Church","address":"Pinewood Road","city":"Fairview","state":"TN","zip":"37062"},{"name":"First Southern Methodist Church","address":"4409 Colorado Avenue","city":"Nashville","state":"TN","zip":"37209"},{"name":"Franklin Southern Methodist Church","address":"1332 Adams Street","city":"Franklin","state":"TN","zip":"37064"},{"name":"Goodlettsville Southern Methodist Church","address":"300 Draper Circle","city":"Goodlettsville","state":"TN","zip":"37072"},{"name":"New Beginnings Southern Methodist Church","address":"7700 George E. Horn Road","city":"Nashville","state":"TN","zip":"37221"},{"name":"Prospect SMC","address":"235 Main Street","city":"Prospect","state":"TN","zip":""}]')

southwest = json.loads('[{"name":"Faith Southern Methodist Church","address":"4840 Magnolia Highway","city":"El Dorado","state":"AR","zip":"71730"},{"name":"Davis Springs Southern Methodist Church","address":"203 Davis Springs Road","city":"Campti","state":"LA","zip":"71411"},{"name":"First Southern Methodist Church","address":"410 East Mulberry Street","city":"Amite","state":"LA","zip":"70422"},{"name":"First Southern Methodist Church","address":"314 Old Jefferson Road","city":"Stonewall","state":"LA","zip":"71078"},{"name":"Holley Springs Southern Methodist Church","address":"152 Holly Springs Church Road","city":"Coushatta","state":"LA","zip":"71019"},{"name":"SMC of Haughton","address":"4206 Highway 80","city":"Haughton","state":"LA","zip":"71037"},{"name":"Walnut Grove Southern Methodist Church","address":"1936 Cooney Bonnett Road","city":"West Monroe","state":"LA","zip":"71292"},{"name":"Harris Chapel Southern Methodist Church","address":"17069 CR 452","city":"Lindale","state":"TX","zip":"75771"}]')

all_data = eastern + midsouth + southwest
print(f'Total: {len(all_data)} churches')

# Import
db = sqlite3.connect(r'E:\grid\churches.db')
db.execute('PRAGMA busy_timeout=60000')
c = db.cursor()

mov = c.execute("SELECT id FROM movement WHERE name='Southern Methodist Church'").fetchone()
if not mov:
    mid = c.execute("SELECT MAX(id) FROM movement").fetchone()[0] + 1
    meth_id = c.execute("SELECT id FROM tradition WHERE name='Methodist'").fetchone()[0]
    c.execute("INSERT INTO movement (id, name, tradition_id) VALUES (?,?,?)", (mid, 'Southern Methodist Church', meth_id))
    db.commit(); mov_id = mid
else: mov_id = mov[0]

prot_id = c.execute("SELECT id FROM legacy WHERE name='Protestant'").fetchone()[0]
meth_id = c.execute("SELECT id FROM tradition WHERE name='Methodist'").fetchone()[0]
nid = c.execute('SELECT MAX(id) FROM churches').fetchone()[0] + 1
imp = dup = 0

for ch in all_data:
    if not ch['state']: continue
    ex = c.execute("SELECT id FROM churches WHERE name=? AND city=? AND state=? AND faith='Christian'",
                   (ch['name'], ch['city'], ch['state'])).fetchone()
    if ex:
        c.execute("UPDATE churches SET movement_id=?, tradition_id=?, legacy_id=? WHERE id=? AND movement_id IS NULL",
                  (mov_id, meth_id, prot_id, ex[0]))
        if c.rowcount > 0: dup += 1; continue
    c.execute("""INSERT INTO churches (id, name, city, state, country, address,
        faith, culture_id, legacy_id, tradition_id, movement_id, landmark_type, source)
        VALUES (?,?,?,?,'US',?,'Christian',555,?,?,?,'church','smc_playwright')""",
        (nid, ch['name'], ch['city'], ch['state'], ch['address'], prot_id, meth_id, mov_id))
    nid += 1; imp += 1

db.commit()
print(f'  New: {imp} | Updated: {dup}')
db.close()
print('DONE')
