"""
Classify the 306K overture_full + 23K IRS NULL-faith records.
Handles multilingual names (Spanish, French, Vietnamese, etc.)
"""
import sqlite3, datetime

DB = 'churches.db'
TS = datetime.datetime.now().isoformat()
conn = sqlite3.connect(DB, timeout=30)
c = conn.cursor()
total = 0

def tag(label, faith, tradition, where_clause):
    global total
    c.execute(f"UPDATE churches SET faith=?, faith_tradition=? WHERE (faith IS NULL OR faith='') AND ({where_clause})",
              (faith, tradition))
    if c.rowcount > 0:
        print(f"  {label}: {c.rowcount:,}")
        total += c.rowcount

# ═══════════════════════════════════════════════════════════════════════════════
# CHRISTIAN — English
# ═══════════════════════════════════════════════════════════════════════════════
print("=== Christian (English) ===")
tag("church","Christian","Christianity","LOWER(name) LIKE '%church%'")
tag("chapel","Christian","Christianity","LOWER(name) LIKE '%chapel%'")
tag("methodist","Christian","Christianity","LOWER(name) LIKE '%methodist%'")
tag("baptist","Christian","Christianity","LOWER(name) LIKE '%baptist%'")
tag("lutheran","Christian","Christianity","LOWER(name) LIKE '%lutheran%'")
tag("presbyterian","Christian","Christianity","LOWER(name) LIKE '%presbyterian%'")
tag("catholic","Christian","Christianity","LOWER(name) LIKE '%catholic%'")
tag("episcopal","Christian","Christianity","LOWER(name) LIKE '%episcopal%'")
tag("anglican","Christian","Christianity","LOWER(name) LIKE '%anglican%'")
tag("adventist","Christian","Christianity","LOWER(name) LIKE '%adventist%' OR LOWER(name) LIKE '%seventh-day%' OR LOWER(name) LIKE '%seventh day%'")
tag("nazarene","Christian","Christianity","LOWER(name) LIKE '%nazarene%'")
tag("pentecostal","Christian","Christianity","LOWER(name) LIKE '%pentecostal%' OR LOWER(name) LIKE '%pentecostes%'")
tag("evangelical/free","Christian","Christianity","LOWER(name) LIKE '%evangelical%' OR LOWER(name) LIKE '%evangelisch%' OR LOWER(name) LIKE '%evangelische%'")
tag("holiness","Christian","Christianity","LOWER(name) LIKE '%holiness%'")
tag("cogic","Christian","Christianity","LOWER(name) LIKE '%cogic%' OR LOWER(name) LIKE '%church of god in christ%'")
tag("mennonite","Christian","Christianity","LOWER(name) LIKE '%mennonite%'")
tag("salvation army","Christian","Christianity","LOWER(name) LIKE '%salvation army%'")
tag("christian/christ","Christian","Christianity","LOWER(name) LIKE '%christian%' OR LOWER(name) LIKE '% christ %' OR LOWER(name) LIKE '%christ %'")
tag("gospel","Christian","Christianity","LOWER(name) LIKE '%gospel%'")
tag("jesus","Christian","Christianity","LOWER(name) LIKE '%jesus%' OR LOWER(name) LIKE '%jesucristo%' OR LOWER(name) LIKE '%jesús%'")
tag("bible","Christian","Christianity","LOWER(name) LIKE '%bible%' OR LOWER(name) LIKE '%bíblic%' OR LOWER(name) LIKE '%scripture%'")
tag("ministries/ministry","Christian","Christianity","LOWER(name) LIKE '%ministr%'")
tag("worship","Christian","Christianity","LOWER(name) LIKE '%worship%'")
tag("fellowship","Christian","Christianity","LOWER(name) LIKE '%fellowship%'")
tag("saint/st.","Christian","Christianity","LOWER(name) LIKE '%saint%' OR LOWER(name) LIKE '%st. %' OR LOWER(name) LIKE '%st %'")
tag("cathedral/basilica","Christian","Christianity","LOWER(name) LIKE '%cathedral%' OR LOWER(name) LIKE '%basilica%' OR LOWER(name) LIKE '%basílica%' OR LOWER(name) LIKE '%catedral%'")
tag("parish","Christian","Christianity","LOWER(name) LIKE '%parish%' OR LOWER(name) LIKE '%parroquia%' OR LOWER(name) LIKE '%paroisse%'")
tag("united church","Christian","Christianity","LOWER(name) LIKE '%united church%' OR LOWER(name) LIKE '%united methodist%'")
tag("ucc","Christian","Christianity","LOWER(name) LIKE '% ucc%' OR LOWER(name) LIKE '%ucc %' OR LOWER(name) LIKE '%united church of christ%'")
tag("reformed","Christian","Christianity","LOWER(name) LIKE '%reformed%' OR LOWER(name) LIKE '%reformada%' OR LOWER(name) LIKE '%reformée%'")
tag("calvary","Christian","Christianity","LOWER(name) LIKE '%calvary%' OR LOWER(name) LIKE '%calvario%' OR LOWER(name) LIKE '%calvaire%'")
tag("grace","Christian","Christianity","LOWER(name) LIKE '%grace%' AND LOWER(name) NOT LIKE '%disgrace%'")
tag("faith","Christian","Christianity","LOWER(name) LIKE '%faith%' AND LOWER(name) NOT LIKE '%interfaith%'")
tag("god","Christian","Christianity","LOWER(name) LIKE '% of god%' OR LOWER(name) LIKE '%god %' OR LOWER(name) LIKE '%de dios%' OR LOWER(name) LIKE '%dieu%'")
tag("assembly","Christian","Christianity","LOWER(name) LIKE '%assembly of god%' OR LOWER(name) LIKE '%assemblies of god%' OR LOWER(name) LIKE '%asamblea%' OR LOWER(name) LIKE '%assemblée%'")
tag("trinity","Christian","Christianity","LOWER(name) LIKE '%trinity%' OR LOWER(name) LIKE '%trinidad%' OR LOWER(name) LIKE '%trinité%'")
tag("tabernacle","Christian","Christianity","LOWER(name) LIKE '%tabernacle%' OR LOWER(name) LIKE '%tabernáculo%' OR LOWER(name) LIKE '%tabernaculo%'")
conn.commit()

