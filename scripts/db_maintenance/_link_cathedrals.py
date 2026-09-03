"""Link Catholic cathedrals to their parent dioceses in catholic_hierarchy.

Strategy:
1. Build a name→id map of all diocese/archdiocese entries in catholic_hierarchy
2. For each Catholic cathedral (churches.landmark_type='cathedral', legacy='Catholic'):
   a. Get its diocese from church_enrichment.diocese
   b. Match that to a hierarchy entry by name
   c. Set parent_id in catholic_hierarchy (or insert if not yet there)
3. Also fix orphaned cathedral entries already in hierarchy
"""

import sqlite3
import re
import sys
from datetime import datetime

CHUNK_SIZE = 500
DB = "churches.db"

def normalize(name):
    """Normalize a diocese name for matching."""
    if not name:
        return ""
    n = name.strip().lower()
    # Strip common prefixes
    for prefix in ["archdiocese of ", "diocese of ", "the "]:
        if n.startswith(prefix):
            n = n[len(prefix):]
    # Strip parenthetical suffixes like "{Sahara Occiental}"
    n = re.sub(r'\{[^}]*\}', '', n).strip()
    n = re.sub(r'\s+', ' ', n).strip()
    return n

def get_db():
    db = sqlite3.connect(DB)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA journal_mode=WAL")
    return db

def probe_name_formats(db):
    """Compare hierarchy names vs enrichment diocese values."""
    c = db.cursor()
    
    print("=" * 60)
    print("PHASE 0: Name format analysis")
    print("=" * 60)
    
    # Sample hierarchy names
    print("\n--- Hierarchy diocese/archdiocese names (sample 20) ---")
    c.execute("""
        SELECT name FROM catholic_hierarchy 
        WHERE cath_type IN ('diocese','archdiocese')
        ORDER BY name LIMIT 20
    """)
    for r in c.fetchall():
        print(f"  HIER: {r[0]}")
    
    # Sample enrichment diocese values from cathedrals
    print("\n--- Enrichment diocese values from Catholic cathedrals (sample 20) ---")
    c.execute("""
        SELECT DISTINCT e.diocese FROM churches ch
        JOIN church_enrichment e ON e.church_id = ch.id
        WHERE ch.landmark_type = 'cathedral' 
        AND ch.legacy = 'Catholic'
        AND e.diocese IS NOT NULL AND e.diocese != ''
        LIMIT 20
    """)
    for r in c.fetchall():
        print(f"  ENRICH: {r[0]}")
    
    # Test match rates
    print("\n--- Testing match rates ---")
    
    # Build hierarchy name map
    c.execute("SELECT id, name FROM catholic_hierarchy WHERE cath_type IN ('diocese','archdiocese')")
    hier_map = {}  # normalized -> (id, original_name)
    for r in c.fetchall():
        key = normalize(r["name"])
        if key:
            hier_map[key] = (r["id"], r["name"])
    
    print(f"  Hierarchy entries (diocese/archdiocese): {len(hier_map)}")
    
    # Get enrichment values
    c.execute("""
        SELECT DISTINCT e.diocese FROM churches ch
        JOIN church_enrichment e ON e.church_id = ch.id
        WHERE ch.landmark_type = 'cathedral' 
        AND ch.legacy = 'Catholic'
        AND e.diocese IS NOT NULL AND e.diocese != ''
    """)
    enrich_vals = [r[0] for r in c.fetchall()]
    print(f"  Distinct enrichment.diocese values: {len(enrich_vals)}")
    
    matched = 0
    unmatched = []
    for val in enrich_vals:
        key = normalize(val)
        if key in hier_map:
            matched += 1
        else:
            unmatched.append(val)
    
    print(f"  Exact match (after normalize): {matched}/{len(enrich_vals)}")
    if unmatched:
        print(f"\n  Unmatched enrichment values (first 20):")
        for v in unmatched[:20]:
            print(f"    '{v}' -> normalized='{normalize(v)}'")

