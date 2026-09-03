#!/usr/bin/env python3
"""
Pre-classification cleanup pass. Removes secular trash, fixes obvious
faith misclassifications, and cleans bad names BEFORE the DeepSeek run.
Saves API costs and prevents garbage-in-garbage-out.
"""
import sqlite3, re
from datetime import datetime

db = sqlite3.connect("churches.db")
c = db.cursor()
fixed = 0

def move_batch(ids, reason):
    """Move a batch of church IDs to Other faith."""
    if not ids:
        return 0
    id_list = ",".join("?" * len(ids))
    c.execute(f"UPDATE churches SET faith='Other', landmark_type='other' WHERE id IN ({id_list})", ids)
    return c.rowcount

def fix_faith(ids, new_faith, new_tradition, new_landmark):
    """Fix faith classification for a batch."""
    if not ids:
        return 0
    id_list = ",".join("?" * len(ids))
    c.execute(f"""UPDATE churches SET faith=?, tradition=?, landmark_type=?
        WHERE id IN ({id_list})""", [new_faith, new_tradition, new_landmark] + list(ids))
    return c.rowcount

print("=== PHASE 1: SECULAR TRASH → Other ===")

# 1a. Known secular patterns (exclude genuine churches)
secular_exclusions = """AND name NOT LIKE '%CHURCH%' AND name NOT LIKE '%CHAPEL%'
    AND name NOT LIKE '%MINISTRY%' AND name NOT LIKE '%FELLOWSHIP%'
    AND name NOT LIKE '%CONGREGATION%' AND name NOT LIKE '%PARISH%'
    AND name NOT LIKE '%DIOCESE%' AND name NOT LIKE '%CATHEDRAL%'
    AND name NOT LIKE '%TEMPLE%' AND name NOT LIKE '%SYNAGOGUE%'
    AND name NOT LIKE '%MOSQUE%' AND name NOT LIKE '%MASJID%'
    AND name NOT LIKE '%GURDWARA%'"""

secular = [
    ("Dental/medical", ["% DDS%", "% DMD%", "% DENTAL%", "% CHIROPRACTIC%"]),
    ("Business", ["% INC%", "% LLC%", "% CORP%"]),
    ("Law", ["% ATTORNEY%", "%LAW OFFICE%", "%LAW GROUP%"]),
    ("Real estate", ["% REALTY%", "% PROPERTIES%", "% APARTMENTS%"]),
    ("Insurance/finance", ["% INSURANCE%", "% MORTGAGE%", "% TAX SERVICE%"]),
    ("Ranch/farm", ["% RANCH%", "% FARM%", "% OUTFITTERS%"]),
    ("Civic/fraternal", ["% ROTARY %CLUB%", "% LIONS %CLUB%", "% MOOSE %LODGE%", "% ELKS %LODGE%", "% VFW %POST%", "% AMERICAN LEGION%", "% MASONIC%", "% EAGLES %CLUB%"]),
    ("Youth orgs", ["% BOY SCOUTS%", "% GIRL SCOUTS%"]),
    ("Funeral/cemetery", ["% FUNERAL HOME%", "% CEMETERY%", "% CREMATORIUM%"]),
]

for label, patterns in secular:
    combined = " OR ".join([f"name LIKE ?" for _ in patterns])
    c.execute(f"""SELECT id FROM churches
        WHERE faith='Christian' AND ({combined}) {secular_exclusions}""", patterns)
    ids = [r[0] for r in c.fetchall()]
    n = move_batch(ids, label)
    if n:
        print(f"  {label:25s}: {n:>6,}")
        fixed += n

print(f"\n=== PHASE 2: OBVIOUS FAITH MISCLASSIFICATIONS ===")

# 2a. Temple/Synagogue/Congregation names → Judaism (comprehensive Hebrew indicators)
c.execute("""SELECT id FROM churches
    WHERE faith='Christian'
    AND ((name LIKE 'TEMPLE %' OR name LIKE 'CONGREGATION %' OR name LIKE '% SYNAGOGUE%'
         OR name LIKE 'KEHILLAT %' OR name LIKE 'KENESETH %')
    AND (name LIKE '%SHOLOM%' OR name LIKE '%ISRAEL%' OR name LIKE '%BETH %'
      OR name LIKE '%BNAI%' OR name LIKE '%SHALOM%' OR name LIKE '%TORAH%'
      OR name LIKE '%EMANU%' OR name LIKE '%CHABAD%' OR name LIKE '%LUBAVITCH%'
      OR name LIKE '%JEWISH%' OR name LIKE '%ADATH%' OR name LIKE '%ADAS%'
      OR name LIKE '%AHADATH%' OR name LIKE '%SHAAR%' OR name LIKE '%SHAARE%'
      OR name LIKE '%OHEV%' OR name LIKE '%TIFERETH%' OR name LIKE '%TIFERET%'
      OR name LIKE '%BETH EL%' OR name LIKE '%RODEF%' OR name LIKE '%MIKVEH%'
      OR name LIKE '%NER %' OR name LIKE '%NER TAMID%' OR name LIKE '%MISHKAN%'
      OR name LIKE '%ANSHE%' OR name LIKE '%ANSHEI%' OR name LIKE '%AGUDATH%'
      OR name LIKE '%CHAVERIM%' OR name LIKE '%MACHZIKEI%'))""")