# ═══════════════════════════════════════════════════════════════════════════════
# CHRISTIAN — Spanish / Portuguese
# ═══════════════════════════════════════════════════════════════════════════════
print("\n=== Christian (Spanish/Portuguese) ===")
tag("iglesia","Christian","Christianity","LOWER(name) LIKE '%iglesia%'")
tag("igreja","Christian","Christianity","LOWER(name) LIKE '%igreja%'")
tag("cristo/cristiana","Christian","Christianity","LOWER(name) LIKE '%cristo%' OR LOWER(name) LIKE '%cristiana%' OR LOWER(name) LIKE '%cristão%'")
tag("dios","Christian","Christianity","LOWER(name) LIKE '%dios%' OR LOWER(name) LIKE '%deus%'")
tag("evangelio/evangelho","Christian","Christianity","LOWER(name) LIKE '%evangelio%' OR LOWER(name) LIKE '%evangelho%' OR LOWER(name) LIKE '%evangélic%'")
tag("bautista","Christian","Christianity","LOWER(name) LIKE '%bautista%' OR LOWER(name) LIKE '%batista%'")
tag("comunidad","Christian","Christianity","LOWER(name) LIKE '%comunidad%cristiana%' OR LOWER(name) LIKE '%comunidade%'")
tag("adoracion","Christian","Christianity","LOWER(name) LIKE '%adoraci%' OR LOWER(name) LIKE '%adoração%'")
tag("templo","Christian","Christianity","LOWER(name) LIKE '%templo%' AND LOWER(name) NOT LIKE '%budista%'")
tag("sagrado/sagrada","Christian","Christianity","LOWER(name) LIKE '%sagrado%' OR LOWER(name) LIKE '%sagrada%'")
tag("santuario","Christian","Christianity","LOWER(name) LIKE '%santuario%' OR LOWER(name) LIKE '%santuário%'")
tag("aleluya/aleluia","Christian","Christianity","LOWER(name) LIKE '%alelu%'")
tag("misericordia","Christian","Christianity","LOWER(name) LIKE '%misericordia%' OR LOWER(name) LIKE '%misericórdia%'")
tag("espiritu/espirito","Christian","Christianity","LOWER(name) LIKE '%espíritu%santo%' OR LOWER(name) LIKE '%espirito%santo%'")
tag("santa cena","Christian","Christianity","LOWER(name) LIKE '%santa cena%' OR LOWER(name) LIKE '%santa ceia%'")
conn.commit()