def link_cathedrals_in_hierarchy(db):
    """Fix orphaned cathedral entries already in hierarchy - link to parent diocese."""
    c = db.cursor()
    
    print("\n" + "=" * 60)
    print("PHASE 1: Link orphaned cathedral entries already in hierarchy")
    print("=" * 60)
    
    # Build hierarchy name map
    c.execute("SELECT id, name FROM catholic_hierarchy WHERE cath_type IN ('diocese','archdiocese')")
    hier_map = {}  # normalized -> (id, name)
    for r in c.fetchall():
        key = normalize(r["name"])
        if key:
            hier_map[key] = (r["id"], r["name"])
    
    print(f"  Hierarchy diocese/archdiocese entries: {len(hier_map)}")
    
    # Get orphaned cathedral entries (in hierarchy, cath_type='cathedral', parent_id IS NULL)
    c.execute("""
        SELECT ch.id, ch.name, ch.church_id, ch.city, ch.country
        FROM catholic_hierarchy ch
        WHERE ch.cath_type = 'cathedral'
        AND ch.parent_id IS NULL
    """)
    orphans = [dict(r) for r in c.fetchall()]
    print(f"  Orphaned cathedral entries in hierarchy: {len(orphans)}")
    
    # For each orphan, get the church's enrichment.diocese
    linked = 0
    no_diocese = 0
    no_match = 0
    updates = []
    
    for o in orphans:
        church_id = o["church_id"]
        if church_id is None:
            no_diocese += 1
            continue
        
        c.execute("SELECT diocese FROM church_enrichment WHERE church_id = ?", (church_id,))
        row = c.fetchone()
        if row is None or not row[0]:
            no_diocese += 1
            continue
        
        diocese_val = row[0]
        key = normalize(diocese_val)
        
        if key in hier_map:
            parent_id, parent_name = hier_map[key]
            updates.append((parent_id, "diocese" if "archdiocese" not in parent_name.lower() else "archdiocese", 
                           parent_name, o["id"], o["name"]))
            linked += 1
        else:
            no_match += 1
    
    print(f"  Can link: {linked}")
    print(f"  No enrichment.diocese: {no_diocese}")
    print(f"  No hierarchy match: {no_match}")
    
    # Apply updates
    if updates:
        print(f"\n  Applying {len(updates)} parent_id updates...")
        db.execute("BEGIN TRANSACTION")
        for parent_id, ptype, pname, cat_id, cat_name in updates:
            db.execute("""
                UPDATE catholic_hierarchy 
                SET parent_id = ?, parent_cath_type = ?, relationship = 'seat_of'
                WHERE id = ?
            """, (parent_id, ptype, cat_id))
        db.commit()
        print(f"  ✅ {len(updates)} cathedral entries linked to parent diocese")
    
    # Show sample
    if updates:
        print("\n  Sample links:")
        for parent_id, ptype, pname, cat_id, cat_name in updates[:10]:
            print(f"    '{cat_name[:40]:40s}' → '{pname[:40]:40s}' ({ptype})")
    
    return linked

