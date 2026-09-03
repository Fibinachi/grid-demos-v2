#!/usr/bin/env python3
"""
Match Jordan mosque data to GRID churches and import contacts.

Reads raw_jordan_mosques, fuzzy-matches by name+city to churches table,
then imports phone numbers and contact names into church_contact_values.

Usage: python scripts/enrichment/_match_jordan_mosques.py
"""
import sqlite3
import json
import re
from datetime import datetime
from difflib import SequenceMatcher

DB = r'E:\grid\churches.db'

# Arabic column name patterns for key fields
NAME_PATTERNS = ['اسم المسجد', 'المسجد', 'مسجد']
CITY_PATTERNS = ['المدينة', 'مدينة', 'المنطقة', 'اللواء', 'مكان المسجد', 'عنوان']
PHONE_PATTERNS = ['هاتف', 'رقم الهاتف', 'رقم هاتف', 'جوال', 'موبايل', 'خلوي']
IMAM_PATTERNS = ['الامام', 'اسم الامام', 'الإمام']
MUEZZIN_PATTERNS = ['المؤذن', 'اسم المؤذن', 'مؤذن']
COMMITTEE_PATTERNS = ['لجنة', 'رئيس لجنة', 'رعاية']


def find_col(cols, patterns):
    """Find first column matching any pattern."""
    for c in cols:
        cl = str(c).strip()
        for p in patterns:
            if p in cl:
                return c
    return None


def extract_contacts(row_dict):
    """Extract structured contacts from a raw row dict. Handles messy Arabic Excel headers."""
    # Normalize all keys: strip spaces, remove newlines
    clean = {}
    for k, v in row_dict.items():
        ck = str(k).strip().replace('\n', '').replace('\r', '')
        # Skip metadata columns and unnamed
        if ck.startswith('Unnamed') or ck in ('source_dataset', 'source_url', ''):
            continue
        sv = str(v).strip()
        if sv in ('nan', 'None', '', 'خالي', 'NaN'):
            continue
        clean[ck] = sv
    
    contacts = []
    
    # Find mosque name — column with 'اسم المسجد' or similar
    mosque_name = ''
    city = ''
    for ck, val in clean.items():
        # Name columns
        if 'اسم' in ck and 'مسجد' in ck and 'قديم' not in ck and 'لجنة' not in ck:
            if not mosque_name:
                mosque_name = val
        # City columns
        elif any(w in ck for w in ['مدينة', 'منطقة', 'لواء']):
            if not city:
                city = val
        elif 'مكان' in ck and 'مسجد' in ck:
            if not city:
                city = val
        elif 'عنوان' in ck and 'مسجد' in ck:
            if not city:
                city = val
    
    # Normalize
    mosque_name = re.sub(r'\s+', ' ', mosque_name).strip()
    city = re.sub(r'\s+', ' ', city).strip()
    
    # Extract contacts from remaining columns
    for ck, val in clean.items():
        # Phone columns
        if 'هاتف' in ck or 'جوال' in ck or 'موبايل' in ck:
            role = 'mosque'
            if 'امام' in ck:
                role = 'imam'
            elif 'مؤذن' in ck:
                role = 'muezzin'
            elif 'لجنة' in ck or 'رئيس' in ck:
                role = 'committee_chair'
            # Clean phone number
            phone = re.sub(r'[^\d+]', '', val)
            if len(phone) >= 7:
                contacts.append({
                    'contact_type': 'phone',
                    'value': phone,
                    'role': role,
                    'confidence': 0.85
                })
        
        # Imam name columns
        elif 'امام' in ck and 'اسم' in ck and 'هاتف' not in ck:
            contacts.append({
                'contact_type': 'name',
                'value': val,
                'role': 'imam',
                'confidence': 0.90
            })
        
        # Muezzin name columns
        elif 'مؤذن' in ck and 'اسم' in ck and 'هاتف' not in ck:
            contacts.append({
                'contact_type': 'name',
                'value': val,
                'role': 'muezzin',
                'confidence': 0.90
            })
        
        # Committee chair
        elif 'رئيس' in ck and ('لجنة' in ck or 'رعاية' in ck) and 'هاتف' not in ck:
            contacts.append({
                'contact_type': 'name',
                'value': val,
                'role': 'committee_chair',
                'confidence': 0.85
            })
    
    return mosque_name, city, contacts