# ═══════════════════════════════════════════════════════════════════════════════
# CHRISTIAN — French
# ═══════════════════════════════════════════════════════════════════════════════
print("\n=== Christian (French) ===")
tag("église","Christian","Christianity","LOWER(name) LIKE '%église%' OR LOWER(name) LIKE '%eglise%'")
tag("chrétien","Christian","Christianity","LOWER(name) LIKE '%chrétien%' OR LOWER(name) LIKE '%chretien%'")
tag("dieu","Christian","Christianity","LOWER(name) LIKE '% dieu %' OR LOWER(name) LIKE '%de dieu%'")
tag("jésus-christ","Christian","Christianity","LOWER(name) LIKE '%jésus%' OR LOWER(name) LIKE '%jesus%'")
tag("saint-e","Christian","Christianity","LOWER(name) LIKE '%sainte%' OR LOWER(name) LIKE '%saint-%'")
tag("évangélique","Christian","Christianity","LOWER(name) LIKE '%évangélique%' OR LOWER(name) LIKE '%evangelique%'")
tag("missionnaire","Christian","Christianity","LOWER(name) LIKE '%missionnaire%' OR LOWER(name) LIKE '%mission%chrétienne%'")
tag("paroisse","Christian","Christianity","LOWER(name) LIKE '%paroisse%'")
tag("catholique","Christian","Christianity","LOWER(name) LIKE '%catholique%'")
tag("protestante","Christian","Christianity","LOWER(name) LIKE '%protestante%' OR LOWER(name) LIKE '%protestant%évangélique%'")
tag("baptiste","Christian","Christianity","LOWER(name) LIKE '%baptiste%'")
tag("luthérien","Christian","Christianity","LOWER(name) LIKE '%luthérien%' OR LOWER(name) LIKE '%lutherien%'")
tag("presbytérien","Christian","Christianity","LOWER(name) LIKE '%presbytérien%' OR LOWER(name) LIKE '%presbyterien%'")
tag("méthodiste","Christian","Christianity","LOWER(name) LIKE '%méthodiste%' OR LOWER(name) LIKE '%methodiste%'")
conn.commit()

# ═══════════════════════════════════════════════════════════════════════════════
# CHRISTIAN — German
# ═══════════════════════════════════════════════════════════════════════════════
print("\n=== Christian (German) ===")
tag("kirche","Christian","Christianity","LOWER(name) LIKE '%kirche%' OR LOWER(name) LIKE '%kirch%'")
tag("evangelisch","Christian","Christianity","LOWER(name) LIKE '%evangelisch%' OR LOWER(name) LIKE '%evangelische%' OR LOWER(name) LIKE '%evangelium%'")
tag("katholisch","Christian","Christianity","LOWER(name) LIKE '%katholisch%' OR LOWER(name) LIKE '%katholische%'")
tag("gemeinde","Christian","Christianity","LOWER(name) LIKE '%gemeinde%'")
tag("gottesdienst","Christian","Christianity","LOWER(name) LIKE '%gottesdienst%' OR LOWER(name) LIKE '%gotteshaus%'")
tag("christus","Christian","Christianity","LOWER(name) LIKE '%christus%'")
tag("pfarr","Christian","Christianity","LOWER(name) LIKE '%pfarr%'")
tag("kloster","Christian","Christianity","LOWER(name) LIKE '%kloster%'")
conn.commit()