def insert_cathedrals_not_in_hierarchy(db):
    """Insert Catholic cathedrals from churches table into hierarchy under their diocese."""
    c = db.cursor()
    
    print("\n" + "=" * 60)
    print("PHASE 2: Insert Catholic cathedrals not yet in hierarchy")
    print("=" * 60)
    
    # Build hierarchy name map
    c.execute("SELECT id, name FROM catholic_hierarchy WHERE cath_type IN ('diocese','archdiocese')")
    hier_map = {}
    for r in c.fetchall():
        key = normalize(r["name"])
        if key:
            hier_map[key] = (r["id"], r["name"])
    
    print(f"  Hierarchy diocese/archdiocese entries: {len(hier_map)}")
    
    # Build set of church_ids already in hierarchy as cathedrals
    c.execute("SELECT church_id FROM catholic_hierarchy WHERE cath_type = 'cathedral' AND church_id IS NOT NULL")
    existing_church_ids = set(r[0] for r in c.fetchall())
    print(f"  Church IDs already in hierarchy as cathedrals: {len(existing_church_ids)}")
    
    # Get Catholic cathedrals NOT in hierarchy
    c.execute("""
        SELECT ch.id, ch.name, ch.city, ch.state, ch.country, ch.lat, ch.lon,
               ch.faith, ch.legacy, ch.tradition, ch.denomination, ch.source
        FROM churches ch
        WHERE ch.landmark_type = 'cathedral'
        AND ch.legacy = 'Catholic'
        ORDER BY ch.id
    """)
    all_catholic_cathedrals = [dict(r) for r in c.fetchall()]
    print(f"  Total Catholic cathedrals in churches: {len(all_catholic_cathedrals)}")
    
    to_insert = [ch for ch in all_catholic_cathedrals if ch["id"] not in existing_church_ids]
    print(f"  Catholic cathedrals NOT yet in hierarchy: {len(to_insert)}")
    
    # For each, get enrichment.diocese and match
    inserted = 0
    no_diocese = 0
    no_match = 0
    batch = []
    
    for ch in to_insert:
        c.execute("SELECT diocese FROM church_enrichment WHERE church_id = ?", (ch["id"],))
        row = c.fetchone()
        diocese_val = row[0] if row and row[0] else None
        
        if not diocese_val:
            no_diocese += 1
            # Still insert as top-level cathedral with note
            batch.append((ch, None, None, "no_diocese_data"))
            continue
        
        key = normalize(diocese_val)
        if key in hier_map:
            parent_id, parent_name = hier_map[key]
            ptype = "archdiocese" if "archdiocese" in parent_name.lower() else "diocese"
            batch.append((ch, parent_id, ptype, parent_name))
            inserted += 1
        else:
            no_match += 1
            batch.append((ch, None, None, f"unmatched_diocese:{diocese_val}"))
    
    print(f"  Can insert with diocese link: {inserted}")
    print(f"  No enrichment.diocese: {no_diocese}")
    print(f"  No hierarchy match: {no_match}")
    
    # Insert in batches
    if batch:
        print(f"\n  Inserting {len(batch)} cathedral entries...")
        db.execute("BEGIN TRANSACTION")
        count = 0
        for ch, parent_id, parent_cath_type, note in batch:
            db.execute("""
                INSERT INTO catholic_hierarchy 
                    (parent_id, church_id, name, original_name, cath_type, cath_detail,
                     diocese, city, state, country, lat, lon,
                     parent_cath_type, relationship, notes)
                VALUES (?, ?, ?, ?, 'cathedral', 'bishop_seat',
                        ?, ?, ?, ?, ?, ?,
                        ?, 'seat_of', ?)
            """, (
                parent_id,
                ch["id"],
                ch["name"],
                ch["name"],
                note if isinstance(note, str) and note.startswith("unmatched") else (parent_cath_type if parent_cath_type else None),
                ch["city"] or "",
                ch["state"] or "",
                ch["country"] or "",
                ch["lat"],
                ch["lon"],
                parent_cath_type,
                f"auto-linked via enrichment.diocese={note}" if isinstance(note, str) and "unmatched" in note else f"auto-linked via enrichment.diocese"
            ))
            count += 1
            if count % CHUNK_SIZE == 0:
                db.commit()
                db.execute("BEGIN TRANSACTION")
        db.commit()
        print(f"  ✅ {len(batch)} cathedrals inserted into hierarchy")
    
    # Show sample
    linked_batch = [b for b in batch if b[1] is not None]
    if linked_batch:
        print("\n  Sample insertions:")
        for ch, pid, ptype, pname in linked_batch[:10]:
            print(f"    '{ch['name'][:40]:40s}' ({ch['city'] or '?'}, {ch['country'] or '?'}) → '{pname[:40] if pname else '?'}'")
    
    return inserted

