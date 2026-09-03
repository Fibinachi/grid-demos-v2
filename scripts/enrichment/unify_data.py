"""
Unify all data sources into the master churches database.
Merges deep profiles by website match.
"""
import sqlite3, csv, os, sys

DB_PATH = '/home/ec2-user/grantwizard/churches.db'
DATA_DIR = '/home/ec2-user/grantwizard/data'

DEEP_PROFILE_COLS = [
    ('pastors', 'pastors'),
    ('service_times', 'service_times'),
    ('ministries', 'ministries'),
    ('languages', 'languages'),
    ('online_giving', 'online_giving'),
    ('attendance', 'attendance'),
    ('church_plant', 'church_plant'),
    ('has_youth', 'has_youth'),
    ('has_children', 'has_children'),
    ('has_food_pantry', 'has_food_pantry'),
    ('has_preschool', 'has_preschool'),
    ('facebook', 'facebook'),
    ('youtube', 'youtube'),
    ('instagram', 'instagram'),
    ('affiliation', 'affiliation'),
    ('fb_followers', 'fb_followers'),
    ('yt_subscribers', 'yt_subscribers'),
    ('yt_videos', 'yt_videos'),
    ('budget_indicators', 'budget_indicators'),
    ('budget_amount', 'budget_amount'),
]

def import_deep_profiles():
    """Import deep profiles into DB, matching by website."""
    path = os.path.join(DATA_DIR, 'deep_profiles.csv')
    if not os.path.exists(path):
        print(f'NOT FOUND: {path}')
        return 0
    
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    
    with open(path, encoding='utf-8') as f:
        reader = csv.DictReader(f)
        matched = 0
        skipped = 0
        for row in reader:
            website = (row.get('website') or '').strip().lower()
            if not website:
                skipped += 1
                continue
            
            # Normalize website for matching
            for prefix in ['https://', 'http://', 'www.']:
                if website.startswith(prefix):
                    website_clean = website[len(prefix):]
                    break
            else:
                website_clean = website
            website_clean = website_clean.rstrip('/')
            
            # Try matching both full and clean
            cur.execute("SELECT id FROM churches WHERE LOWER(website) = ? OR LOWER(website) = ? OR LOWER(website) = ?",
                       (website, 'https://' + website_clean, 'http://' + website_clean))
            match = cur.fetchone()
            
            if match:
                church_id = match[0]
                sets = []
                params = []
                for csv_col, db_col in DEEP_PROFILE_COLS:
                    val = row.get(csv_col, '').strip()
                    if val and val != 'N/A':
                        sets.append(f'{db_col}=?')
                        params.append(val)
                
                if sets:
                    params.append(church_id)
                    cur.execute(f"UPDATE churches SET {','.join(sets)} WHERE id=?", params)
                matched += 1
            else:
                skipped += 1
    
    conn.commit()
    conn.close()
    print(f'Deep profiles: {matched} matched, {skipped} skipped (no website match)')
    return matched

def deep_profile_coverage():
    """Report on deep profile enrichment coverage."""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    
    total = cur.execute("SELECT COUNT(*) FROM churches").fetchone()[0]
    
    print('\n=== Enrichment Coverage Report ===')
    for col, label in [
        ('website', 'Website'),
        ('email', 'Email'),
        ('phone', 'Phone'),
        ('pastors', 'Pastor named'),
        ('service_times', 'Service times'),
        ('online_giving', 'Online giving'),
        ('attendance', 'Attendance est'),
        ('has_youth', 'Youth ministry'),
        ('has_food_pantry', 'Food pantry'),
        ('facebook', 'Facebook'),
        ('youtube', 'Youtube'),
    ]:
        filled = cur.execute(f"SELECT COUNT(*) FROM churches WHERE {col} != '' AND {col} IS NOT NULL AND {col} != '0'").fetchone()[0]
        pct = round(filled / total * 100, 1)
        print(f'  {label:20s} {filled:>7d} / {total} ({pct:>5.1f}%)')
    
    # Census columns
    cur.execute("PRAGMA table_info(churches)")
    cols = [r[1] for r in cur.fetchall()]
    census_cols = [c for c in cols if c.startswith('census_')]
    print(f'\n  Census columns added: {len(census_cols)}')
    if census_cols:
        filled = cur.execute(f"SELECT COUNT(*) FROM churches WHERE {census_cols[0]} != '' AND {census_cols[0]} IS NOT NULL").fetchone()[0]
        print(f'  Records with census data: {filled} / {total}')
    
    conn.close()

def export_unified_csv():
    """Export unified dataset as CSV."""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    
    cur.execute("PRAGMA table_info(churches)")
    cols = [r[1] for r in cur.fetchall()]
    
    cur.execute(f"SELECT {','.join(cols)} FROM churches ORDER BY source, name")
    rows = cur.fetchall()
    
    out_path = os.path.join(DATA_DIR, 'unified_churches.csv')
    with open(out_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(cols)
        writer.writerows(rows)
    
    conn.close()
    print(f'\nUnified CSV exported: {out_path} ({len(rows)} records, {len(cols)} columns)')

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='Unify church data sources')
    parser.add_argument('--import-deep', action='store_true', help='Import deep profiles')
    parser.add_argument('--report', action='store_true', help='Coverage report')
    parser.add_argument('--export', action='store_true', help='Export unified CSV')
    parser.add_argument('--all', action='store_true', help='Run all steps')
    
    args = parser.parse_args()
    
    if args.all or args.import_deep:
        import_deep_profiles()
    if args.all or args.report:
        deep_profile_coverage()
    if args.all or args.export:
        export_unified_csv()
    
    if not any([args.import_deep, args.report, args.export, args.all]):
        print('No action specified. Use --all, --import-deep, --report, or --export')
