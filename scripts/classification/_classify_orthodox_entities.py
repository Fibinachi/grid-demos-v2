"""
_classify_orthodox_entities.py - Fast bulk classifier for Orthodox records.
"""
import sqlite3, re, sys
from collections import defaultdict

DB = 'E:/grid/churches.db'

# Valid Orthodox denominations
ORTH_DENOMS = {'Greek Orthodox Archdiocese of America','Coptic Orthodox Church',
    'Ethiopian Orthodox Tewahedo Church','Orthodox Church in America',
    'Romanian Orthodox Church','Armenian Apostolic Church',
    'Antiochian Orthodox Christian Archdiocese','Antiochian Orthodox Christian Archdiocese of North America',
    'Ukrainian Orthodox Church','Malankara Orthodox Syrian Church',
    'Eastern Orthodox','Coptic Orthodox','Bulgarian Orthodox Church',
    'Serbian Orthodox Church','Orthodox','Other Eastern Orthodox'}
NON_ORTH = {'Orthodox Presbyterian Church','Orthodox Union','Local Spiritual Assembly'}

JEWISH_RE = re.compile(r'\b(chabad|beth|b\'?nai|chaverim|chevra|kadisha|khal|knesset|mikvah?|shul|synagog|talmud|torah|yeshiva|yeshivah|minyan|kodesh|kohanim|zvi|etz|beit|tefil[ah]\w*|hamerkaz|mesivta|eliyah\w*|simchat|shabbos|shabbat|kosher|hashem|yisrael|derech|adas|adar|agud[a-z]*\s|tzedek|bukhar|keter\s|sion\b|darchei|shomrei|hadas|grossvardein|yisroel|yeshurun|anshei|chevrah?|kahal|kehil|mach[az]|ohab|ohav|shearith|tifereth|temple\s+beth|temple\s+emanuel|temple\s+israel|congregation\s+beth|congregation\s+agud|congregation\s+b\'nai|congregation\s+ohev|jewish\s+congregation|jewish\s+center|jewish\s+community)\b', re.I)
NON_ORTH_CHRISTIAN = ['orthodox presbyterian','lutheran','methodist','baptist','evangelical','pentecostal','assembly of god','church of god','church of christ','seventh day adventist','anglican','episcopal','congregational']

def classify(n,dn):
    n=n.lower().strip();d=(dn or '').lower().strip()
    if JEWISH_RE.search(n):return'non_orthodox'
    for p in NON_ORTH_CHRISTIAN:
        if p in n and 'orthodox' not in n.replace(p,''):return'non_orthodox'
    if 'local spiritual assembly' in n or 'baha' in n:return'non_orthodox'
    jur=_juris(n,d)
    # National body / Archdiocese level
    natl_pats=['greek orthodox archdiocese of america','antiochian orthodox christian archdiocese',
               'orthodox church in america','coptic orthodox church archdiocese of north america',
               'ethiopian orthodox tewahedo church','malankara archdiocese of the syrian orthodox church',
               'serbian orthodox church','ukrainian orthodox church of the usa',
               'bulgarian eastern orthodox diocese of the usa']
    for p in natl_pats:
        if p in n:return'national_body'
    if 'metropolis of' in n and 'orthodox' in n:return'diocese'
    if 'archdiocese of' in n and 'orthodox' in n:return'diocese'
    if 'diocese of' in n and 'orthodox' in n:return'diocese'
    if 'eparchy' in n and 'orthodox' in n:return'diocese'
    if 'western american diocese of russian orthodox' in n:return'diocese'
    if 'monastery' in n:return'monastery'
    if any(x in n for x in ['seminary','theological school','college']):
        if any(x in n for x in ['orthodox','greek','coptic','russian']):return'school'
    if any(x in n for x in ['foundation for','endowment for','society of']):
        if 'orthodox' in n:return'foundation'
    if 'cemetery' in n and 'church' not in n:return'cemetery'
    if 'chapel' in n and 'church' not in n:return'chapel'
    if 'mission' in n and ('orthodox' in n or 'greek' in n or 'russian' in n):return'mission'
    if 'cathedral' in n:return'parish'
    if any(x in n for x in ['church','parish','greek orthodox','russian orthodox','orthodox church','coptic orthodox','orthodox community','orthodox parish','orthodox cathedral']):return'parish'
    if any(x in n for x in ['st ','saint ','holy ']):return'parish'
    return'parish'

