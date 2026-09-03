"""
_classify_catholic_entities.py - Fast bulk classifier for Catholic records.
"""
import sqlite3, re, sys
from collections import defaultdict

DB = 'E:/grid/churches.db'

DIOCESES_BY_ST = {'AL':['Birmingham','Mobile'],'AK':['Anchorage','Fairbanks'],'AZ':['Phoenix','Tucson'],'AR':['Little Rock'],'CA':['Los Angeles','San Francisco','Oakland','San Jose','Sacramento','San Diego','Monterey','Orange','San Bernardino','Fresno','Stockton','Santa Rosa'],'CO':['Denver','Colorado Springs','Pueblo'],'CT':['Hartford','Bridgeport','Norwich'],'DE':['Wilmington'],'DC':['Washington'],'FL':['Miami','St. Augustine','St. Petersburg','Orlando','Palm Beach','Venice','Pensacola-Tallahassee'],'GA':['Atlanta','Savannah'],'HI':['Honolulu'],'ID':['Boise'],'IL':['Chicago','Joliet','Peoria','Rockford','Springfield','Belleville'],'IN':['Indianapolis','Fort Wayne-South Bend','Gary','Evansville','Lafayette'],'IA':['Des Moines','Davenport','Dubuque','Sioux City'],'KS':['Kansas City','Dodge City','Salina','Wichita'],'KY':['Louisville','Covington','Lexington','Owensboro'],'LA':['New Orleans','Baton Rouge','Alexandria','Houma-Thibodaux','Lafayette','Lake Charles','Shreveport'],'ME':['Portland'],'MD':['Baltimore'],'MA':['Boston','Fall River','Springfield','Worcester'],'MI':['Detroit','Grand Rapids','Gaylord','Kalamazoo','Lansing','Marquette','Saginaw'],'MN':['St. Paul','Crookston','Duluth','New Ulm','St. Cloud','Winona'],'MS':['Jackson','Biloxi'],'MO':['St. Louis','Kansas City-St. Joseph','Jefferson City','Springfield-Cape Girardeau'],'MT':['Helena','Great Falls-Billings'],'NE':['Omaha','Lincoln','Grand Island'],'NV':['Las Vegas','Reno'],'NH':['Manchester'],'NJ':['Newark','Camden','Metuchen','Paterson','Trenton'],'NM':['Santa Fe','Las Cruces','Gallup'],'NY':['New York','Albany','Brooklyn','Buffalo','Ogdensburg','Rochester','Rockville Centre','Syracuse'],'NC':['Charlotte','Raleigh'],'ND':['Bismarck','Fargo'],'OH':['Cincinnati','Cleveland','Columbus','Steubenville','Toledo','Youngstown'],'OK':['Oklahoma City','Tulsa'],'OR':['Portland','Baker'],'PA':['Philadelphia','Pittsburgh','Allentown','Altoona-Johnstown','Erie','Greensburg','Harrisburg','Scranton'],'RI':['Providence'],'SC':['Charleston'],'SD':['Sioux Falls','Rapid City'],'TN':['Nashville','Knoxville','Memphis'],'TX':['Galveston-Houston','Dallas','Fort Worth','Austin','San Antonio','Amarillo','Beaumont','Brownsville','Corpus Christi','El Paso','Laredo','Lubbock','San Angelo','Tyler','Victoria'],'UT':['Salt Lake City'],'VT':['Burlington'],'VA':['Richmond','Arlington'],'WA':['Seattle','Spokane','Yakima'],'WV':['Wheeling-Charleston'],'WI':['Milwaukee','Green Bay','La Crosse','Madison','Superior'],'WY':['Cheyenne']}
ARCH_NAMES = {'Anchorage','Atlanta','Baltimore','Boston','Chicago','Cincinnati','Denver','Detroit','Galveston-Houston','Hartford','Indianapolis','Kansas City','Los Angeles','Louisville','Miami','Milwaukee','Mobile','New Orleans','New York','Newark','Oklahoma City','Omaha','Philadelphia','Portland','St. Louis','St. Paul','San Antonio','San Francisco','Santa Fe','Seattle','Washington'}

