"""
Fast geocode + classify CRA churches.
Geocoding: pgeocode internal DataFrame -> dict lookup (1,653 Canadian FSAs).
Classification: name-based keyword matching.
"""
import sqlite3, time, pandas as pd, pgeocode

DB_PATH = "E:/grid/churches.db"
BATCH = 5000

def main():
    db = sqlite3.connect(DB_PATH)
    
    # Load geocode dict once
    nomi = pgeocode.Nominatim('ca')
    pc_df = nomi._data_frame
    geo_dict = {}
    for _, row in pc_df.iterrows():
        pc = str(row['postal_code']).strip().upper()
        lat, lon = row['latitude'], row['longitude']
        if pc and pd.notna(lat) and pd.notna(lon):
            geo_dict[pc] = (float(lat), float(lon))
    print(f"Loaded {len(geo_dict):,} FSA geocodes")
    
    # Step 1: Geocode
    ungeocoded = db.execute("""
        SELECT id, zip, city, state FROM churches 
        WHERE source IN ('cra_2018', 'cra_2011') 
          AND (latitude IS NULL OR latitude = 0)
    """).fetchall()
    
    print(f"Geocoding {len(ungeocoded):,} CRA churches...")
    gc_count = 0
    t0 = time.time()
    
    for i in range(0, len(ungeocoded), BATCH):
        batch = ungeocoded[i:i+BATCH]
        updates = []
        for cid, zip_code, city, state in batch:
            if not zip_code or not isinstance(zip_code, str):
                continue
            fsa = zip_code.strip().upper()[:3]
            ll = geo_dict.get(fsa)
            if ll:
                updates.append((ll[0], ll[1], zip_code, cid))
        
        if updates:
            db.executemany("""
                UPDATE churches SET latitude=?, longitude=?, 
                geocode_source='pgeocode_ca_fsa', geocode_last_attempt=datetime('now'),
                zip=?
                WHERE id=?
            """, updates)
            db.commit()
            gc_count += len(updates)
        
        if i % (BATCH*4) == 0:
            elapsed = time.time() - t0
            rate = gc_count / max(elapsed, 0.1)
            pct = 100 * gc_count / len(ungeocoded)
            print(f"  {gc_count:,}/{len(ungeocoded):,} ({pct:.0f}%) - {rate:.0f}/s")
    
    elapsed = time.time() - t0
    print(f"Geocoded {gc_count:,} in {elapsed:.0f}s")
    
    # Step 2: Classify
    print(f"\nClassifying CRA church names...")
    to_classify = db.execute("""
        SELECT id, name FROM churches
        WHERE source IN ('cra_2018', 'cra_2011')
          AND (family IS NULL OR family = '')
    """).fetchall()
    
    print(f"  {len(to_classify):,} to classify")
    cl_count = 0
    
    for i in range(0, len(to_classify), BATCH):
        batch = to_classify[i:i+BATCH]
        updates = []
        for cid, name in batch:
            if not name:
                continue
            family, subtradition, confidence = classify_name(name)
            if family:
                updates.append((family, subtradition, confidence, cid))
        
        if updates:
            db.executemany("""
                UPDATE churches SET family=?, subtradition=?, classification_source='cra_name_classifier',
                classification_timestamp=datetime('now'), classification_version='cra_name_v1'
                WHERE id=?
            """, updates)
            db.commit()
            cl_count += len(updates)
        
        if i % (BATCH*4) == 0:
            pct = 100 * cl_count / len(to_classify)
            print(f"  {cl_count:,}/{len(to_classify):,} ({pct:.0f}%)")
    
    print(f"Classified {cl_count:,}")
    
    # Summary
    print(f"\n--- Final CRA stats ---")
    for src in ('cra_2018', 'cra_2011'):
        t = db.execute(f"SELECT COUNT(*) FROM churches WHERE source='{src}'").fetchone()[0]
        g = db.execute(f"SELECT COUNT(*) FROM churches WHERE source='{src}' AND latitude IS NOT NULL AND latitude!=0").fetchone()[0]
        f = db.execute(f"SELECT COUNT(*) FROM churches WHERE source='{src}' AND family IS NOT NULL AND family!=''").fetchone()[0]
        print(f"  {src}: {t:,} total | {g:,} geocoded ({100*g/max(t,1):.0f}%) | {f:,} classified ({100*f/max(t,1):.0f}%)")
    
    print(f"\n  Family breakdown (CRA 2018):")
    for fam, cnt in db.execute("SELECT family, COUNT(*) FROM churches WHERE source='cra_2018' AND family IS NOT NULL GROUP BY family ORDER BY COUNT(*) DESC LIMIT 15"):
        print(f"    {fam}: {cnt:,}")
    
    db.close()


