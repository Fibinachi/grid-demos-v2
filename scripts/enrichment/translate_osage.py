"""
Backfill name_original (Simplified Chinese) and translate addresses
for OSAGE-China entries using pypinyin + admin unit substitution.

OSAGE-HK entries already have English addresses, so this targets China only.
"""
import csv, sqlite3, os, sys, re
sys.path.insert(0, 'E:/grid')
from pypinyin import pinyin, Style

DB = 'E:/grid/churches.db'
CSV_PATH = 'E:/grid/data/osage/china/bundle/CSVdata/data_ReligiousSiteBase.csv'
CHUNK = 1000

# Chinese admin unit → English
ADMIN_MAP = {
    '省': ' Province',
    '市': ' City',
    '区': ' District',
    '县': ' County',
    '镇': ' Town',
    '乡': ' Township',
    '村': ' Village',
    '街': ' Street',
    '路': ' Road',
    '号': '',
    '大道': ' Avenue',
    '胡同': ' Alley',
    '弄': ' Lane',
    '大厦': ' Building',
    '楼': ' Building',
    '自治区': ' Autonomous Region',
    '自治州': ' Autonomous Prefecture',
    '自治县': ' Autonomous County',
    '开发区': ' Development Zone',
    '管委会': ' Management Committee',
    '街道办事处': ' Subdistrict Office',
    '地区': ' Prefecture',
    '中国': '',
    '社区': ' Community',
    '小区': ' Complex',
    '组': ' Group',
    '队': ' Team',
    '甲': 'A',
    '乙': 'B',
    '丙': 'C',
    '丁': 'D',
}

def translate_address(chinese_addr):
    """Convert Chinese address to English-readable pinyin + admin units."""
    if not chinese_addr:
        return ''
    
    # Get pinyin for each character
    py_chars = pinyin(chinese_addr, style=Style.TONE)
    
    result = []
    i = 0
    while i < len(chinese_addr):
        char = chinese_addr[i]
        
        # Check multi-char admin units (longest match first)
        matched = False
        for length in [6, 5, 4, 3, 2, 1]:
            if i + length <= len(chinese_addr):
                seg = chinese_addr[i:i+length]
                if seg in ADMIN_MAP:
                    eng = ADMIN_MAP[seg]
                    if eng:
                        result.append(eng)
                    i += length
                    matched = True
                    break
        
        if not matched:
            # Use pinyin
            py = py_chars[i][0] if i < len(py_chars) else char
            # Strip tone numbers for readability
            py_clean = re.sub(r'\d', '', py)
            # Capitalize first letter
            if py_clean:
                result.append(py_clean.capitalize())
            i += 1
    
    # Join and clean up
    text = ' '.join(result)
    # Remove double spaces and trailing/leading
    text = re.sub(r'\s+', ' ', text).strip()
    # Remove space before comma
    text = re.sub(r'\s+,', ',', text)
    
    return text


def main():
    print("=" * 60)
    print("OSAGE TRANSLATION & NAME BACKFILL")
    print("=" * 60)
    
    db = sqlite3.connect(DB)
    db.execute("PRAGMA synchronous=NORMAL")
    db.execute("PRAGMA journal_mode=WAL")
    
    # ── Step 1: Build CSV name map ──
    print("\nStep 1: Loading Chinese names from CSV...")
    name_map = {}  # English name → Simplified Chinese name
    with open(CSV_PATH, encoding='utf-8') as f:
        for row in csv.DictReader(f):
            ename = (row.get('E_name', '') or '').strip()
            sname = (row.get('S_name', '') or '').strip()
            if ename and sname:
                name_map[ename] = sname
    print(f"  {len(name_map):,} name mappings loaded")
    
    # ── Step 2: Get all OSAGE China entries ──
    print("\nStep 2: Loading OSAGE entries from DB...")
    rows = db.execute(
        "SELECT id, name, address FROM churches WHERE source='osage_china'"
    ).fetchall()
    print(f"  {len(rows):,} entries")
    
    # ── Step 3: Backfill name_original ──
    print("\nStep 3: Backfilling name_original...")
    name_updates = []
    for row in rows:
        cid, ename = row[0], row[1]
        sname = name_map.get(ename)
        if sname:
            name_updates.append((sname, cid))
    
    batch = []
    for sname, cid in name_updates:
        batch.append((sname, cid))
        if len(batch) >= CHUNK:
            db.executemany("UPDATE churches SET name_original=? WHERE id=?", batch)
            db.commit()
            batch = []
    if batch:
        db.executemany("UPDATE churches SET name_original=? WHERE id=?", batch)
        db.commit()
    print(f"  {len(name_updates):,} name_original backfilled")
    
    # ── Step 4: Translate addresses ──
    print("\nStep 4: Translating addresses (pypinyin)...")
    translated = 0
    batch_updates = []
    
    for i, row in enumerate(rows):
        cid, addr = row[0], row[2]
        if not addr:
            continue
        
        eng_addr = translate_address(addr)
        batch_updates.append((eng_addr, cid))
        translated += 1
        
        if len(batch_updates) >= CHUNK:
            db.executemany(
                "UPDATE churches SET address=? WHERE id=?",
                batch_updates
            )
            db.commit()
            pct = min(translated / len(rows) * 100, 100)
            print(f"\r  {pct:.0f}%  {translated:,}/{len(rows):,}", end='', flush=True)
            batch_updates = []
    
    if batch_updates:
        db.executemany(
            "UPDATE churches SET address=? WHERE id=?",
            batch_updates
        )
        db.commit()
    
    print(f"\n  {translated:,} addresses translated")
    
    # ── Step 5: Verify ──
    print("\nStep 5: Verification...")
    
    # Sample
    samples = db.execute(
        "SELECT name, name_original, address FROM churches WHERE source='osage_china' LIMIT 8"
    ).fetchall()
    print("\nSample entries:")
    for r in samples:
        print(f"  EN: {r[0][:50]}")
        if r[1]:
            print(f"  ZH: {r[1][:50]}")
        print(f"  AD: {r[2][:80]}")
        print()
    
    # Coverage
    total = db.execute(
        "SELECT COUNT(*) FROM churches WHERE source='osage_china'"
    ).fetchone()[0]
    has_orig = db.execute(
        "SELECT COUNT(*) FROM churches WHERE source='osage_china' AND name_original IS NOT NULL AND name_original!=''"
    ).fetchone()[0]
    print(f"name_original coverage: {has_orig:,} / {total:,} ({has_orig*100/total:.1f}%)")
    
    # Integrity
    r = db.execute("PRAGMA integrity_check").fetchone()
    print(f"Integrity: {r[0]}")
    
    db.close()
    print("\nDone.")


if __name__ == '__main__':
    main()