def classify(n):
    n=n.lower().strip()
    if re.search(r'^(almost three years|here are the|hundreds pack|images of our|key deadline|la archdiocese parish leadership|la catholics remember|lausd must|like bishop|masses launching|not quite santa|mount saint marys)',n):return'junk'
    if re.search(r'(archbishop|archdiocese).*(celebrates|concludes|dedicates|joins|after|host|welcome|commemorate)',n):return'junk'
    if re.search(r'(saturday|sunday)\s+\d{1,2}(::\d{2})?\s*(am|pm)',n):return'junk'
    if re.match(r'^(st\.?\s+)?\w+\s+\d{1,2}$',n):return'junk'
    for p in ['cathedral of praise','cathedral of the holy spirit','cathedral of truth','cathedral of hope','cathedral body of christ','cathedral of faith','covenant church','lancaster cathedral','gordon feltus lazard cathedral']:
        if p in n:return'non_catholic'
    if 'united states conference of catholic bishops' in n or n=='usccb':return'national_body'
    if 'archdiocese' in n and any(d.lower() in n for d in ARCH_NAMES):return'archdiocese'
    if 'archdiocese' in n and ('catholic' in n or 'roman' in n):return'archdiocese'
    if 'diocese' in n and ('catholic' in n or 'roman' in n):return'diocese'
    if 'eparchy of' in n:return'diocese'
    if any(x in n for x in ['high school','middle school','elementary school','grammar school','grade school','regional school','preparatory school','academy','catholic school','college','university','seminary']):return'school'
    if n.endswith(' school') and len(n)<60:return'school'
    if 'school of' in n:return'school'
    if any(x in n for x in ['hospital','medical center','health system','health center','healthcare','nursing home','assisted living','hospice']):return'hospital'
    if any(x in n for x in ['order of','sisters of','brothers of','fathers of','school sisters','little sisters','missionary sisters','missionaries of','daughters of','society of jesus','congregation of the','franciscan','jesuit','dominican','benedictine','carmelite','oblate','paulist','redemptorist','vincentian','salesian','marist']):return'religious_order'
    if any(x in n for x in ['monastery','convent','abbey','priory','cloister']):return'monastery'
    if 'cemetery' in n and 'church' not in n:return'cemetery'
    if any(x in n for x in ['catholic charities','catholic social services','catholic community services','catholic family','catholic relief','st vincent de paul']):return'charity'
    if any(x in n for x in ['knights of columbus','k of c','columbus club','columbus hall']):return'fraternal'
    if any(x in n for x in ['retreat center','retreat house','spirituality center']):return'retreat_center'
    if 'shrine' in n:return'shrine'
    if 'chapel' in n and 'church' not in n:return'chapel'
    if 'mission' in n and ('catholic' in n or n.startswith(('st ','saint '))):return'mission'
    if any(x in n for x in ['catholic church','catholic parish','catholic cathedral','roman catholic','catholic community','catholic center']):return'parish'
    return'parish'

def core(n):
    n=n.lower().strip();n=re.sub(r'^the ','',n)
    for s in [' gift shop',' thrift shop',' school',' cemetery',' convent',' rectory',' parish hall',' parish center',' hall',' foundation',' trust']:
        if s in n and len(n)>len(s)+5:n=n[:n.index(s)].strip()
    return re.sub(r'\s+(inc|llc|a corp|tr|corp)$','',n).strip()

