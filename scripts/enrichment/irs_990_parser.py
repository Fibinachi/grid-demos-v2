#!/usr/bin/env python3
"""
IRS Form 990 E-File XML Parser
===============================
Extracts websites, phone numbers, and emails from raw IRS Form 990 e-file XML
data hosted on AWS Open Data (s3://irs-form-990/).

Modern Form 990 e-file XML frequently contains:
  - Filer/WebSite — Official organization website URL
  - Filer/Phone — Organization phone number
  - Filer/Email — Contact email (less common but present)
  - ReturnHeader/Preparer info — Tax preparer contacts (skip)
  - Schedule O — Additional org details (sometimes has website/email)

Workflow:
  1. Download IRS yearly index CSVs (list EIN → XML file paths)
  2. Cross-reference against our 251K church EINs
  3. Download latest XML filing per EIN (most recent tax year)
  4. Extract website, phone, email from XML header metadata
  5. Write results back to churches.db with provenance logging

Usage:
    # Full run — process all IRS-sourced churches with EINs
    python scripts/enrichment/irs_990_parser.py

    # Dry run — preview what would be found
    python scripts/enrichment/irs_990_parser.py --dry-run --limit 5000

    # Resume from checkpoint (avoids re-downloading)
    python scripts/enrichment/irs_990_parser.py --resume

Requires:
    pip install boto3  (AWS SDK — for S3 access)
    pip install lxml   (fast XML parsing)

AWS Open Data: s3://irs-form-990/ — No AWS credentials needed (public bucket).
"""
import csv, io, json, os, re, sys, time, sqlite3, urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from collections import defaultdict

# ── Optional dependencies ──
try:
    import boto3
    from botocore import UNSIGNED
    from botocore.config import Config
    HAS_BOTO = True
except ImportError:
    HAS_BOTO = False

try:
    from lxml import etree
    HAS_LXML = True
except ImportError:
    HAS_LXML = False

# ── Config ──
PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DB_PATH = os.path.join(PROJECT_DIR, 'churches.db')
CHECKPOINT = os.path.join(PROJECT_DIR, 'data', 'irs_990_checkpoint.json')

# IRS S3 bucket (public AWS Open Data — no credentials needed)
IRS_BUCKET = 'irs-form-990'
IRS_REGION = 'us-east-1'

# Years to scan — most recent first (stop when enough found)
IRS_YEARS = list(range(2025, 2018, -1))  # 2025 down to 2019

# Concurrency
PARSE_WORKERS = 20  # XML download + parse threads
INDEX_DOWNLOAD_WORKERS = 8

# Fields we care about in IRS XML
NSMAP = {
    'irs': 'http://www.irs.gov/efile',
    'xf': 'http://www.w3.org/2002/08/xhtml/xforms',
}

# ── Stats ──
stats = {
    'eins_in_db': 0,
    'index_entries': 0,
    'matched_eins': 0,
    'xml_downloaded': 0,
    'xml_parsed': 0,
    'websites_found': 0,
    'phones_found': 0,
    'emails_found': 0,
    'xml_errors': 0,
    'skipped_existing': 0,
    'db_updates_website': 0,
    'db_updates_phone': 0,
    'db_updates_email': 0,
    'financial_records': 0,
    'officers_found': 0,
    'officers_matched_staff': 0,
}


def get_s3_client():
    """Get anonymous S3 client (no credentials needed for public bucket)."""
    return boto3.client(
        's3',
        region_name=IRS_REGION,
        config=Config(signature_version=UNSIGNED)
    )


def get_irs_index_files(year):
    """Get list of IRS index CSV keys for a given year.
    
    IRS publishes index files like: index_2023.csv, index_2024.csv
    Recent years also have sharded indexes: index_2024_1.csv through index_2024_N.csv
    """
    s3 = get_s3_client()
    candidates = [f'index_{year}.csv']
    # Also check for sharded indexes
    try:
        paginator = s3.get_paginator('list_objects_v2')
        pages = paginator.paginate(Bucket=IRS_BUCKET, Prefix=f'index_{year}_')
        for page in pages:
            for obj in page.get('Contents', []):
                key = obj['Key']
                if key.endswith('.csv') and key not in candidates:
                    candidates.append(key)
    except Exception as e:
        print(f"  [WARN] Could not list sharded indexes for {year}: {e}")
    
    return candidates