# ═══════════════════════════════════════════════════════════════════════════════
# CHRISTIAN — Other languages
# ═══════════════════════════════════════════════════════════════════════════════
print("\n=== Christian (Other languages) ===")
tag("Dutch: kerk/gemeente","Christian","Christianity","LOWER(name) LIKE '%kerk%' OR LOWER(name) LIKE '%gemeente%' OR LOWER(name) LIKE '%gereformeerd%' OR LOWER(name) LIKE '%hervormd%'")
tag("Italian: chiesa","Christian","Christianity","LOWER(name) LIKE '%chiesa%' OR LOWER(name) LIKE '%cattolica%' OR LOWER(name) LIKE '%parrocchia%'")
tag("Polish: kościół","Christian","Christianity","LOWER(name) LIKE '%kościół%' OR LOWER(name) LIKE '%kosciol%' OR LOWER(name) LIKE '%parafia%'")
tag("Vietnamese: nhà thờ/thánh","Christian","Christianity","LOWER(name) LIKE '%nhà thờ%' OR LOWER(name) LIKE '%thánh%' OR LOWER(name) LIKE '%hoi thanh%' OR LOWER(name) LIKE '%hội thánh%' OR LOWER(name) LIKE '%tin lành%'")
tag("Korean: 교회","Christian","Christianity","LOWER(name) LIKE '%교회%' OR LOWER(name) LIKE '%성당%'")
tag("Chinese: 教会/教堂","Christian","Christianity","LOWER(name) LIKE '%教会%' OR LOWER(name) LIKE '%教堂%' OR LOWER(name) LIKE '%基督%'")
tag("Tagalog: simbahan","Christian","Christianity","LOWER(name) LIKE '%simbahan%' OR LOWER(name) LIKE '%iglesia ni cristo%'")
tag("Russian: церковь","Christian","Christianity","LOWER(name) LIKE '%церковь%' OR LOWER(name) LIKE '%церква%' OR LOWER(name) LIKE '%храм%' OR LOWER(name) LIKE '%собор%'")
tag("Nordic: kyrka/kirke","Christian","Christianity","LOWER(name) LIKE '%kyrka%' OR LOWER(name) LIKE '%kirke%' OR LOWER(name) LIKE '%kyrkje%' OR LOWER(name) LIKE '%församling%' OR LOWER(name) LIKE '%menighet%'")
conn.commit()

# ═══════════════════════════════════════════════════════════════════════════════
# NON-CHRISTIAN catch (rare in overture data but be safe)
# ═══════════════════════════════════════════════════════════════════════════════
print("\n=== Non-Christian safety checks ===")
tag("mosque/masjid","Islam","Islam","LOWER(name) LIKE '%mosque%' OR LOWER(name) LIKE '%masjid%' OR LOWER(name) LIKE '%mescit%' OR LOWER(name) LIKE '%mescidi%' OR LOWER(name) LIKE '%camii%' OR LOWER(name) LIKE '%islamic%' OR LOWER(name) LIKE '%muslim%'")
tag("synagogue","Jewish","Judaism","LOWER(name) LIKE '%synagogue%' OR LOWER(name) LIKE '%synagog%' OR LOWER(name) LIKE '%beit%knesset%' OR LOWER(name) LIKE '%shul%'")
tag("temple (non-Christian)","Hindu","Hinduism","LOWER(name) LIKE '%temple%' AND LOWER(name) NOT LIKE '%church%' AND LOWER(name) NOT LIKE '%christian%' AND LOWER(name) NOT LIKE '%gospel%' AND LOWER(name) NOT LIKE '%calvary%' AND LOWER(name) NOT LIKE '%worship%'")
tag("buddhist","Buddhist","Buddhism","LOWER(name) LIKE '%buddhist%' OR LOWER(name) LIKE '%buddha%' OR LOWER(name) LIKE '%wat %' OR LOWER(name) LIKE '%vihara%'")
tag("gurudwara","Sikh","Sikhism","LOWER(name) LIKE '%gurudwara%' OR LOWER(name) LIKE '%gurdwara%'")
tag("hindu","Hindu","Hinduism","LOWER(name) LIKE '%hindu%' OR LOWER(name) LIKE '%mandir%'")
conn.commit()