def _juris(n,d):
    if 'greek orthodox' in d or 'greek orthodox' in n:return'greek_orthodox'
    if 'orthodox church in america' in d or 'orthodox church in america' in n:return'oca'
    if 'antiochian orthodox' in d or 'antiochian orthodox' in n:return'antiochian'
    if 'coptic orthodox' in d or 'coptic orthodox' in n:return'coptic'
    if 'ethiopian orthodox' in d or 'ethiopian orthodox' in n:return'ethiopian'
    if 'romanian orthodox' in d or 'romanian orthodox' in n:return'romanian'
    if 'armenian' in d or 'armenian' in n:return'armenian'
    if 'ukrainian orthodox' in d or 'ukrainian orthodox' in n:return'ukrainian'
    if 'malankara' in d or 'malankara' in n or 'syrian orthodox' in n:return'malankara'
    if 'bulgarian orthodox' in d or 'bulgarian orthodox' in n:return'bulgarian'
    if 'serbian orthodox' in d or 'serbian orthodox' in n:return'serbian'
    if 'eastern orthodox' in d or 'eastern orthodox' in n:return'eastern_orthodox'
    if 'russian orthodox' in n or 'carpatho' in n:return'oca'
    return'orthodox_generic'

def core(n):
    n=n.lower().strip();n=re.sub(r'^the ','',n)
    for s in [' cemetery',' foundation',' trust',' inc',' llc',' school',' mission station chapel']:
        if s in n:n=n[:n.index(s)].strip()
    return n.strip()