def download_irs_index(year, timeout=120):
    """Download IRS yearly index CSV. Returns list of (ein, file_path, tax_period) tuples."""
    s3 = get_s3_client()
    entries = []
    index_files = get_irs_index_files(year)
    
    for idx_key in index_files:
        try:
            obj = s3.get_object(Bucket=IRS_BUCKET, Key=idx_key)
            body = obj['Body'].read().decode('utf-8', errors='replace')
            reader = csv.DictReader(io.StringIO(body))
            for row in reader:
                # Index CSV columns: EIN, TAX_PERIOD, RETURN_TYPE, FILE_PATH, etc.
                ein = row.get('EIN', '').strip()
                file_path = row.get('FILE_PATH', '').strip() or row.get('OBJECT_ID', '').strip()
                tax_period = row.get('TAX_PERIOD', '').strip()
                return_type = row.get('RETURN_TYPE', '').strip()
                
                if ein and file_path:
                    # Filter: only interested in 990 series (990, 990-EZ, 990-PF)
                    if return_type and not re.match(r'^990', return_type):
                        continue
                    entries.append((ein, file_path, tax_period))
        except Exception as e:
            print(f"  [WARN] Could not download {idx_key}: {e}")
            continue
    
    return entries


def parse_irs_xml(xml_bytes):
    """Parse IRS 990 XML and extract website, phone, email from header metadata.
    
    Returns dict with keys: website, phone, email (or None if not found).
    """
    result = {'website': None, 'phone': None, 'email': None}
    
    try:
        root = etree.fromstring(xml_bytes)
    except Exception:
        return result
    
    # Register namespaces
    ns = {}
    for ns_key, ns_val in NSMAP.items():
        ns[ns_key] = ns_val
    
    # Try to find actual namespace from the document
    root_tag = root.tag
    doc_ns = ''
    if root_tag.startswith('{'):
        doc_ns = root_tag[:root_tag.index('}') + 1]
    
    # XPath helper — tries multiple namespace patterns
    def find_text(xpath_pattern):
        for prefix in [doc_ns, NSMAP.get('irs', ''), '']:
            if prefix:
                full_xpath = xpath_pattern.replace('ns:', f'{{{prefix[1:-1]}}}')
            else:
                full_xpath = xpath_pattern.replace('ns:', '')
            try:
                elements = root.xpath(full_xpath)
                if elements and elements[0].text:
                    return elements[0].text.strip()
            except Exception:
                continue
        return None
    
    # IRS e-file XML structure (simplified):
    # ReturnHeader
    #   Filer
    #     EIN
    #     BusinessName
    #     BusinessNameControl
    #     Phone
    #     WebSite   ← THIS is what we want (often present in modern filings)
    #     USAddress
    #   Preparer
    #   ...etc
    
    # Try to find website — common locations
    website = find_text('//ns:Filer/ns:WebSite/text()')
    if not website:
        website = find_text('//ns:WebSite/text()')
    if not website:
        # Some returns have it in ReturnHeader
        website = find_text('//ns:ReturnHeader/ns:Filer/ns:WebSite/text()')
    # Also check Schedule O or other schedules
    if not website:
        website = find_text('//ns:WebsiteAddressTxt/text()')
    
    # Phone number
    phone = find_text('//ns:Filer/ns:Phone/text()')
    if not phone:
        phone = find_text('//ns:ReturnHeader/ns:Filer/ns:Phone/text()')
    
    # Email — less common but occasionally present
    email = find_text('//ns:Filer/ns:Email/text()')
    if not email:
        email = find_text('//ns:ReturnHeader/ns:Filer/ns:Email/text()')
    # Some have it in the ReturnHeader level
    if not email:
        email = find_text('//ns:EmailAddressTxt/text()')
    
    # Clean up results
    if website:
        # Normalize URL
        website = website.lower().strip()
        if not website.startswith('http'):
            website = 'https://' + website
        # Basic sanity check
        if not re.match(r'^https?://[a-z0-9][-a-z0-9.]+\.[a-z]{2,}', website):
            website = None
    
    if phone:
        phone = re.sub(r'[^\d]', '', phone)
        if len(phone) == 10:
            phone = f"({phone[:3]}) {phone[3:6]}-{phone[6:]}"
        elif len(phone) != 0:
            phone = None  # Skip non-10-digit phones
    
    if email:
        email = email.strip().lower()
        if not re.match(r'^[^@]+@[^@]+\.[^@]+$', email):
            email = None
    
    return {'website': website, 'phone': phone, 'email': email}


