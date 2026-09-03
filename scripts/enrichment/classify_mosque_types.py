"""
Classify global mosques by operational type from name patterns.

Operational types (in priority order):
  - congregational_mosque : Jami/Juma/Grand/Jama — open daily, all 5 prayers + Friday khutbah
  - prayer_room           : Musalla/Surau/Langgar/Mescid — limited hours, may not have Friday
  - school_mosque         : Madrasa-based — school hours + prayer times
  - sufi_lodge            : Dargah/Zawiya/Tekke — irregular hours, Sufi gathering days
  - shia_congregation     : Imambargah/Hussainia — Shia, Muharram-focused schedule
  - islamic_center        : Islamic Center/Markaz — extended hours, community programs
  - turkish_cami          : Turkish Camii — standard mosque, usually congregational
  - generic_masjid        : Named "Masjid" — standard mosque, unknown if Jami
  - generic_mosque        : Named "Mosque" or variant — standard mosque
  - other                 : Doesn't match any pattern

The name itself encodes operational information:
  "Jami Masjid" = congregational, open for Friday prayers
  "Musalla" = small prayer room, limited hours  
  "Dargah" = Sufi shrine, specific gathering days
  "Imambargah" = Shia congregation hall, Muharram schedule
"""
import sqlite3, re, sys
from collections import Counter

DB = 'churches.db'

def classify_mosque(name):
    """Classify a mosque name into operational type."""
    if not name:
        return None
    
    upper = name.upper()
    
    # === Priority 1: Congregational (Jami/Juma/Grand/Jama) ===
    # "Jami Masjid" = جامع مسجد = congregational mosque with Friday prayers
    # "Juma/Jumma Masjid" = Friday mosque
    # "Grand Mosque" = main congregational mosque
    # "Jama Masjid" = variant of Jami (South Asia)
    # "Great Mosque" = translation of Jami
    # Turkish: "Ulu Camii" = Grand Mosque
    if (re.search(r'\bJAMI[\'\s]', upper) or re.search(r'\bJAMEK\b', upper)
        or re.search(r'\bJUMA\b', upper) or re.search(r'\bJUMMA\b', upper)
        or re.search(r'\bJUMU[\' ]AH\b', upper) or re.search(r'\bJUM\'AH\b', upper)
        or re.search(r'\bFRIDAY\b', upper)
        or re.search(r'\bGRAND\b', upper)
        or re.search(r'\bGREAT\b', upper)
        or re.search(r'\bULU\b', upper)  # Turkish: Ulu Camii = Grand Mosque
        or re.search(r'\bJAMA[\'\s]', upper)  # Jama Masjid
        or re.search(r'\bCAMI[-\s]I\s*KEBIR\b', upper)  # Turkish: Camii Kebir = Great Mosque
        or re.search(r'\bBUYUK\b', upper)):  # Turkish: Büyük Camii = Great Mosque
        return 'congregational_mosque'
    
    # === Priority 2: Prayer Room (Musalla/Surau/Langgar/Mescid) ===
    # Musalla = مصلى = prayer space, usually smaller, may not have minbar
    # Surau/Langgar = Indonesian/Malay small prayer house
    # Mescid = Turkish for small mosque (no Friday prayers)
    if (re.search(r'\bMUSALLA[HS]?\b', upper)
        or re.search(r'\bSURAU\b', upper)
        or re.search(r'\bLANGGAR\b', upper)
        or re.search(r'\bTAJUG\b', upper)
        or re.search(r'\bMESCID[I]?\b', upper)):  # Turkish mescid = small mosque
        return 'prayer_room'
    
    # === Priority 3: School Mosque (Madrasa) ===
    if re.search(r'\bMADRASA[SH]?\b', upper) or re.search(r'\bMADRASSA\b', upper):
        return 'school_mosque'
    
    # === Priority 4: Sufi Shrine/Lodge (Dargah/Zawiya/Tekke) ===
    # Dargah = درگاہ = Sufi shrine/tomb complex
    # Zawiya/Zawia = زاوية = Sufi lodge
    # Tekke = Turkish Sufi lodge
    # Khanqah = Persian Sufi lodge
    if (re.search(r'\bDARGA[HS]?\b', upper)
        or re.search(r'\bZAWIYA\b', upper) or re.search(r'\bZAWIA\b', upper) or re.search(r'\bZAUIA\b', upper)
        or re.search(r'\bTEKKE\b', upper) or re.search(r'\bTEKKEH\b', upper)
        or re.search(r'\bKHANQAH\b', upper) or re.search(r'\bKHANEGAH\b', upper)):
        return 'sufi_lodge'
    
    # === Priority 5: Shia Congregation (Imambargah/Hussainia) ===
    # Imambargah/Imambara = Shia congregation hall
    # Hussainia/Hussainiyah = Shia mourning hall
    # Matam = Shia mourning place
    # Ashura Khana = Shia mourning hall
    if (re.search(r'\bIMAMBARGAH\b', upper) or re.search(r'\bIMAMBARA\b', upper) or re.search(r'\bIMAMBADA\b', upper)
        or re.search(r'\bHUSSAINIA[HY]?\b', upper)
        or re.search(r'\bMATAM\b', upper)
        or re.search(r'\bASHUR\s*KHANA\b', upper)):
        return 'shia_congregation'
    
    # === Priority 6: Islamic Center / Markaz ===
    if re.search(r'\bISLAMIC\s+(CENTER|CENTRE)\b', upper):
        return 'islamic_center'
    if re.search(r'\bMARKAZ\b', upper):
        return 'islamic_center'
    
    # === Priority 7: Turkish Camii (standard mosque) ===
    # Camii = mosque in Turkish (from Arabic Jami')
    # Historically all camii are congregational, but we distinguish only Ulu/Büyük
    if re.search(r'\bCAMI[I]?\b', upper):
        return 'turkish_cami'
    
    # === Priority 8: Generic non-English mosque variants ===
    # Mesjid = Indonesian/Malay spelling of Masjid
    if re.search(r'\bMESJID\b', upper):
        return 'generic_masjid'
    
    # Mosquée (French), Moschee (German), Mezquita (Spanish), Moské (Scandinavian)
    if (re.search(r'\bMOSQU[EÉ]E\b', upper)  # French
        or re.search(r'\bMOSCHEE\b', upper)  # German
        or re.search(r'\bMEZQUITA\b', upper)  # Spanish
        or re.search(r'\bMOSK[EÉ]?\b', upper)  # Various (Dutch, Scandinavian, Russian)
        or re.search(r'\bMOSC[EÉ]?\b', upper)  # Additional variants
        or re.search(r'\bMECZET\b', upper)):  # Polish
        return 'generic_mosque'
    
    # === Priority 9: English mosque/masjid ===
    if re.search(r'\bMASJID\b', upper):
        return 'generic_masjid'
    
    if re.search(r'\bMOSQUE\b', upper):
        return 'generic_mosque'
    
    return 'other'


