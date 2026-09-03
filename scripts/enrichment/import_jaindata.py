"""
Import jaindata.com RSS feeds into churches.db.
Sources:
  /jain_temple/RSS.aspx  — 185 temples with GPS
  /jain_paathshala/RSS.aspx — 141 religious schools
  /jain_swadhyay/RSS.aspx  — 6 study groups
"""
import requests, re, json, time
from pathlib import Path
from bs4 import BeautifulSoup
import sqlite3
from datetime import datetime

BASE = "https://www.jaindata.com"
H = {"User-Agent": "Mozilla/5.0"}
DB = "churches.db"
OUT = Path("data/jainmandir")
OUT.mkdir(parents=True, exist_ok=True)

def extract_gps(text):
    """Find GPS coordinates like 12.980933, 80.198776 in text."""
    coords = re.findall(r"(-?\d+\.\d+),\s*(-?\d+\.\d+)", text)
    if coords:
        lat, lon = float(coords[0][0]), float(coords[0][1])
        if -90 <= lat <= 90 and -180 <= lon <= 180:
            return lat, lon
    return None, None

def extract_email_phone(text):
    """Extract email and phone from text."""
    emails = re.findall(r"[\w.+-]+@[\w-]+\.[\w.-]+", text)
    phones = re.findall(r"(?:\+?\d{1,3}[-.\s]?)?\(?\d{3,5}\)?[-.\s]?\d{3}[-.\s]?\d{4}", text)
    return emails[0] if emails else "", phones[0] if phones else ""

def fetch_rss(name, path, category, landmark_type):
    """Fetch an RSS feed, parse items, insert into DB."""
    print(f"\n=== {name} ===")
    r = requests.get(f"{BASE}/{path}", headers=H, timeout=30)
    if r.status_code != 200:
        print(f"  FAILED: {r.status_code}")
        return []
    
    soup = BeautifulSoup(r.text, "xml")
    items = soup.find_all("item")
    print(f"  RSS items: {len(items)}")
    
    # Save raw RSS
    with open(OUT / f"{name.lower().replace(' ','_')}_rss.xml", "w", encoding="utf-8") as f:
        f.write(r.text)
    
    db = sqlite3.connect(DB)
    inserted = skipped = 0
    
    for item in items:
        title = item.find("title")
        desc = item.find("description")
        link = item.find("link")
        
        title_text = title.text.strip() if title else ""
        desc_text = desc.text.strip() if desc else ""
        link_text = link.text.strip() if link else ""
        
        # Extract GPS from description
        lat, lon = extract_gps(desc_text)
        
        # Extract address - everything before GPS or the description itself
        address = re.sub(r'\s*\(\d+\.\d+,\s*\d+\.\d+\)\s*', '', desc_text).strip()
        
        # Extract email and phone
        email, phone = extract_email_phone(desc_text)
        
        # Check if already exists by name (unique enough from RSS)
        existing = db.execute(
            "SELECT id FROM churches WHERE source='jaindata' AND name=?",
            (title_text[:500],)
        ).fetchone()
        
        if existing:
            # Update existing record with contact info
            if email:
                db.execute("INSERT OR IGNORE INTO church_contact_values (church_id, contact_type, value, source) VALUES (?, 'email', ?, 'jaindata')", (existing[0], email))
            if phone:
                db.execute("INSERT OR IGNORE INTO church_contact_values (church_id, contact_type, value, source) VALUES (?, 'phone', ?, 'jaindata')", (existing[0], phone))
            skipped += 1
            continue
        
        if not lat or not lon:
            skipped += 1
            continue
        
        # Insert
        db.execute("""INSERT INTO churches 
            (name, faith, tradition, latitude, longitude, country, source, landmark_type)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (title_text[:500], "Jain", "Jain", lat, lon, "IN", "jaindata", landmark_type))
        
        church_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
        
        # Add contact info
        if email:
            db.execute("INSERT INTO church_contact_values (church_id, contact_type, value, source) VALUES (?, 'email', ?, 'jaindata')", (church_id, email))
        if phone:
            db.execute("INSERT INTO church_contact_values (church_id, contact_type, value, source) VALUES (?, 'phone', ?, 'jaindata')", (church_id, phone))
        
        inserted += 1
    
    db.commit()
    db.close()
    print(f"  Inserted: {inserted}, Skipped: {skipped}")
    return {"name": name, "inserted": inserted, "skipped": skipped, "total": len(items)}

# Run all imports
results = []
results.append(fetch_rss("Jain Temples", "jain_temple/RSS.aspx", "Jain", "temple"))
results.append(fetch_rss("Jain Paathshalas", "jain_paathshala/RSS.aspx", "Jain", "school"))
results.append(fetch_rss("Jain Swadhyay", "jain_swadhyay/RSS.aspx", "Jain", "study_group"))

# Summary
print(f"\n{'='*60}")
print(f"IMPORT SUMMARY")
print(f"{'='*60}")
total_ins = sum(r["inserted"] for r in results)
total_skipped = sum(r["skipped"] for r in results)
for r in results:
    print(f"  {r['name']:20s} {r['inserted']:4d} new, {r['skipped']:4d} skipped")
print(f"{'─'*60}")
print(f"  Total: {total_ins} new, {total_skipped} skipped")

# Final Jain count
db = sqlite3.connect(DB)
jain_total = db.execute("SELECT COUNT(*) FROM churches WHERE faith='Jain'").fetchone()[0]
db.close()
print(f"  Jain entries in DB now: {jain_total}")