def load_church_eins(db, limit=0):
    """Load all IRS-sourced church EINs that need website/phone/email enrichment."""
    query = """
        SELECT id, ein, name
        FROM churches
        WHERE ein != ''
          AND source LIKE '%irs%'
          AND (website = '' OR phone = '' OR email = '')
        ORDER BY id
    """
    if limit:
        query += f" LIMIT {limit}"
    return db.execute(query).fetchall()


def resume_from_checkpoint():
    """Load previously processed EINs to avoid re-downloading."""
    if not os.path.exists(CHECKPOINT):
        return set()
    try:
        with open(CHECKPOINT) as f:
            data = json.load(f)
        return set(data.get('processed_eins', []))
    except Exception:
        return set()


def save_checkpoint(processed_eins):
    """Save checkpoint of processed EINs."""
    os.makedirs(os.path.dirname(CHECKPOINT), exist_ok=True)
    with open(CHECKPOINT, 'w') as f:
        json.dump({'processed_eins': list(processed_eins),
                    'updated': datetime.now().isoformat()}, f)


def process_xml_for_church(s3, ein, file_path, church_id, church_name):
    """Download and parse a single IRS XML for a church. Returns update tuple or None."""
    try:
        obj = s3.get_object(Bucket=IRS_BUCKET, Key=file_path)
        xml_bytes = obj['Body'].read()
        with stats_lock:
            stats['xml_downloaded'] += 1
    except Exception as e:
        with stats_lock:
            stats['xml_errors'] += 1
        return None
    
    info = parse_irs_xml(xml_bytes)
    
    with stats_lock:
        stats['xml_parsed'] += 1
        if info['website']:
            stats['websites_found'] += 1
        if info['phone']:
            stats['phones_found'] += 1
        if info['email']:
            stats['emails_found'] += 1
    
    # Only return if we found something useful
    if info['website'] or info['phone'] or info['email']:
        return (church_id, church_name, ein, info['website'], info['phone'], info['email'])
    return None


