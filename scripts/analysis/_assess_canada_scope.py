#!/usr/bin/env python3
"""Assess Canadian records scope for census geography tagging."""

import sqlite3

db = sqlite3.connect(r'E:\grid\churches.db')

# Count Canadian records with coordinates
cur = db.execute('SELECT COUNT(*) FROM churches WHERE country = ? AND latitude IS NOT NULL', ('CA',))
print(f'Canadian records with coords: {cur.fetchone()[0]}')

cur = db.execute('SELECT COUNT(*) FROM churches WHERE country = ?', ('CA',))
total = cur.fetchone()[0]
print(f'Total Canadian records: {total}')

cur = db.execute('SELECT COUNT(*) FROM churches WHERE country = ? AND latitude IS NULL', ('CA',))
print(f'Canadian records WITHOUT coords: {cur.fetchone()[0]}')

# Check for postal code column
cur = db.execute("SELECT name FROM pragma_table_info('churches') WHERE name IN ('postal_code', 'postcode', 'zip_code', 'postal')")
cols = [r[0] for r in cur.fetchall()]
print(f'\nPostal code columns in churches: {cols}')

# Check church_contacts columns
cur = db.execute("SELECT name FROM pragma_table_info('church_contacts')")
print(f'\nchurch_contacts columns: {[r[0] for r in cur.fetchall()]}')

# Any existing geo/census tables
cur = db.execute("SELECT name FROM sqlite_master WHERE type='table' AND (name LIKE '%geo%' OR name LIKE '%census%' OR name LIKE '%statcan%' OR name LIKE '%canada%' OR name LIKE '%dissemin%')")
print(f'\nRelevant existing tables: {[r[0] for r in cur.fetchall()]}')

# Sample records
cur = db.execute('SELECT id, name, country, state, city, postal_code, latitude, longitude FROM churches WHERE country = ? AND latitude IS NOT NULL LIMIT 10', ('CA',))
rows = cur.fetchall()
print(f'\n=== Sample Canadian records ===')
for r in rows:
    print(f'    id={r[0]} | {r[1][:50]} | {r[2]}, {r[3]} {r[4]} | postal={r[5]} | {r[6]:.4f}, {r[7]:.4f}')

# Count by province
cur = db.execute("SELECT COALESCE(state, 'NULL'), COUNT(*) FROM churches WHERE country = ? GROUP BY state ORDER BY COUNT(*) DESC", ('CA',))
print(f'\n=== Canadian records by province ===')
for r in cur.fetchall():
    print(f'    {r[0]}: {r[1]}')

# Count by source
cur = db.execute('SELECT source, COUNT(*) FROM churches WHERE country = ? GROUP BY source ORDER BY COUNT(*) DESC', ('CA',))
print(f'\n=== Canadian records by source ===')
for r in cur.fetchall():
    print(f'    {r[0]}: {r[1]}')

# Check how many have postal codes
cur = db.execute("SELECT COUNT(*) FROM churches WHERE country = ? AND postal_code IS NOT NULL AND postal_code != ''", ('CA',))
print(f'\nCanadian records WITH postal codes: {cur.fetchone()[0]}')

# Check if natural_earth world_borders db exists
import os
if os.path.exists(r'E:\grid\data\natural_earth\world_borders.db'):
    print('\n=== natural_earth/world_borders.db EXISTS ===')
else:
    print('\n=== natural_earth/world_borders.db NOT FOUND ===')

db.close()
