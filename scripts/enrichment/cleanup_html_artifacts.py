#!/usr/bin/env python3
"""
GrantWizard — Data Cleanup Utility
Run after any scrape/enrichment to sanitize HTML artifacts from text fields.
"""
import sqlite3, html, re, os

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DB_PATH = os.path.join(PROJECT_DIR, "churches.db")

# All text fields that could contain HTML artifacts
# Run this after EVERY scrape/enrichment to strip HTML entities from text fields.
# Usage: .venv\Scripts\python scripts/enrichment/cleanup_html_artifacts.py

TEXT_COLS = [
    'name', 'city', 'state', 'address', 'pastor_name', 'email', 'website',
    'notes', 'denomination', 'family', 'conference', 'synod', 'diocese',
    'association', 'district', 'presbytery', 'province', 'deanery',
    'archdiocese', 'denom_region', 'denom_subgroup', 'faith_tradition',
    'campus_name', 'service_times', 'languages', 'livestream_link',
    'online_giving_link', 'facebook_url', 'instagram_url', 'youtube_url',
    'leadership_structure', 'doctrinal_alignment', 'worship_style',
    'community_impact', 'primary_language', 'secondary_languages',
    'cms_type', 'historical_status', 'calendar_type', 'rite',
]

HTML_ENTITIES = [
    ('&amp;', '&'),
    ('&nbsp;', ' '),
    ('&lt;', '<'),
    ('&gt;', '>'),
    ('&quot;', '"'),
    ('&#39;', "'"),
    ('&apos;', "'"),
]

def clean_db(db_path=None):
    """Run full HTML artifact cleanup on the database. Returns count of fixes."""
    path = db_path or DB_PATH
    conn = sqlite3.connect(path, timeout=60)
    conn.execute("PRAGMA journal_mode=WAL")
    c = conn.cursor()
    total = 0
    
    for col in TEXT_COLS:
        try:
            # 1. HTML numeric entities (&#xxxx;) via html.unescape
            c.execute(f"SELECT COUNT(1) FROM churches WHERE {col} LIKE '%&#%'")
            if c.fetchone()[0] > 0:
                c.execute(f"SELECT id, {col} FROM churches WHERE {col} LIKE '%&#%'")
                for rid, val in c.fetchall():
                    cleaned = html.unescape(val)
                    if cleaned != val:
                        c.execute(f"UPDATE churches SET {col}=? WHERE id=?", (cleaned, rid))
                        total += 1
            
            # 2. Named HTML entities (&amp;, &nbsp;, etc.)
            for ent, replacement in HTML_ENTITIES:
                c.execute(f"SELECT COUNT(1) FROM churches WHERE {col} LIKE ?", (f'%{ent}%',))
                if c.fetchone()[0] > 0:
                    c.execute(f"SELECT id, {col} FROM churches WHERE {col} LIKE ?", (f'%{ent}%',))
                    for rid, val in c.fetchall():
                        cleaned = val.replace(ent, replacement)
                        if cleaned != val:
                            c.execute(f"UPDATE churches SET {col}=? WHERE id=?", (cleaned, rid))
                            total += 1
            
            # 3. Literal NBSP (\xa0) characters
            c.execute(f"SELECT COUNT(1) FROM churches WHERE {col} LIKE '%' || char(160) || '%'")
            if c.fetchone()[0] > 0:
                c.execute(f"SELECT id, {col} FROM churches WHERE {col} LIKE '%' || char(160) || '%'")
                for rid, val in c.fetchall():
                    cleaned = val.replace('\xa0', ' ').strip()
                    if cleaned != val:
                        c.execute(f"UPDATE churches SET {col}=? WHERE id=?", (cleaned, rid))
                        total += 1
            
        except Exception as e:
            print(f"  Skipping {col}: {e}")
    
    conn.commit()
    conn.close()
    return total


def main():
    print("GrantWizard — HTML Artifact Cleanup")
    print(f"DB: {DB_PATH}")
    print(f"Checking {len(TEXT_COLS)} text columns...")
    fixes = clean_db()
    print(f"Done! {fixes:,} fixes applied.")
    
    if fixes > 0:
        # Log to provenance if table exists
        try:
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            c.execute("INSERT INTO provenance_log (event_type, description) VALUES (?, ?)",
                      ('data_cleanup', f'HTML artifact cleanup: {fixes} fixes'))
            conn.commit()
            conn.close()
        except:
            pass


if __name__ == '__main__':
    main()