# ═══════════════════════════════════════════════════════════════════════════════
# CATCH-ALL: anything with Christian-sounding names → Christian
# ═══════════════════════════════════════════════════════════════════════════════
print("\n=== Catch-all Christian signals ===")
tag("Generic Christian signals","Christian","Christianity",
    "(LOWER(name) LIKE '%cross%' OR LOWER(name) LIKE '%cruz%' OR LOWER(name) LIKE '%croix%'"
    " OR LOWER(name) LIKE '%holy%' OR LOWER(name) LIKE '%santo%' OR LOWER(name) LIKE '%sanct%'"
    " OR LOWER(name) LIKE '%blessed%' OR LOWER(name) LIKE '%bendito%' OR LOWER(name) LIKE '%béni%'"
    " OR LOWER(name) LIKE '%redeemer%' OR LOWER(name) LIKE '%redentor%'"
    " OR LOWER(name) LIKE '%savior%' OR LOWER(name) LIKE '%salvador%' OR LOWER(name) LIKE '%sauveur%'"
    " OR LOWER(name) LIKE '%praise%' OR LOWER(name) LIKE '%alabanza%' OR LOWER(name) LIKE '%louange%'"
    " OR LOWER(name) LIKE '%resurrection%' OR LOWER(name) LIKE '%resurrección%'"
    " OR LOWER(name) LIKE '%messiah%' OR LOWER(name) LIKE '%mesías%'"
    " OR LOWER(name) LIKE '%apostolic%' OR LOWER(name) LIKE '%apostólic%'"
    " OR LOWER(name) LIKE '%prophetic%' OR LOWER(name) LIKE '%profético%'"
    " OR LOWER(name) LIKE '%zion%' OR LOWER(name) LIKE '%sion%' OR LOWER(name) LIKE '%sión%'"
    " OR LOWER(name) LIKE '%bethel%' OR LOWER(name) LIKE '%betel%' OR LOWER(name) LIKE '%béthel%'"
    " OR LOWER(name) LIKE '%ebenezer%' OR LOWER(name) LIKE '%ebenezer%'"
    " OR LOWER(name) LIKE '%shalom%' OR LOWER(name) LIKE '%hallelujah%' OR LOWER(name) LIKE '%aleluya%'"
    " OR LOWER(name) LIKE '%gloria%' OR LOWER(name) LIKE '%gloria%'"
    " OR LOWER(name) LIKE '%convent%' OR LOWER(name) LIKE '%convento%'"
    " OR LOWER(name) LIKE '%rectory%' OR LOWER(name) LIKE '%presbytery%'"
    ")")

conn.commit()

print(f"\n=== Total tagged: {total:,} ===")

# ── Final NULL faith count ──────────────────────────────────────────────────
c.execute("SELECT COUNT(*) FROM churches WHERE faith IS NULL OR faith=''")
print(f"Remaining NULL-faith: {c.fetchone()[0]:,}")

c.execute("SELECT source, COUNT(*) FROM churches WHERE faith IS NULL OR faith='' GROUP BY source ORDER BY COUNT(*) DESC LIMIT 10")
print("\nTop NULL sources remaining:")
for src, cnt in c.fetchall():
    print(f"  {str(src or 'NULL'):<50} {cnt:>10,}")

# Log
c.execute("""
    INSERT INTO provenance_log (source, script_name, started_at, completed_at,
        churches_updated, churches_inserted, fields_populated, status, notes)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
""", ('manual', '_classify_unclassified.py', TS, TS,
      total, 0, 'faith,faith_tradition', 'completed',
      f'Classified {total} NULL-faith records with multilingual patterns'))

conn.commit()
conn.close()
print("Done!")
