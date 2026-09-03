"""
Quick pass: link orphaned cathedrals to dioceses by name/city matching.

Strategy:
1. Extract a candidate city from the cathedral entry (name or city field)
2. Find a diocese/archdiocese in the same country whose name or city contains that candidate
3. For US: also try matching county_fips_5 via spatial join
4. Update parent_id in catholic_hierarchy
"""

import sqlite3
import re
import sys

DB_PATH = "churches.db"
CHUNK_SIZE = 100

# Cathedral names that don't contain their city — manual overrides
NAME_OVERRIDES = {
    # id: diocese_id or hierarchy_name
}

def extract_city_candidates(name, city_field):
    """Extract likely city names from a cathedral entry."""
    candidates = []
    
    # 1. Use the city field directly
    if city_field and city_field.strip():
        candidates.append(city_field.strip())
    
    if not name:
        return candidates
    
    # 2. Strip "Cathedral" and common prefixes
    cleaned = name
    cleaned = re.sub(r'\bCathedral\b', '', cleaned, flags=re.I)
    cleaned = re.sub(r'\b(Co-|Co )?Cathedral\b', '', cleaned, flags=re.I)
    cleaned = re.sub(r'\bBasilica\b', '', cleaned, flags=re.I)
    cleaned = re.sub(r'\bMetropolitan\b', '', cleaned, flags=re.I)
    cleaned = re.sub(r'\([^)]*\)', '', cleaned)  # Remove parentheticals
    cleaned = re.sub(r'\b(Church|of|the|Our|Lady|Saint|St\.|San|Santo|Santa|São|Don|Notre|Dame|Du|Dom|Mariä|Himmelfahrt)\b', '', cleaned, flags=re.I)
    cleaned = re.sub(r'[;,].*$', '', cleaned)  # Remove after comma/semicolon
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    
    # The remaining words might contain the city
    words = cleaned.split()
    for w in words:
        if len(w) > 3 and w[0].isupper():
            candidates.append(w)
    
    # 3. For names like "Palma Cathedral" — the word before Cathedral is the city
    m = re.match(r'^([A-Za-zÀ-ÖØ-öø-ÿ -]+)\s+Cathedral', name)
    if m:
        candidates.append(m.group(1).strip())
    
    # 4. For names like "Cathedral of La Plata" — the word after "of" is the city
    m = re.search(r'Cathedral\s+of\s+([A-Za-zÀ-ÖØ-öø-ÿ -]+)', name)
    if m:
        candidates.append(m.group(1).strip())
    
    return list(set(candidates))


def find_diocese(c, city_candidate, country, state):
    """Find a diocese matching a city candidate."""
    if not city_candidate:
        return None
    
    cc = city_candidate.strip().lower()
    
    # Direct: diocese name contains city
    c.execute("""
        SELECT id, name FROM catholic_hierarchy
        WHERE cath_type IN ('diocese','archdiocese')
        AND LOWER(country) = LOWER(?) AND LOWER(name) LIKE ?
        LIMIT 1
    """, (country, f'%{cc}%'))
    row = c.fetchone()
    if row:
        return row
    
    # Try without diacritics
    cc_simple = cc.replace('á','a').replace('é','e').replace('í','i').replace('ó','o').replace('ú','u')
    cc_simple = cc_simple.replace('à','a').replace('è','e').replace('ì','i').replace('ò','o').replace('ù','u')
    cc_simple = cc_simple.replace('ä','a').replace('ë','e').replace('ï','i').replace('ö','o').replace('ü','u')
    cc_simple = cc_simple.replace('ñ','n').replace('ç','c')
    if cc_simple != cc:
        c.execute("""
            SELECT id, name FROM catholic_hierarchy
            WHERE cath_type IN ('diocese','archdiocese')
            AND LOWER(country) = LOWER(?) AND LOWER(name) LIKE ?
            LIMIT 1
        """, (country, f'%{cc_simple}%'))
        row = c.fetchone()
        if row:
            return row
    
    return None


def main():
    dry_run = "--dry-run" in sys.argv
    
    db = sqlite3.connect(DB_PATH)
    c = db.cursor()
    
    # Get orphaned cathedrals
    c.execute("""
        SELECT ch.id, ch.name, ch.city, ch.state, ch.country, ch.lat, ch.lon
        FROM catholic_hierarchy ch
        WHERE ch.cath_type = 'cathedral' AND ch.parent_id IS NULL
        ORDER BY ch.country, ch.city
    """)
    orphans = c.fetchall()
    print(f"Orphaned cathedrals: {len(orphans)}")
    
    # For each, try to find a matching diocese
    matched = []
    unmatched = []
    
    for hid, name, city, state, country, lat, lon in orphans:
        if not country:
            unmatched.append((hid, name, "no country"))
            continue
        
        candidates = extract_city_candidates(name or "", city)
        
        found = None
        for cand in candidates:
            found = find_diocese(c, cand, country, state)
            if found:
                break
        
        if found:
            matched.append((hid, found[0], found[1], name, city, country))
        else:
            unmatched.append((hid, name, f"no match for {candidates[:3]}"))
    
    print(f"\nMatched: {len(matched)}")
    print(f"Unmatched: {len(unmatched)}")
    
    # Show matches
    print(f"\n=== MATCHES (first 30) ===")
    for hid, did, dname, cname, city, country in matched[:30]:
        print(f"  cathedral#{hid}: '{cname[:40]:40s}' → diocese#{did}: {dname[:40]}")
    
    # Show unmatched
    print(f"\n=== UNMATCHED (first 20) ===")
    for hid, name, reason in unmatched[:20]:
        print(f"  cathedral#{hid}: '{name[:50]:50s}' | {reason}")
    
    # Country breakdown of unmatched
    print(f"\n=== Unmatched by country ===")
    country_counts = {}
    for hid, name, reason in unmatched:
        # Extract country from name or use placeholder
        country = "??"
        for part in name.split(","):
            part = part.strip()
            if len(part) == 2 and part.isalpha():
                country = part
                break
        country_counts[country] = country_counts.get(country, 0) + 1
    for cname, cnt in sorted(country_counts.items(), key=lambda x: -x[1])[:15]:
        print(f"  {cname:30s} {cnt}")
    
    if dry_run:
        db.close()
        print("\n✅ Dry run complete. Omit --dry-run to execute.")
        return
    
    # --- EXECUTE ---
    print(f"\n{'='*60}")
    print("LINKING...")
    
    updated = 0
    for hid, did, dname, cname, city, country in matched:
        c.execute("""
            UPDATE catholic_hierarchy
            SET parent_id = ?, parent_cath_type = 'diocese',
                relationship = 'seat_of',
                notes = COALESCE(notes, '') || ' | Linked by name match'
            WHERE id = ?
        """, (did, hid))
        updated += 1
        if updated % CHUNK_SIZE == 0:
            db.commit()
            print(f"  Updated {updated}/{len(matched)}...")
    
    db.commit()
    print(f"  Updated {updated} cathedral entries")
    
    # Summary
    c.execute("SELECT COUNT(DISTINCT parent_id) FROM catholic_hierarchy WHERE cath_type='cathedral' AND parent_id IS NOT NULL")
    covered = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM catholic_hierarchy WHERE cath_type='cathedral' AND parent_id IS NULL")
    remaining = c.fetchone()[0]
    print(f"\nDioceses with cathedral: {covered}")
    print(f"Still orphaned: {remaining}")
    
    db.close()
    print("✅ Done!")


if __name__ == "__main__":
    main()