# --- SCHEDULE INFERENCE ---
# Based on mosque type, what are the typical operating patterns?
SCHEDULE_INFO = {
    'congregational_mosque': {
        'open_days': '7 days',
        'prayer_times': '5 daily + Friday khutbah',
        'typical_hours': 'Fajr to Isha (dawn to night)',
        'has_friday': True,
        'is_main_mosque': True,
    },
    'turkish_cami': {
        'open_days': '7 days',
        'prayer_times': '5 daily prayers',
        'typical_hours': 'Fajr to Isha',
        'has_friday': True,  # Most Turkish camii are congregational
        'is_main_mosque': True,
    },
    'generic_masjid': {
        'open_days': 'Varies (5-7 days)',
        'prayer_times': '5 daily prayers (may or may not have Friday)',
        'typical_hours': 'Prayer times only or extended',
        'has_friday': 'unknown',
        'is_main_mosque': False,
    },
    'generic_mosque': {
        'open_days': 'Varies (5-7 days)',
        'prayer_times': '5 daily prayers (may or may not have Friday)',
        'typical_hours': 'Prayer times only or extended',
        'has_friday': 'unknown',
        'is_main_mosque': False,
    },
    'islamic_center': {
        'open_days': '7 days',
        'prayer_times': '5 daily + Friday + community programs',
        'typical_hours': 'Extended (often 9am-9pm or longer)',
        'has_friday': True,
        'is_main_mosque': True,
    },
    'prayer_room': {
        'open_days': 'Varies (often limited)',
        'prayer_times': 'Limited (may not have all 5 daily)',
        'typical_hours': 'Specific prayer times only',
        'has_friday': False,
        'is_main_mosque': False,
    },
    'school_mosque': {
        'open_days': 'School days',
        'prayer_times': 'School schedule + prayers',
        'typical_hours': 'School hours',
        'has_friday': 'varies',
        'is_main_mosque': False,
    },
    'sufi_lodge': {
        'open_days': 'Varies (specific gathering days)',
        'prayer_times': 'Sufi gatherings (dhikr, hadra)',
        'typical_hours': 'Varies, often Thursday evening + Friday',
        'has_friday': 'varies',
        'is_main_mosque': False,
    },
    'shia_congregation': {
        'open_days': 'Varies (Muharram peak)',
        'prayer_times': 'Shia prayer times + majlis',
        'typical_hours': 'Event-based (Thursday evenings, Muharram daily)',
        'has_friday': 'varies',
        'is_main_mosque': False,
    },
}

