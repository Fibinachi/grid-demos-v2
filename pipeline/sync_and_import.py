"""
Sync & Import Pipeline Results
================================
Pulls completed results from all EC2s and imports into SQLite.
Run this periodically to keep the database up to date.
"""
import subprocess, os, csv, sqlite3, sys, re
from datetime import datetime
from gw_filters import status
from gw_filters import clean as gw_clean

KEY = os.path.expanduser("~/.ssh/grantwizard-key.pem")
DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "churches.db")
INCOMING = os.path.join(os.path.dirname(os.path.abspath(__file__)), "incoming")
os.makedirs(INCOMING, exist_ok=True)

# ─── EC2 output files to sync ─────────────────────────────────────
INSTANCES = {
    "18.118.169.15": ["deep_profiles.csv"],
    "18.188.95.190": ["scraped_chunk_1.csv", "deep_profiles_1.csv"],
    "18.191.145.108": ["scraped_chunk_2.csv", "deep_profiles_2.csv"],
    "3.19.141.81":    ["found_chunk_0.csv", "found_chunk_0_ckpt.csv", "scraped_irs.csv"],
    "18.191.24.204":  ["found_chunk_0.csv", "found_chunk_0_ckpt.csv", "scraped_irs.csv"],
    "3.138.187.55":   ["found_chunk_0.csv", "found_chunk_0_ckpt.csv", "scraped_irs.csv"],
}

def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")

def scp_from(ip, remote_file, local_path):
    """SCP a file from EC2 to local machine. Returns True if succeeded."""
    full = ['scp', '-o', 'StrictHostKeyChecking=no', '-o', 'ConnectTimeout=5',
            '-i', KEY, f'ubuntu@{ip}:~/{remote_file}', local_path]
    try:
        r = subprocess.run(full, capture_output=True, text=True, timeout=15)
        return r.returncode == 0
    except:
        return False

def sync_all():
    """Pull all output files from EC2s."""
    synced = []
    for ip, files in INSTANCES.items():
        for fname in files:
            local_name = f"{ip}_{fname}"
            local_path = os.path.join(INCOMING, local_name)
            if scp_from(ip, fname, local_path):
                size = os.path.getsize(local_path)
                log(f"  {ip}:{fname} -> {local_name} ({size:,} bytes)")
                synced.append(local_name)
            else:
                # Check if it exists remotely first
                check = subprocess.run(
                    ['ssh', '-o', 'StrictHostKeyChecking=no', '-o', 'ConnectTimeout=5',
                     '-i', KEY, f'ubuntu@{ip}', f'test -f ~/{fname} && echo YES || echo NO'],
                    capture_output=True, text=True, timeout=8)
                if "YES" in check.stdout:
                    log(f"  {ip}:{fname} EXISTS but scp failed (permissions?)")
                # else: file doesn't exist yet, that's fine
    return synced