def classify_name(name):
    n = name.upper().strip() if name else ""
    
    if any(k in n for k in ['CATHOLIC', 'CATHOLIQUE', 'DIOCESE', 'ARCHDIOCESE',
            'PAROISSE ', 'PARISH ', 'ARCHIEPISCOPAL', 'NOTRE DAME', 'SACRED HEART',
            'SACRE COEUR', 'HOLY CROSS', 'SAINTE CROIX', 'OUR LADY OF ',
            'ST. ', ' SAINT ', 'STE. ', ' SAINTE ', 'ST-', 'SAINT-', 'STE-', ' ABBEY']):
        if any(k in n for k in ['UKRAINIAN', 'UKRAINIEN']):
            return ('Catholic', 'Ukrainian Catholic', 0.8)
        if 'MARONITE' in n:
            return ('Catholic', 'Maronite', 0.8)
        return ('Catholic', 'Roman Catholic', 0.75)
    
    if any(k in n for k in ['ANGLICAN', 'ANGLICANE']):
        return ('Protestant', 'Anglican', 0.9)
    if any(k in n for k in ['UNITED CHURCH', 'EGLISE UNIE', 'PASTORAL CHARGE']):
        return ('Protestant', 'United Church of Canada', 0.85)
    if 'PRESBYTERIAN' in n or 'PRESBYTERIEN' in n:
        return ('Protestant', 'Presbyterian', 0.9)
    if 'LUTHERAN' in n or 'LUTHERIEN' in n:
        return ('Protestant', 'Lutheran', 0.9)
    if any(k in n for k in ['BAPTIST', 'BAPTISTE']):
        return ('Protestant', 'Baptist', 0.9)
    if any(k in n for k in ['PENTECOSTAL', 'PENTECOTE', 'PENTECÔTE', 'ASSEMBLY OF GOD',
            'ASSEMBLEE DE DIEU', 'FOURSQUARE']):
        return ('Protestant', 'Pentecostal', 0.85)
    if any(k in n for k in ['EVANGELICAL', 'EVANGELIQUE', 'EVANGÉLIQUE']):
        return ('Protestant', 'Evangelical', 0.8)
    if 'MENNONITE' in n:
        return ('Protestant', 'Mennonite', 0.9)
    if any(k in n for k in ['REFORMED', 'REFORMEE', 'REFORMÉE']):
        return ('Protestant', 'Reformed', 0.8)
    if 'METHODIST' in n or 'METHODISTE' in n:
        return ('Protestant', 'Methodist', 0.9)
    if 'SALVATION ARMY' in n or 'ARMEE DU SALUT' in n:
        return ('Protestant', 'Salvation Army', 0.95)
    if any(k in n for k in ["JEHOVAH", "TÉMOINS DE JÉHOVAH", "TEMOINS DE JEHOVAH",
            "WATCHTOWER", "WATCH TOWER"]):
        return ("Christian", "Jehovah's Witnesses", 0.95)
    if any(k in n for k in ['LDS ', 'MORMON', 'LATTER DAY', 'LATTER-DAY']):
        return ('Christian', 'Latter-day Saints', 0.9)
    if 'SEVENTH' in n and 'ADVENTIST' in n:
        return ('Protestant', 'Seventh-day Adventist', 0.9)
    if 'CHRISTIAN AND MISSIONARY' in n or 'ALLIANCE CHRETIENNE' in n:
        return ('Protestant', 'Christian and Missionary Alliance', 0.9)
    if any(k in n for k in ['ORTHODOX', 'ORTHODOXE', 'COPTIC', 'COPTE']):
        if 'GREEK' in n: return ('Orthodox', 'Greek Orthodox', 0.85)
        if 'RUSSIAN' in n or 'RUSSE' in n: return ('Orthodox', 'Russian Orthodox', 0.85)
        if 'UKRAINIAN' in n: return ('Orthodox', 'Ukrainian Orthodox', 0.85)
        return ('Orthodox', 'Eastern Orthodox', 0.8)
    if any(k in n for k in ['MUSLIM', 'ISLAMIC', 'ISLAMIQUE', 'MOSQUE', 'MOSQUEE',
            'MASJID', 'AHMADIYYA']):
        return ('Muslim', 'Sunni', 0.75)
    if any(k in n for k in ['SYNAGOGUE', 'JEWISH', 'JUIF', 'JUIVE', 'BETH ISRAEL',
            'BETH EL', 'BNAI', "B'NAI", 'HEBREW', 'SHOLEM', 'SHALOM']):
        return ('Jewish', 'Jewish', 0.8)
    if any(k in n for k in ['BUDDHIST', 'BOUDDHISTE', 'BOUDDHIQUE']):
        return ('Buddhist', 'Buddhist', 0.85)
    if 'HINDU' in n:
        return ('Hindu', 'Hindu', 0.85)
    if any(k in n for k in ['SIKH', 'GURDWARA', 'KHALSA']):
        return ('Sikh', 'Sikh', 0.85)
    if 'BAHA' in n:
        return ('Other', "Baha'i", 0.9)
    if any(k in n for k in ['CHURCH', 'EGLISE', 'ÉGLISE', 'CHAPEL', 'CHAPELLE',
            'CHRISTIAN', 'CHRETIEN', 'CHRÉTIEN', 'MINISTRY', 'MINISTERE',
            'MINISTÈRE', 'GOSPEL', 'FELLOWSHIP', 'COMMUNAUTE CHRETIENNE',
            'ASSEMBLEE CHRETIENNE', 'CONGREGATION', 'CONGRÉGATION',
            'TABERNACLE', 'SANCTUARY', 'SANCTUAIRE']):
        return ('Christian', 'Christian', 0.5)
    
    return (None, None, 0)


if __name__ == '__main__':
    main()