def main():
    import argparse
    parser = argparse.ArgumentParser(description='IRS Form 990 XML Parser')
    parser.add_argument('--dry-run', action='store_true', help='Preview only')
    parser.add_argument('--limit', type=int, default=0, help='Limit churches to process')
    parser.add_argument('--resume', action='store_true', help='Resume from checkpoint')
    parser.add_argument('--workers', type=int, default=PARSE_WORKERS, help='Download workers')
    args = parser.parse_args()
    
    if not HAS_BOTO:
        print("ERROR: boto3 required. Install: pip install boto3")
        sys.exit(1)
    if not HAS_LXML:
        print("ERROR: lxml required. Install: pip install lxml")
        sys.exit(1)
    
    global stats_lock
    stats_lock = __import__('threading').Lock()
    
    print("=" * 60)
    print("IRS Form 990 E-File XML Parser")
    print("=" * 60)
    
    # Connect to DB
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    
    # Load churches with EINs that need enrichment
    churches = load_church_eins(db, args.limit)
    print(f"\nChurches with EINs needing enrichment: {len(churches):,}")
    stats['eins_in_db'] = len(churches)
    
    if not churches:
        print("Nothing to do. All churches already have website/phone/email.")
        return
    
    # Load checkpoint if resuming
    processed_eins = resume_from_checkpoint() if args.resume else set()
    if processed_eins:
        print(f"Resuming: {len(processed_eins):,} EINs already processed")
    
    # Step 1: Build EIN → church mapping
    ein_to_church = {}
    for row in churches:
        ein_to_church[row['ein']] = (row['id'], row['name'])
    
    # Step 2: Download IRS index files for recent years
    print(f"\n--- Step 1: Downloading IRS index files ({len(IRS_YEARS)} years) ---")
    all_index_entries = []
    
    for year in IRS_YEARS:
        entries = download_irs_index(year)
        all_index_entries.extend(entries)
        print(f"  {year}: {len(entries):,} index entries")
    
    stats['index_entries'] = len(all_index_entries)
    print(f"\nTotal index entries across all years: {len(all_index_entries):,}")
    
    # Step 3: Filter index entries to our EINs
    # Build EIN → list of (file_path, tax_period) for our churches
    ein_files = defaultdict(list)
    for ein, file_path, tax_period in all_index_entries:
        if ein in ein_to_church:
            ein_files[ein].append((file_path, tax_period))
    
    stats['matched_eins'] = len(ein_files)
    print(f"\n--- Step 2: Matched {len(ein_files):,} EINs to IRS index ---")
    
    if not ein_files:
        print("No matching IRS filings found. Exiting.")
        db.close()
        return
    
    # Step 4: For each EIN, pick the latest filing and download + parse XML
    print(f"\n--- Step 3: Downloading and parsing XML filings ---")
    
    s3 = get_s3_client()
    updates = []
    
    # Prioritize: most recent filing per EIN
    parse_queue = []
    skipped = 0
    for ein, filings in ein_files.items():
        if ein in processed_eins:
            skipped += 1
            continue
        # Sort by tax_period descending, pick latest
        filings.sort(key=lambda x: x[1], reverse=True)
        best_path = filings[0][0]
        church_id, church_name = ein_to_church[ein]
        parse_queue.append((ein, best_path, church_id, church_name))
    
    stats['skipped_existing'] = skipped
    print(f"  Queue: {len(parse_queue):,} filings to download")
    if skipped:
        print(f"  Skipped (already processed): {skipped:,}")
    
    if args.dry_run:
        print("\n  [DRY RUN] Would process these filings:")
        for i, (ein, path, cid, cname) in enumerate(parse_queue[:10]):
            print(f"    {cid:>8d} | {cname[:40]:40s} | EIN {ein} | {path}")
        if len(parse_queue) > 10:
            print(f"    ... and {len(parse_queue) - 10:,} more")
    else:
        # Parallel download + parse
        with ThreadPoolExecutor(max_workers=args.workers) as executor:
            futures = {
                executor.submit(process_xml_for_church, s3, ein, path, cid, cname):
                (ein, cid) for ein, path, cid, cname in parse_queue
            }
            
            done_count = 0
            last_report = time.time()
            for future in as_completed(futures):
                result = future.result()
                if result:
                    updates.append(result)
                done_count += 1
                
                if time.time() - last_report > 5:
                    pct = done_count / len(parse_queue) * 100
                    print(f"    Progress: {done_count:,}/{len(parse_queue):,} ({pct:.1f}%) "
                          f"— Found: {len(updates):,} churches with data")
                    last_report = time.time()
        
        print(f"\n  Download complete: {stats['xml_downloaded']:,} XML files")
        print(f"  Parsed: {stats['xml_parsed']:,}")
        print(f"  Errors: {stats['xml_errors']:,}")
        print(f"  Found websites: {stats['websites_found']:,}")
        print(f"  Found phones: {stats['phones_found']:,}")
        print(f"  Found emails: {stats['emails_found']:,}")
        
        # Step 5: Write to database
        print(f"\n--- Step 4: Writing {len(updates):,} updates to database ---")
        
        db_updates_website = 0
        db_updates_phone = 0
        db_updates_email = 0
        
        for church_id, church_name, ein, website, phone, email in updates:
            parts = []
            
            if website:
                # Check if current website is empty OR lower confidence
                cur = db.execute("SELECT website, website_source, website_confidence FROM churches WHERE id=?", (church_id,))
                row = cur.fetchone()
                current_website = row['website'] if row else ''
                current_source = row['website_source'] if row else ''
                current_conf = row['website_confidence'] if row else 0
                
                if not current_website or (current_conf or 0) < 0.5:
                    parts.append(f"website={json.dumps(website)}")
                    parts.append("website_source='irs_990'")
                    parts.append("website_confidence=0.70")
                    db_updates_website += 1
            
            if phone:
                cur = db.execute("SELECT phone FROM churches WHERE id=?", (church_id,))
                row = cur.fetchone()
                if not row or not row['phone']:
                    parts.append(f"phone={json.dumps(phone)}")
                    parts.append("phone_source='irs_990'")
                    db_updates_phone += 1
            
            if email:
                cur = db.execute("SELECT email FROM churches WHERE id=?", (church_id,))
                row = cur.fetchone()
                if not row or not row['email']:
                    parts.append(f"email={json.dumps(email)}")
                    parts.append("email_source='irs_990'")
                    db_updates_email += 1
            
            if parts:
                parts.append("last_updated=datetime('now')")
                sql = f"UPDATE churches SET {', '.join(parts)} WHERE id=?"
                db.execute(sql, (church_id,))
        
        db.commit()
        
        stats['db_updates_website'] = db_updates_website
        stats['db_updates_phone'] = db_updates_phone
        stats['db_updates_email'] = db_updates_email
        
        # Log to provenance
        db.execute("""
            INSERT INTO provenance_log 
                (source, script_name, started_at, completed_at, 
                 churches_updated, churches_inserted, fields_populated, 
                 records_attempted, records_matched, status, notes)
            VALUES (?, ?, ?, ?, ?, 0, ?, ?, ?, 'completed', ?)
        """, (
            'irs_990',
            'irs_990_parser.py',
            datetime.now().isoformat(),
            datetime.now().isoformat(),
            len(updates),
            'website,phone,email',
            len(parse_queue),
            len(updates),
            f'Found {stats["websites_found"]} websites, {stats["phones_found"]} phones, {stats["emails_found"]} emails'
        ))
        db.commit()
        
        # Save checkpoint
        all_processed = processed_eins | {ein for ein, _, _, _ in parse_queue}
        save_checkpoint(all_processed)
    
    # ---------- Summary ----------
    print(f"\n{'='*60}")
    print(f"RESULTS SUMMARY")
    print(f"{'='*60}")
    print(f"  Churches with EINs in DB:      {stats['eins_in_db']:>8,}")
    print(f"  IRS index entries scanned:     {stats['index_entries']:>8,}")
    print(f"  EINs matched to filings:       {stats['matched_eins']:>8,}")
    print(f"  XML files downloaded:          {stats['xml_downloaded']:>8,}")
    print(f"  XML parse errors:              {stats['xml_errors']:>8,}")
    print(f"  Websites found in XML:         {stats['websites_found']:>8,}")
    print(f"  Phones found in XML:           {stats['phones_found']:>8,}")
    print(f"  Emails found in XML:           {stats['emails_found']:>8,}")
    print(f"  DB website updates:            {stats['db_updates_website']:>8,}")
    print(f"  DB phone updates:              {stats['db_updates_phone']:>8,}")
    print(f"  DB email updates:              {stats['db_updates_email']:>8,}")
    
    db.close()
    print("\nDone!")


if __name__ == '__main__':
    main()