def validate(db):
    """Check the results."""
    c = db.cursor()
    
    print("\n" + "=" * 60)
    print("VALIDATION")
    print("=" * 60)
    
    c.execute("SELECT COUNT(*) FROM catholic_hierarchy WHERE cath_type = 'cathedral'")
    print(f"  Total cathedral entries in hierarchy: {c.fetchone()[0]}")
    
    c.execute("SELECT COUNT(*) FROM catholic_hierarchy WHERE cath_type = 'cathedral' AND parent_id IS NOT NULL")
    print(f"  Cathedrals WITH parent diocese: {c.fetchone()[0]}")
    
    c.execute("SELECT COUNT(*) FROM catholic_hierarchy WHERE cath_type = 'cathedral' AND parent_id IS NULL")
    print(f"  Cathedrals STILL orphaned: {c.fetchone()[0]}")
    
    c.execute("""
        SELECT COUNT(DISTINCT parent_id) FROM catholic_hierarchy 
        WHERE cath_type = 'cathedral' AND parent_id IS NOT NULL
    """)
    print(f"  Unique dioceses now with a cathedral: {c.fetchone()[0]}")
    
    c.execute("""
        SELECT COUNT(*) FROM catholic_hierarchy 
        WHERE cath_type IN ('diocese','archdiocese')
        AND id IN (SELECT DISTINCT parent_id FROM catholic_hierarchy WHERE cath_type = 'cathedral')
    """)
    total_with = c.fetchone()[0]
    
    c.execute("SELECT COUNT(*) FROM catholic_hierarchy WHERE cath_type IN ('diocese','archdiocese')")
    total_dioceses = c.fetchone()[0]
    print(f"  Dioceses/archdioceses with a cathedral: {total_with}/{total_dioceses} ({100*total_with//total_dioceses if total_dioceses else 0}%)")
    
    # Relationship breakdown
    print("\n  Relationship types used:")
    c.execute("""
        SELECT relationship, COUNT(*) FROM catholic_hierarchy
        WHERE cath_type = 'cathedral'
        GROUP BY relationship
    """)
    for r in c.fetchall():
        print(f"    {r[0]}: {r[1]}")
    
    # Sample linked cathedrals
    print("\n  Sample linked cathedrals:")
    c.execute("""
        SELECT ch.name, ch.city, ch.country, pc.name as diocese_name, pc.cath_type as diocese_type
        FROM catholic_hierarchy ch
        JOIN catholic_hierarchy pc ON ch.parent_id = pc.id
        WHERE ch.cath_type = 'cathedral' AND ch.parent_id IS NOT NULL
        LIMIT 15
    """)
    for r in c.fetchall():
        print(f"    '{r[0][:40]:40s}' | {r[1] or '?'}, {r[2] or '?'} | → {r[3][:40]:40s} ({r[4]})")
    
    # Show orphaned cathedrals
    print("\n  Orphaned cathedrals (no parent):")
    c.execute("""
        SELECT name, city, country, church_id, notes
        FROM catholic_hierarchy
        WHERE cath_type = 'cathedral' AND parent_id IS NULL
        LIMIT 15
    """)
    for r in c.fetchall():
        print(f"    '{r[0][:45]:45s}' | {r[1] or '?'}, {r[2] or '?'} | notes={str(r[4])[:30] if r[4] else 'None'}")


if __name__ == "__main__":
    db = get_db()
    
    # Phase 0: Probe name formats
    probe_name_formats(db)
    
    # Ask user if matches look right before proceeding
    print("\n" + "-" * 60)
    print("Review the name matching above.")
    print("If it looks correct, re-run with --apply to apply changes.")
    print("-" * 60)
    
    if "--apply" in sys.argv:
        print("\n🔧 --apply flag detected. Proceeding with linking...\n")
        
        # Phase 1: Link orphaned cathedral entries
        linked = link_cathedrals_in_hierarchy(db)
        
        # Phase 2: Insert remaining cathedrals
        inserted = insert_cathedrals_not_in_hierarchy(db)
        
        # Validate
        validate(db)
        
        print("\n✅ Done! Provenance logged.")
    else:
        print("\nDry run only. Run with --apply to execute.")
    
    db.close()