def import_found_csv(csv_path, label):
    """Import IRS finder results (found_chunk_X.csv).
    Matching priority: EIN > Address > Phone > Website > Name+State
    """
    if not os.path.exists(csv_path):
        return 0
    conn = sqlite3.connect(DB)
    cur = conn.cursor()
    
    for col in ["website", "website_scrape_status", "email_scrape_status"]:
        try:
            cur.execute(f"ALTER TABLE churches ADD COLUMN {col} TEXT DEFAULT 'pending'")
        except:
            pass
    
    imported = 0
    with open(csv_path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            church_name = (row.get("church_name") or "").strip()
            website = (row.get("website") or "").strip()
            ein = (row.get("ein") or "").strip()
            email = (row.get("email") or "").strip()
            phone = (row.get("phone") or "").strip()
            address = (row.get("address") or row.get("street") or "").strip()
            city = (row.get("city") or "").strip()
            state = (row.get("state") or "").strip()
            zip_code = (row.get("zip") or "").strip()
            
            has_data = website or email or phone
            
            # ── Priority 1: Match by EIN ──────────────────────────
            if ein:
                if has_data:
                    cur.execute("UPDATE churches SET website=COALESCE(website,?), website_scrape_status='found' WHERE ein=?", (website, ein))
                    if email:
                        cur.execute("UPDATE churches SET email=COALESCE(email,?), email_scrape_status='found' WHERE ein=?", (email, ein))
                    if phone:
                        cur.execute("UPDATE churches SET phone=COALESCE(phone,?) WHERE ein=?", (phone, ein))
                    if cur.rowcount > 0:
                        imported += cur.rowcount
                        continue
                else:
                    cur.execute("UPDATE churches SET website_scrape_status='not_found' WHERE ein=?", (ein,))
                    continue
            
            # ── Priority 2: Match by address ──────────────────────
            if address and state:
                addr_clean = address.replace(',', '').strip()
                cur.execute("""
                    UPDATE churches SET website=COALESCE(website,?),
                        website_scrape_status='found'
                    WHERE address LIKE ? AND state=?
                """, (website, f"%{addr_clean[:20]}%", state))
                if cur.rowcount > 0:
                    if email:
                        cur.execute("UPDATE churches SET email=COALESCE(email,?) WHERE address LIKE ? AND state=?", (email, f"%{addr_clean[:20]}%", state))
                    if phone:
                        cur.execute("UPDATE churches SET phone=COALESCE(phone,?) WHERE address LIKE ? AND state=?", (phone, f"%{addr_clean[:20]}%", state))
                    imported += cur.rowcount
                    continue
            
            # ── Priority 3: Match by phone ────────────────────────
            if phone:
                digits = re.sub(r'\D', '', phone)
                if len(digits) >= 10:
                    cur.execute("""
                        UPDATE churches SET website=COALESCE(website,?), website_scrape_status='found'
                        WHERE phone IS NOT NULL AND REPLACE(REPLACE(REPLACE(REPLACE(phone,'-',''),'(',''),')',''),' ','') LIKE ?
                    """, (website, f"%{digits[-10:]}%"))
                    if cur.rowcount > 0:
                        if email:
                            cur.execute("UPDATE churches SET email=COALESCE(email,?) WHERE phone IS NOT NULL AND REPLACE(REPLACE(REPLACE(REPLACE(phone,'-',''),'(',''),')',''),' ','') LIKE ?", (email, f"%{digits[-10:]}%"))
                        imported += cur.rowcount
                        continue
            
            # ── Priority 4: Match by website ──────────────────────
            if website:
                cur.execute("""
                    UPDATE churches SET website=?, website_scrape_status='found'
                    WHERE website=? AND (website='' OR website IS NULL)
                """, (website, website))
                if cur.rowcount == 0:
                    # Website already set - just update status
                    cur.execute("UPDATE churches SET website_scrape_status='found' WHERE website=?", (website,))
                if email:
                    cur.execute("UPDATE churches SET email=COALESCE(email,?), email_scrape_status='found' WHERE website=?", (email, website))
                if cur.rowcount > 0:
                    imported += cur.rowcount
                    continue
            
            # ── Priority 5: Match by name + state (lowest confidence) ──
            if church_name and state:
                cur.execute(
                    "UPDATE churches SET website=COALESCE(website,?), website_scrape_status='found' WHERE name LIKE ? AND state=? AND (website='' OR website IS NULL)",
                    (website, f"%{church_name[:30]}%", state)
                )
                if cur.rowcount > 0:
                    if email:
                        cur.execute(
                            "UPDATE churches SET email=COALESCE(email,?), email_scrape_status='found' WHERE name LIKE ? AND state=?",
                            (email, f"%{church_name[:30]}%", state)
                        )
                    imported += cur.rowcount

def import_phase1_csv(csv_path, label):
    """Import Phase 1 scraper results (scraped_chunk_X.csv with emails/phones).
    Matching: by website only, but uses COALESCE to never overwrite existing data."""
    if not os.path.exists(csv_path):
        return 0
    conn = sqlite3.connect(DB)
    cur = conn.cursor()
    for col in ["website_scrape_status", "email_scrape_status"]:
        try:
            cur.execute(f"ALTER TABLE churches ADD COLUMN {col} TEXT DEFAULT 'pending'")
        except:
            pass
    
    imported = 0
    with open(csv_path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            website = (row.get("website") or "").strip()
            email = (row.get("email") or "").strip()
            phone = (row.get("phone") or "").strip()
            
            if not website:
                continue
            
            # Mark website as found (non-destructive)
            cur.execute("UPDATE churches SET website_scrape_status='found' WHERE website=? AND (website_scrape_status='' OR website_scrape_status IS NULL OR website_scrape_status='pending')", (website,))
            
            # Use COALESCE to never overwrite existing data
            if email:
                cur.execute("UPDATE churches SET email=COALESCE(email,?), email_scrape_status=COALESCE(email_scrape_status,'found') WHERE website=?", (email, website))
                imported += cur.rowcount
            if phone:
                cur.execute("UPDATE churches SET phone=COALESCE(phone,?) WHERE website=? AND (phone='' OR phone IS NULL)", (phone, website))
    
    conn.commit()
    conn.close()
    log(f"  Imported {imported} contacts from {label}")
    return imported

def import_deep_profiles(csv_path, label):
    """Import deep scrape profiles (pastors, service times, ministries, etc.)."""
    if not os.path.exists(csv_path):
        return 0
    conn = sqlite3.connect(DB)
    cur = conn.cursor()
    
    # Add deep profile columns if they don't exist
    new_cols = [
        "pastors", "service_times", "ministries", "languages",
        "online_giving", "attendance", "church_plant",
        "has_youth", "has_children", "has_food_pantry", "has_preschool",
        "facebook", "youtube", "instagram",
        "affiliation", "fb_followers", "yt_subscribers", "yt_videos",
        "budget_indicators", "budget_amount",
    ]
    for col in new_cols:
        try:
            cur.execute(f"ALTER TABLE churches ADD COLUMN {col} TEXT DEFAULT ''")
        except:
            pass
    
    imported = 0
    with open(csv_path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            website = (row.get("website") or "").strip()
            if not website:
                continue
            
            sets = []
            params = []
            for col in new_cols:
                val = row.get(col, "")
                if val:
                    sets.append(f"{col}=?")
                    params.append(str(val))
            
            if sets:
                params.append(website)
                cur.execute(f"UPDATE churches SET {', '.join(sets)} WHERE website=?", params)
                imported += cur.rowcount
    
    conn.commit()
    conn.close()
    log(f"  Updated {imported} churches with deep profiles from {label}")
    return imported

def import_all():
    """Import all synced files."""
    log("Importing into SQLite...")
    total = 0
    
    for fname in sorted(os.listdir(INCOMING)):
        fpath = os.path.join(INCOMING, fname)
        if not os.path.isfile(fpath) or fname.endswith('.imported'):
            continue
        
        log(f"Processing: {fname}")
        
        if "deep_profile" in fname:
            total += import_deep_profiles(fpath, fname)
        elif "scraped" in fname or "scraped_irs" in fname:
            total += import_phase1_csv(fpath, fname)
        elif "found" in fname:
            total += import_found_csv(fpath, fname)
        else:
            log(f"  Unknown format, skipping")
            continue
        
        # Mark as imported
        os.rename(fpath, fpath + ".imported")
    
    log(f"Total records imported/updated: {total}")
    return total

def db_summary():
    """Print database summary."""
    conn = sqlite3.connect(DB)
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM churches")
    total = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM churches WHERE website != '' AND website IS NOT NULL")
    with_web = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM churches WHERE email != '' AND email IS NOT NULL")
    with_email = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM churches WHERE pastors != '' AND pastors IS NOT NULL")
    with_pastor = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM churches WHERE affiliation != '' AND affiliation IS NOT NULL")
    with_affil = cur.fetchone()[0]
    conn.close()
    log(f"\n{'='*50}")
    log(f"Database Summary:")
    log(f"  Total: {total:,}")
    log(f"  With website: {with_web:,}")
    log(f"  With email: {with_email:,}")
    log(f"  With pastor: {with_pastor:,}")
    log(f"  With affiliation: {with_affil:,}")
    log(f"{'='*50}")

if __name__ == "__main__":
    log("Starting sync & import...")
    synced = sync_all()
    if synced:
        log(f"Synced {len(synced)} files")
        import_all()
        db_summary()
    else:
        log("No new files found")
    
    log("Done")