n = fix_faith([r[0] for r in c.fetchall()], "Judaism", "Jewish", "synagogue")
if n:
    print(f"  Synagogues → Judaism: {n:,}")
    fixed += n

# 2b. Mosque/Masjid → Islam
c.execute("""SELECT id FROM churches
    WHERE faith='Christian'
    AND (name LIKE '%MOSQUE%' OR name LIKE '%MASJID%' OR name LIKE '% ISLAMIC%'
      OR name LIKE '%MUSLIM%' OR name LIKE '%JAMI%' OR name LIKE '%MECCA%')""")
n = fix_faith([r[0] for r in c.fetchall()], "Islam", "Muslim", "mosque")
if n:
    print(f"  Mosques → Islam: {n:,}")
    fixed += n

# 2c. Gurdwara → Sikh
c.execute("""SELECT id FROM churches WHERE faith='Christian' AND name LIKE '%GURDWARA%'""")
n = fix_faith([r[0] for r in c.fetchall()], "Sikh", "Sikh", "gurdwara")
if n:
    print(f"  Gurdwaras → Sikh: {n:,}")
    fixed += n

# 2d. Mandir/Hindu temple → Hindu
c.execute("""SELECT id FROM churches
    WHERE faith='Christian' AND (name LIKE '%MANDIR%' OR name LIKE '% HINDU %')""")
n = fix_faith([r[0] for r in c.fetchall()], "Hindu", "Hindu", "temple")
if n:
    print(f"  Hindu temples: {n:,}")
    fixed += n

# 2e. Buddhist temples/wats → Buddhist
c.execute("""SELECT id FROM churches
    WHERE faith='Christian' AND (name LIKE '%WAT %' OR name LIKE '%VIHARA%' OR name LIKE '%BUDDHIST%')""")
n = fix_faith([r[0] for r in c.fetchall()], "Buddhist", "Buddhist", "temple")
if n:
    print(f"  Buddhist: {n:,}")
    fixed += n

# 2f. Shinto shrines
c.execute("""SELECT id FROM churches
    WHERE faith='Christian' AND (name LIKE '%JINJA%' OR name LIKE '%SHRINE%' AND country='JP')""")
n = fix_faith([r[0] for r in c.fetchall()], "Shinto", "Shrine Shinto", "shrine")
if n:
    print(f"  Shinto: {n:,}")
    fixed += n

print(f"\n=== PHASE 3: BAD NAME CLEANUP ===")

# 3a. "PASTOR OF X CHURCH" → extract "X CHURCH"
c.execute("""SELECT id, name FROM churches
    WHERE faith='Christian' AND name LIKE 'PASTOR OF %'""")
pastor_rows = c.fetchall()
n = 0
for rid, rname in pastor_rows:
    m = re.match(r'^PASTOR OF (.+)$', rname, re.IGNORECASE)
    if m:
        new_name = m.group(1).strip()
        # Only fix if the extracted name has religious indicators
        if any(w in new_name.upper() for w in ['CHURCH','PARISH','CATHEDRAL','CHAPEL','SHRINE']):
            c.execute("UPDATE churches SET name=? WHERE id=?", (new_name, rid))
            n += 1
if n:
    print(f"  PASTOR OF → extracted church name: {n:,}")
    fixed += n

db.commit()

# Remaining
c.execute("SELECT COUNT(*) FROM churches WHERE faith='Christian' AND (tradition IS NULL OR tradition='')")
remaining = c.fetchone()[0]

# Provenance
c.execute("""INSERT INTO provenance_log (source, script_name, started_at, completed_at, status, churches_updated, notes)
    VALUES (?,?,?,?,'completed',?,?)""",
    ("pre_classification_cleanup", __file__, datetime.now().isoformat(), datetime.now().isoformat(),
     fixed, f"Phase 1: secular sweep. Phase 2: faith misclass fixes. Phase 3: name cleanup. {fixed} total fixes. {remaining} remaining for DeepSeek."))

db.commit()
print(f"\n{'='*50}")
print(f"Total fixes: {fixed:,}")
print(f"Remaining for DeepSeek: {remaining:,}")
db.close()
print("Done!")
