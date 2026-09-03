#!/usr/bin/env python3
"""
Import COGIC churches from scraped CSV into the database.
"""
import sqlite3, csv, sys, os
from datetime import datetime

DB = r'E:\grid\churches.db'
CSV = r'E:\grid\data\denom\cogic_churches.csv'

def log(msg):
    print(f'[{datetime.now().strftime("%H:%M:%S")}] {msg}', flush=True)

conn = sqlite3.connect(DB)
c = conn.cursor()

# Read CSV
with open(CSV, encoding='utf-8') as f:
    reader = csv.DictReader(f)
    churches = list(reader)

log(f'Loaded {len(churches):,} churches from CSV')

# Check existing COGIC records
existing = c.execute("SELECT COUNT(*) FROM churches WHERE denomination = 'Church of God in Christ' AND (is_closed IS NULL OR is_closed = 0)").fetchone()[0]
log(f'Existing COGIC in DB: {existing:,}')

# Import new records
imported = 0
skipped = 0
for ch in churches:
    name = ch.get('name', '').strip()
    if not name:
        skipped += 1
        continue
    
    # Parse address from raw
    address = ch.get('address', '') or ''
    city = ch.get('city_guess', '') or ''
    state = ch.get('state_guess', '') or ''
    zipcode = ch.get('zip', '') or ''
    pastor = ch.get('pastor', '') or ''
    
    # Check for duplicates by name+city+state
    existing_id = c.execute(
        "SELECT id FROM churches WHERE name = ? AND city = ? AND state = ? AND denomination = 'Church of God in Christ'",
        (name, city, state)
    ).fetchone()
    
    if existing_id:
        skipped += 1
        continue
    
    # Insert
    c.execute("""
        INSERT INTO churches (
            name, denomination, family, address, city, state, zip,
            pastor_name, source, is_closed
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
    """, (
        name,
        'Church of God in Christ',
        'Pentecostal Churches',
        address,
        city,
        state,
        zipcode,
        pastor,
        'cogic_scraper'
    ))
    imported += 1

conn.commit()
log(f'Imported: {imported:,} new, Skipped: {skipped:,}')

# Verify
total = c.execute("SELECT COUNT(*) FROM churches WHERE denomination = 'Church of God in Christ' AND (is_closed IS NULL OR is_closed = 0)").fetchone()[0]
log(f'Total COGIC in DB now: {total:,}')

conn.close()
