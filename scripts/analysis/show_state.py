#!/usr/bin/env python3
"""
Show all churches in a given state with contact info.
Usage: python scripts/analysis/show_state.py VT
       python scripts/analysis/show_state.py CA --minimal
       python scripts/analysis/show_state.py SC --emails-only
"""
import sqlite3, os, sys

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DB_PATH = os.path.join(PROJECT_DIR, "churches.db")
db = sqlite3.connect(DB_PATH)

state = (sys.argv[1] if len(sys.argv) > 1 else "SC").upper()
emails_only = "--emails-only" in sys.argv
minimal = "--minimal" in sys.argv

total = db.execute("SELECT COUNT(*) FROM churches WHERE state=?", (state,)).fetchone()[0]
with_web = db.execute("SELECT COUNT(*) FROM churches WHERE state=? AND website IS NOT NULL AND website != ''", (state,)).fetchone()[0]
with_email = db.execute("SELECT COUNT(*) FROM churches WHERE state=? AND email IS NOT NULL AND email != ''", (state,)).fetchone()[0]
with_phone = db.execute("SELECT COUNT(*) FROM churches WHERE state=? AND phone IS NOT NULL AND phone != ''", (state,)).fetchone()[0]
faiths = db.execute("SELECT faith_tradition, COUNT(*) FROM churches WHERE state=? GROUP BY faith_tradition ORDER BY COUNT(*) DESC", (state,)).fetchall()

print(f"\n{'='*60}")
print(f"  {state} — {total:,} churches")
print(f"{'='*60}")
print(f"  Websites: {with_web:,}  Emails: {with_email:,}  Phones: {with_phone:,}")
print(f"  Faiths: {', '.join(f'{f[0]}={f[1]:,}' for f in faiths[:6])}")
print()

if emails_only:
    rows = db.execute("SELECT name, city, email FROM churches WHERE state=? AND email IS NOT NULL AND email != '' ORDER BY city, name", (state,)).fetchall()
    print(f"{'Name':55s} {'City':18s} {'Email':35s}")
    print("-" * 110)
    for r in rows:
        print(f"{r[0][:54]:55s} {r[1][:17]:18s} {r[2]:35s}")
elif minimal:
    print(f"{'Name':55s} {'City':18s} {'Faith':12s} {'Website':35s}")
    print("-" * 120)
    rows = db.execute("SELECT name, city, faith_tradition, website FROM churches WHERE state=? ORDER BY faith_tradition, city, name", (state,)).fetchall()
    for r in rows:
        print(f"{r[0][:54]:55s} {r[1][:17]:18s} {(r[2] or '-'):12s} {(r[3] or '-'):35s}")
else:
    print(f"{'Name':55s} {'City':18s} {'Faith':12s} {'Website':35s} {'Email':30s} {'Phone':15s} {'Zip':6s}")
    print("-" * 170)
    rows = db.execute("SELECT name, city, faith_tradition, website, email, phone, zip5 FROM churches WHERE state=? ORDER BY faith_tradition, city, name", (state,)).fetchall()
    for r in rows:
        print(f"{r[0][:54]:55s} {r[1][:17]:18s} {(r[2] or '-'):12s} {(r[3] or '-'):35s} {(r[4] or '-'):30s} {(r[5] or '-'):15s} {(r[6] or '-'):6s}")

db.close()
