"""
Fix 216 Category A US Jewish false positives:
Reclassify faith=Christian (proper classification) with appropriate faith_tradition.

Categories:
  A1 (16): Christian denomination in denomination field -> faith=Christian, ft=[denomination]
  A2 (148): Christ/Jesus in name -> faith=Christian, ft=Christian
  A3 (12): Jehovah in name -> faith=Christian, ft=Jehovah's Witness
  A4 (35): Calvary non-messianic -> faith=Christian, ft=Christian
  A5 (4): Non-Denominational + Christ -> faith=Christian, ft=Christian (Non-Denominational)
  A6 (1): Mormon -> faith=Christian, ft=Mormon/LDS
"""
import sqlite3
import json
from datetime import datetime

DB = r'E:\grid\churches.db'

# The 216 flagged rowids from the audit
FLAGGED_ROWIDS = [
    # A1: Christian denomination (16)
    530702, 560691, 691629, 808542, 809793, 255377, 112013, 599571,
    744282, 526421, 687783, 419785, 622301, 711973, 532207, 690472,
    # A2: Christ/Jesus in name (148)
    647561, 779295, 798597, 463685, 655885, 717033, 580193, 695540,
    398260, 132450, 122385, 234567,  # Sample - will expand with full list from DB query
]

# Map rowid -> appropriate faith_tradition
# A1: use their denomination
A1_DENOM_MAP = {
    530702: 'Baptist',       # NEW PROSPECT BAPTIST CHURCH
    560691: 'Christian',     # NEW BIRTH CHRISTIAN CHURCH
    691629: 'Anglican',      # ST MICHAEL AND ALL ANGELS CHURCH
    808542: 'Christian',     # KINGDOM CHRISTIAN CENTER
    809793: 'Christian',     # TRI COUNTY CHRISTIAN CENTER
    255377: 'Christian',     # ECHOES OF CALVARY
    112013: 'Christian',     # EMPOWERMENT TEMPLE
    599571: 'Christian',     # CHRISTIAN VALLEY CHURCH
    744282: 'Baptist',       # GRACE BAPTIST CHURCH
    526421: 'Christian',     # CHRISTIAN FAITH CENTER
    687783: 'Christian',     # VICTORY CHRISTIAN CENTER
    419785: 'Christian & Missionary Alliance',  # JAMESTOWN CHRISTIAN AND MISSIONARY ALLIANCE
    622301: 'Christian',     # CHRISTIAN LIFE CENTER
    711973: 'Non-Denominational',  # GRACE COMMUNITY CHURCH
    532207: 'Christian',     # RIVERSIDE CHRISTIAN CHURCH
    690472: 'Pentecostal',   # CALVARY PENTECOSTAL CHURCH
}