def main():
    db = sqlite3.connect(DB)
    db.execute("PRAGMA journal_mode=WAL")
    cur = db.cursor()
    
    # Check if column exists
    cur.execute("PRAGMA table_info(churches)")
    cols = [r[1] for r in cur.fetchall()]
    
    if 'mosque_type' not in cols:
        print("Adding mosque_type column...")
        cur.execute("ALTER TABLE churches ADD COLUMN mosque_type TEXT")
        db.commit()
    else:
        # Reset existing classifications
        print("Clearing existing mosque_type values...")
        cur.execute("UPDATE churches SET mosque_type = NULL WHERE faith = 'Islam'")
        db.commit()
    
    # Get all Islamic entries
    cur.execute("SELECT id, name FROM churches WHERE faith = 'Islam' AND name IS NOT NULL AND name != ''")
    rows = cur.fetchall()
    print(f'Total Islam entries with names: {len(rows)}')
    
    # Classify and batch update
    type_counts = Counter()
    batch_size = 5000
    batch = []
    total_updated = 0
    
    for rid, name in rows:
        mtype = classify_mosque(name)
        if mtype:
            type_counts[mtype] += 1
            batch.append((mtype, rid))
        
        if len(batch) >= batch_size:
            cur.executemany("UPDATE churches SET mosque_type = ? WHERE id = ?", batch)
            db.commit()
            total_updated += len(batch)
            batch = []
    
    # Final batch
    if batch:
        cur.executemany("UPDATE churches SET mosque_type = ? WHERE id = ?", batch)
        db.commit()
        total_updated += len(batch)
    
    print(f'Classifiable: {total_updated} ({total_updated/len(rows)*100:.1f}%)')
    print(f'Updated: {total_updated} rows with mosque_type')
    
    print('\n=== Classification Distribution ===')
    for mtype, cnt in type_counts.most_common():
        pct = cnt / len(rows) * 100
        info = SCHEDULE_INFO.get(mtype, {})
        fri = info.get('has_friday', '?')
        hours = info.get('typical_hours', '?')
        print(f'  {mtype:25s}: {cnt:>8d} ({pct:5.1f}%) | Friday={str(fri):8s} | {hours}')
    
    # Show schedule summary
    print('\n=== Inferred Schedule by Type ===')
    for mtype in type_counts:
        info = SCHEDULE_INFO.get(mtype, {})
        if info:
            open_days = info.get('open_days', '?')
            prayers = info.get('prayer_times', '?')
            hours = info.get('typical_hours', '?')
            friday = info.get('has_friday', '?')
            print(f'\n  {mtype}:')
            print(f'    Open: {open_days}')
            print(f'    Prayers: {prayers}')
            print(f'    Hours: {hours}')
            print(f'    Friday khutbah: {friday}')
    
    # Show "other" samples for debugging
    other_count = type_counts.get('other', 0)
    if other_count > 0:
        print(f'\n=== "Other" category ({other_count} entries) ===')
        cur.execute("SELECT name, country FROM churches WHERE mosque_type = 'other' AND faith = 'Islam' LIMIT 30")
        for name, country in cur.fetchall():
            n = (name or '')[:80]
            print(f'  {n:80s} [{country}]')
    
    db.close()
    print('\nDone.')

if __name__ == '__main__':
    main()