def main():
    conn=sqlite3.connect(DB)
    conn.execute('PRAGMA journal_mode=WAL');conn.execute('PRAGMA synchronous=OFF');conn.execute('PRAGMA busy_timeout=30000')
    if 'entity_type' not in [r[1] for r in conn.execute('PRAGMA table_info(churches)')]:
        conn.execute('ALTER TABLE churches ADD COLUMN entity_type TEXT');conn.commit()
    print('Loading Orthodox records...')
    rows=conn.execute("""SELECT id,name,city,state,county_name,county_fips,denomination FROM churches
        WHERE (denomination LIKE '%orthodox%' OR denomination='Greek Orthodox Archdiocese of America'
               OR denomination='Armenian Apostolic Church' OR denomination LIKE '%coptic%'
               OR denomination LIKE '%ethiopian orthodox%' OR denomination LIKE '%antiochian orthodox%'
               OR denomination LIKE '%malankara%')
          AND denomination NOT IN ('Orthodox Presbyterian Church','Orthodox Union','Local Spiritual Assembly')""").fetchall()
    print(f'  {len(rows)} records')
    recs={};stats=defaultdict(int);cls=[]
    for r in rows:
        cid,nm,ct,st,cn,cf,dn=r;et=classify(nm,dn);stats[et]+=1;recs[cid]=(nm,ct,st,cn or '',cf or '',et,dn);cls.append((cid,et))
    for e,c in sorted(stats.items(),key=lambda x:-x[1]):print(f'  {e:25s}: {c:5d}')
    print('  Bulk updating entity_type...')
    conn.execute('CREATE TEMP TABLE _oc (id INTEGER PRIMARY KEY, entity_type TEXT)')
    conn.executemany('INSERT INTO _oc VALUES(?,?)',cls)
    conn.execute('UPDATE churches SET entity_type=(SELECT entity_type FROM _oc WHERE _oc.id=churches.id) WHERE id IN (SELECT id FROM _oc)')
    conn.execute('DROP TABLE _oc');conn.commit();print('  Done.')

    # --- Build parent maps in memory ---
    parent={}
    dio_by_jur_st=defaultdict(list)
    natl_by_jur={}
    for cid,(nm,ct,st,cn,cf,et,dn) in recs.items():
        jur=_juris(nm,dn)
        if et in ('diocese','national_body') and st:
            dio_by_jur_st[(jur,st.strip().upper())].append((cid,nm))
        if et=='national_body':
            natl_by_jur[jur]=cid

    print(f'  Found {sum(len(v) for v in dio_by_jur_st.values())} diocese/natl records across jurisdictions')
    print(f'  National bodies: {len(natl_by_jur)}')

    # Link parishes to diocese (same jurisdiction + state)
    for cid,(nm,ct,st,cn,cf,et,dn) in recs.items():
        if et not in ('parish','mission','chapel','monastery') or not st:continue
        jur=_juris(nm,dn)
        cands=dio_by_jur_st.get((jur,st.strip().upper()),[])
        if cands:parent[cid]=cands[0][0]

    # Link dioceses to national body (same jurisdiction)
    for cid,(nm,ct,st,cn,cf,et,dn) in recs.items():
        if et!='diocese' or cid in parent:continue
        jur=_juris(nm,dn)
        nid=natl_by_jur.get(jur)
        if nid and nid!=cid:parent[cid]=nid

    # Link associated to parish (same city)
    assoc={'school','foundation','cemetery','chapel','mission','monastery'}
    par_by_city=defaultdict(list)
    for cid,(nm,ct,st,cn,cf,et,dn) in recs.items():
        if et=='parish' and ct:par_by_city[(ct.strip().upper(),(st or '').strip().upper())].append((cid,nm))
    for cid,(nm,ct,st,cn,cf,et,dn) in recs.items():
        if et not in assoc or not ct or cid in parent:continue
        cands=par_by_city.get((ct.strip().upper(),(st or '').strip().upper()),[])
        c=core(nm)
        for pid,pn in cands:
            if c in core(pn) or core(pn) in c or c==core(pn):parent[cid]=pid;break

    # Bulk apply parent_church_id
    print(f'  Applying {len(parent)} parent links...')
    if parent:
        conn.execute('CREATE TEMP TABLE _op (id INTEGER PRIMARY KEY, parent_id INTEGER)')
        conn.executemany('INSERT INTO _op VALUES(?,?)',[(cid,pid) for cid,pid in parent.items()])
        conn.execute('UPDATE churches SET parent_church_id=(SELECT parent_id FROM _op WHERE _op.id=churches.id) WHERE id IN (SELECT id FROM _op)')
        conn.execute('DROP TABLE _op');conn.commit()

    # Summary
    print('\n=== Final hierarchy summary ===')
    for e,c in conn.execute("""SELECT entity_type,COUNT(*) FROM churches
        WHERE (denomination LIKE '%orthodox%' OR denomination='Greek Orthodox Archdiocese of America'
               OR denomination='Armenian Apostolic Church' OR denomination LIKE '%coptic%'
               OR denomination LIKE '%ethiopian orthodox%' OR denomination LIKE '%antiochian orthodox%'
               OR denomination LIKE '%malankara%')
          AND denomination NOT IN ('Orthodox Presbyterian Church','Orthodox Union','Local Spiritual Assembly')
        GROUP BY 1 ORDER BY 2 DESC""").fetchall():
        et=e or 'NULL'
        wp=conn.execute("""SELECT COUNT(*) FROM churches WHERE entity_type=?
          AND parent_church_id IS NOT NULL AND (denomination LIKE '%orthodox%'
               OR denomination='Greek Orthodox Archdiocese of America' OR denomination='Armenian Apostolic Church'
               OR denomination LIKE '%coptic%' OR denomination LIKE '%ethiopian orthodox%'
               OR denomination LIKE '%antiochian orthodox%' OR denomination LIKE '%malankara%')
          AND denomination NOT IN ('Orthodox Presbyterian Church','Orthodox Union','Local Spiritual Assembly')""",(e,)).fetchone()[0]
        print(f'  {et:25s}: {c:5d}  ({wp:5d} linked)')
    conn.close();print('\nDone.')

if __name__=='__main__':main()