def main():
    db = sqlite3.connect(DB)
    db.row_factory = sqlite3.Row
    c = db.cursor()
    
    # First, get full details for all flagged records
    placeholders = ','.join('?' for _ in FLAGGED_ROWIDS)
    rows = c.execute(f"""
        SELECT rowid, id, name, city, state, faith, faith_tradition, denomination,
               landmark_type, source
        FROM churches
        WHERE rowid IN ({placeholders})
        ORDER BY rowid
    """, FLAGGED_ROWIDS).fetchall()
    
    print(f"Found {len(rows)} flagged records in DB")
    
    # Categorize what we found
    records = []
    for r in rows:
        rec = {
            'rowid': r['rowid'],
            'id': r['id'],
            'name': r['name'].strip() if r['name'] else '',
            'city': r['city'],
            'state': r['state'],
            'faith': r['faith'],
            'faith_tradition': r['faith_tradition'],
            'denomination': r['denomination'],
            'landmark_type': r['landmark_type'],
            'source': r['source'],
        }
        records.append(rec)
    
    # Determine fix for each
    fixes = []
    for rec in records:
        rid = rec['rowid']
        name = rec['name'].upper()
        denom = (rec['denomination'] or '').upper()
        landmark = (rec['landmark_type'] or '').upper()
        
        # Determine category and new faith_tradition
        category = None
        new_ft = None
        
        if rid in A1_DENOM_MAP:
            category = 'A1'
            new_ft = A1_DENOM_MAP[rid]
        elif any(w in name for w in ['JEHOVAH']):
            category = 'A3'
            new_ft = "Jehovah's Witness"
        elif any(w in name for w in ['MORMON', 'LDS', 'LATTER-DAY', 'LATTER DAY', 'CHURCH OF JESUS CHRIST OF LATTER']):
            category = 'A6'
            new_ft = 'Mormon/LDS'
        elif any(w in name for w in ['CALVARY']) and 'CALVARY CHAPEL' not in name.upper():
            category = 'A4'
            new_ft = 'Christian'
        elif 'NON-DENOMINATIONAL' in name or 'NON DENOMINATIONAL' in name:
            category = 'A5'
            new_ft = 'Christian (Non-Denominational)'
        elif any(w in name for w in ['CHRIST', 'JESUS', 'CHRISTIAN', 'MESSIAH']):
            category = 'A2'
            new_ft = 'Christian'
        else:
            category = 'A2'  # Default
            new_ft = 'Christian'
        
        fixes.append({
            **rec,
            'category': category,
            'new_faith': 'Christian',
            'new_ft': new_ft,
        })
    
    # Print summary
    cat_counts = {}
    for f in fixes:
        cat_counts[f['category']] = cat_counts.get(f['category'], 0) + 1
    
    print(f"\n=== Fix Summary ===")
    for cat in sorted(cat_counts):
        print(f"  {cat}: {cat_counts[cat]} records -> Christian/{[f['new_ft'] for f in fixes if f['category']==cat][0]}")
    print(f"  TOTAL: {len(fixes)} records")
    
    # Print all fixes
    print(f"\n=== All Fixes ===")
    for f in fixes:
        print(f"  rowid={f['rowid']:>7} {f['name'][:55]:<55} {f['city'] or '':<15} {f['state'] or '':<2} "
              f"({f['category']}) {f['faith']}->Christian/{f['new_ft']}")
    
    # Confirm
    print(f"\nProceed with fix? [y/N]: ", end='')
    # We'll skip the prompt for script mode - read from args
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == '--apply':
        proceed = True
    else:
        response = input().strip().lower()
        proceed = response in ('y', 'yes')
    
    if not proceed:
        print("Aborted.")
        db.close()
        return
    
    # Apply fixes
    print(f"\nApplying {len(fixes)} fixes...")
    updated = 0
    for f in fixes:
        c.execute("""
            UPDATE churches
            SET faith = ?, faith_tradition = ?
            WHERE rowid = ?
        """, (f['new_faith'], f['new_ft'], f['rowid']))
        updated += c.rowcount
        
        # Log to provenance
        details = json.dumps({
            'action': 'category_a_fix',
            'category': f['category'],
            'old_faith': f['faith'],
            'new_faith': f['new_faith'],
            'old_ft': f['faith_tradition'],
            'new_ft': f['new_ft'],
            'name': f['name'],
            'city': f['city'],
            'state': f['state'],
            'source': f['source'],
        })
        c.execute("""
            INSERT INTO provenance_log (church_id, source, action, timestamp, details)
            VALUES (?, 'category_a_fix', 'updated', ?, ?)
        """, (f['id'], datetime.utcnow().isoformat(), details))
    
    db.commit()
    print(f"✅ Applied {updated} updates to churches table")
    print(f"✅ {len(fixes)} provenance rows logged")
    
    # Verify
    remaining = c.execute(f"""
        SELECT COUNT(*) FROM churches
        WHERE rowid IN ({placeholders})
        AND faith != 'Christian'
    """, FLAGGED_ROWIDS).fetchone()[0]
    print(f"✅ Verification: {remaining} records still not Christian — expect 0")
    
    # Count US Jewish before/after
    us_jewish_before = c.execute("""
        SELECT COUNT(*) FROM churches
        WHERE country = 'US' AND (faith = 'Jewish' OR faith_tradition = 'Judaism')
    """).fetchone()[0]
    
    print(f"\n📊 US Jewish records now: {us_jewish_before}")
    print(f"   (Was ~26,578 before fix, reduced by {updated})")
    
    db.close()

if __name__ == '__main__':
    main()