def main():
    conn=sqlite3.connect(DB)
    conn.execute('PRAGMA journal_mode=WAL');conn.execute('PRAGMA synchronous=OFF');conn.execute('PRAGMA busy_timeout=30000')
    if 'entity_type' not in [r[1] for r in conn.execute('PRAGMA table_info(churches)')]:
        conn.execute('ALTER TABLE churches ADD COLUMN entity_type TEXT');conn.commit()
    print('Loading Catholic records...')
    rows=conn.execute("SELECT id,name,city,state,county_name,county_fips,denomination FROM churches WHERE denomination LIKE '%catholic%' OR denomination LIKE '%roman%'").fetchall()
    print(f'  {len(rows)} records')
    recs={};stats=defaultdict(int);cls=[]
    for r in rows:
        cid,nm,ct,st,cn,cf,dn=r;et=classify(nm);stats[et]+=1;recs[cid]=(nm,ct,st,cn or '',cf or '',et,dn);cls.append((cid,et))
    for e,c in sorted(stats.items(),key=lambda x:-x[1]):print(f'  {e:25s}: {c:5d}')
    print('  Bulk updating entity_type...')
    conn.execute('CREATE TEMP TABLE _cc (id INTEGER PRIMARY KEY, entity_type TEXT)')
    conn.executemany('INSERT INTO _cc VALUES(?,?)',cls)
    conn.execute('UPDATE churches SET entity_type=(SELECT entity_type FROM _cc WHERE _cc.id=churches.id) WHERE id IN (SELECT id FROM _cc)')
    conn.execute('DROP TABLE _cc');conn.commit();print('  Done.')

    # --- Build parent maps in memory ---
    parent={}  # child_id -> parent_id
    dio_by_st={}  # state -> list of (dio_id, dio_name)
    arch_by_st={}  # state -> archdiocese_id
    for cid,(nm,ct,st,cn,cf,et,dn) in recs.items():
        if et=='diocese' and st:
            dio_by_st.setdefault(st.strip().upper(),[]).append((cid,nm))
        if et=='archdiocese' and st:
            arch_by_st[st.strip().upper()]=cid

    print(f'  Found {sum(len(v) for v in dio_by_st.values())} diocese, {len(arch_by_st)} archdiocese records')

    # Link parishes to diocese by state
    for cid,(nm,ct,st,cn,cf,et,dn) in recs.items():
        if et not in ('parish','mission','chapel','shrine','monastery') or not st:continue
        candidates=DIOCESES_BY_ST.get(st.strip().upper(),[])
        for cn2 in candidates:
            for did,dn2 in dio_by_st.get(st.strip().upper(),[]):
                if cn2.lower() in dn2.lower():
                    parent[cid]=did;break
            if cid in parent:break

    # Link dioceses to archdiocese
    for cid,(nm,ct,st,cn,cf,et,dn) in recs.items():
        if et!='diocese' or not st or cid in parent:continue
        aid=arch_by_st.get(st.strip().upper())
        if aid and aid!=cid:parent[cid]=aid

    # Link associated to parish (same city)
    assoc={'school','hospital','cemetery','charity','religious_order','retreat_center','fraternal','monastery','chapel','mission'}
    par_by_city=defaultdict(list)
    for cid,(nm,ct,st,cn,cf,et,dn) in recs.items():
        if et=='parish' and ct:par_by_city[(ct.strip().upper(),(st or '').strip().upper())].append((cid,nm))
    for cid,(nm,ct,st,cn,cf,et,dn) in recs.items():
        if et not in assoc or not ct or cid in parent:continue
        cands=par_by_city.get((ct.strip().upper(),(st or '').strip().upper()),[])
        c=core(nm)
        for pid,pn in cands:
            if c in core(pn) or core(pn) in c or c==core(pn):parent[cid]=pid;break

    # Link archdioceses to national body
    natl=[cid for cid,(nm,ct,st,cn,cf,et,dn) in recs.items() if et=='national_body']
    if natl:
        for cid,(nm,ct,st,cn,cf,et,dn) in recs.items():
            if et=='archdiocese' and cid not in parent:parent[cid]=natl[0]

    # Bulk apply parent_church_id
    print(f'  Applying {len(parent)} parent links...')
    if parent:
        conn.execute('CREATE TEMP TABLE _cp (id INTEGER PRIMARY KEY, parent_id INTEGER)')
        conn.executemany('INSERT INTO _cp VALUES(?,?)',[(cid,pid) for cid,pid in parent.items()])
        conn.execute('UPDATE churches SET parent_church_id=(SELECT parent_id FROM _cp WHERE _cp.id=churches.id) WHERE id IN (SELECT id FROM _cp)')
        conn.execute('DROP TABLE _cp');conn.commit()

    # Summary
    print('\n=== Final hierarchy summary ===')
    for e,c in conn.execute("SELECT entity_type,COUNT(*) FROM churches WHERE denomination LIKE '%catholic%' OR denomination LIKE '%roman%' GROUP BY 1 ORDER BY 2 DESC").fetchall():
        et=e or 'NULL'
        wp=conn.execute("SELECT COUNT(*) FROM churches WHERE entity_type=? AND parent_church_id IS NOT NULL AND (denomination LIKE '%catholic%' OR denomination LIKE '%roman%')",(e,)).fetchone()[0]
        print(f'  {et:25s}: {c:5d}  ({wp:5d} linked)')
    conn.close();print('\nDone.')

if __name__=='__main__':main()