def fuzzy_match(a, b):
    """Simple fuzzy match ratio."""
    a = re.sub(r'[^\w\s]', '', str(a)).lower().strip()
    b = re.sub(r'[^\w\s]', '', str(b)).lower().strip()
    if not a or not b:
        return 0
    return SequenceMatcher(None, a, b).ratio()


def main():
    db = sqlite3.connect(DB, timeout=60)
    
    print('Loading raw Jordan mosque data...')
    rows = db.execute("SELECT id, raw_data FROM raw_jordan_mosques WHERE raw_data IS NOT NULL").fetchall()
    print(f'  {len(rows)} raw records')
    
    # Parse all rows
    parsed = []
    for rid, raw in rows:
        try:
            row_dict = json.loads(raw)
            name, city, contacts = extract_contacts(row_dict)
            if name and name not in ('nan', 'None', ''):
                parsed.append({
                    'raw_id': rid,
                    'name': name,
                    'city': city,
                    'contacts': contacts
                })
        except:
            continue
    
    print(f'  {len(parsed)} parsed with names')
    
    # Load Jordan churches for matching
    churches = db.execute(
        "SELECT id, name, city, latitude, longitude FROM churches WHERE country='JO'"
    ).fetchall()
    print(f'  {len(churches)} JO churches to match against')
    
    # Match by name
    matched = 0
    new_contacts = 0
    skipped_no_name = 0
    skipped_no_contacts = 0
    
    for p in parsed:
        best_score = 0
        best_church = None
        
        for c in churches:
            score = fuzzy_match(p['name'], c[1])
            if score > best_score:
                best_score = score
                best_church = c
        
        if best_score >= 0.65 and best_church:
            matched += 1
            for contact in p['contacts']:
                value = contact['value']
                # Skip invalid phone numbers
                if contact['contact_type'] == 'phone':
                    value = re.sub(r'[^\d+]', '', value)
                    if len(value) < 7:
                        continue
                
                try:
                    db.execute('''
                        INSERT OR IGNORE INTO church_contact_values
                            (church_id, contact_type, value, confidence, source, notes)
                        VALUES (?, ?, ?, ?, ?, ?)
                    ''', (
                        best_church[0],
                        contact['contact_type'],
                        value,
                        contact.get('confidence', 0.85),
                        'opendata.gov.jo',
                        f"role:{contact.get('role', 'mosque')}"
                    ))
                    new_contacts += 1
                except:
                    pass
    
    db.commit()
    
    print(f'\n  Matched: {matched} / {len(parsed)} mosques')
    print(f'  New contacts imported: {new_contacts}')
    
    # Show sample
    print('\n  Sample matches:')
    sample = db.execute('''
        SELECT DISTINCT c.name, c.city, v.value, v.notes
        FROM church_contact_values v
        JOIN churches c ON v.church_id = c.id
        WHERE v.source = 'opendata.gov.jo'
        LIMIT 8
    ''').fetchall()
    for s in sample:
        print(f'    {s[0][:35]:35s} | {s[1] or "?":15s} | {s[2]:15s} | {s[3]}')
    
    # Provenance
    now = datetime.now().isoformat()
    db.execute('''
        INSERT INTO provenance_log
            (source, script_name, started_at, completed_at,
             churches_updated, fields_populated, status, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        'opendata_gov_jo_match',
        '_match_jordan_mosques.py',
        now, now, matched,
        'contact_values (phone, name)',
        'completed',
        f'{matched}/{len(parsed)} Jordan mosques matched, {new_contacts} contacts imported'
    ))
    db.commit()
    db.close()
    
    print(f'\n{"="*60}')
    print(f'DONE: {matched} mosques matched, {new_contacts} contacts imported')
    print(f'{"="*60}')


if __name__ == '__main__':
    main()
