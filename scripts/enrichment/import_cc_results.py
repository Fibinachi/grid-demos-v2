#!/usr/bin/env python3
"""
Import Common Crawl results into the DB with provenance tracking.

Usage:
    python scripts/enrichment/import_cc_results.py --csv cc_results.csv
"""
import csv, json, sqlite3, sys, os

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
for _ in range(5):
    if os.path.exists(os.path.join(PROJECT_DIR, "churches.db")):
        break
    parent = os.path.dirname(PROJECT_DIR)
    if parent == PROJECT_DIR:
        break
    PROJECT_DIR = parent

DB_PATH = os.path.join(PROJECT_DIR, "churches.db")

def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", required=True, help="CC results CSV")
    parser.add_argument("--db", default=DB_PATH, help="DB path")
    parser.add_argument("--log-id", type=int, default=None, 
                        help="provenance_log id to update (auto-create if not set)")
    parser.add_argument("--source-label", default="common_crawl", 
                        help="Source label for provenance")
    args = parser.parse_args()
    
    if not os.path.exists(args.csv):
        print(f"CSV not found: {args.csv}")
        return
    
    db = sqlite3.connect(args.db)
    
    # Start provenance log entry
    log_id = args.log_id
    if not log_id:
        db.execute("""
            INSERT INTO provenance_log 
                (source, script_name, started_at, fields_populated, parameters, status)
            VALUES (?, 'import_cc_results.py', datetime('now'), 'website,phone,email,social,people', ?, 'importing')
        """, (args.source_label, json.dumps({"csv": args.csv})))
        log_id = db.lastrowid
        db.commit()
    
    print(f"Provenance log ID: {log_id}")
    
    # Read CSV
    updates = 0
    new_websites = 0
    people_found = 0
    emails_found = 0
    
    with open(args.csv, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            church_id = row.get("id", "").strip()
            domain = row.get("cc_domain", "").strip()
            url = row.get("cc_url", "").strip()
            page_title = row.get("cc_page_title", "").strip()
            verified = int(row.get("cc_verified", 0))
            confidence = float(row.get("cc_confidence", 0))
            emails = row.get("cc_emails", "").strip()
            phones = row.get("cc_phones", "").strip()
            social = row.get("cc_social", "").strip()
            people_names = row.get("cc_people_names", "").strip()
            live_url = row.get("live_url", "").strip()
            
            if not church_id:
                continue
            
            # Determine what we found
            website = url or live_url
            if not website and domain:
                website = f"https://{domain}"
            
            if not website:
                continue
            
            # Build UPDATE
            parts = []
            params = []
            
            if confidence >= 60:
                # Verified - use the URL
                parts.append("website=?")
                params.append(website)
                parts.append("website_scrape_status='verified'")
                parts.append("website_confidence=?")
                params.append(confidence / 100.0)
                parts.append("website_last_verified=datetime('now')")
                parts.append("website_source='common_crawl'")
                new_websites += 1
            elif confidence > 0:
                # Partial match
                parts.append("website=?")
                params.append(website)
                parts.append("website_scrape_status='found'")
                parts.append("website_confidence=?")
                params.append(confidence / 100.0)
                parts.append("website_source='common_crawl'")
                new_websites += 1
            elif live_url:
                # Live but unverified
                parts.append("website=?")
                params.append(live_url)
                parts.append("website_scrape_status='found'")
                parts.append("website_confidence=0.3")
                parts.append("website_source='common_crawl'")
                new_websites += 1
            else:
                continue
            
            # Emails
            if emails:
                email_list = [e.strip() for e in emails.replace("mailto:", "").split(";")]
                valid_emails = [e for e in email_list if "@" in e]
                if valid_emails:
                    existing = db.execute(
                        "SELECT email FROM churches WHERE id=?", (church_id,)
                    ).fetchone()
                    if existing and existing[0]:
                        current = existing[0]
                        new = "; ".join(valid_emails)
                        if new not in current:
                            parts.append("email=CASE WHEN email='' OR email IS NULL THEN ? ELSE email||'; '||? END")
                            params.extend([new, new])
                    else:
                        parts.append("email=?")
                        params.append("; ".join(valid_emails[:3]))
                    parts.append("email_scrape_status='found'")
                    parts.append("email_source='common_crawl'")
                    emails_found += len(valid_emails)
            
            # Phones
            if phones:
                parts.append("phone=?")
                params.append(phones)
                parts.append("phone_source='common_crawl'")
            
            # Social links
            if social:
                for s_item in social.split("; "):
                    s_item = s_item.strip()
                    if ":" in s_item:
                        stype, surl = s_item.split(":", 1)
                        if stype == "facebook" and surl:
                            parts.append("facebook_url=?")
                            params.append(surl)
                        elif stype == "instagram" and surl:
                            parts.append("instagram_url=?")
                            params.append(surl)
                        elif stype == "youtube" and surl:
                            parts.append("youtube_url=?")
                            params.append(surl)
            
            # People names
            if people_names:
                # Store in notes field
                existing = db.execute(
                    "SELECT notes FROM churches WHERE id=?", (church_id,)
                ).fetchone()
                note_line = f"[CC People: {people_names}]"
                if existing and existing[0]:
                    if note_line not in existing[0]:
                        parts.append("notes=CASE WHEN notes='' OR notes IS NULL THEN ? ELSE notes||'\n'||? END")
                        params.extend([note_line, note_line])
                else:
                    parts.append("notes=?")
                    params.append(note_line)
                people_found += 1
            
            params.append(church_id)
            db.execute(f"UPDATE churches SET {', '.join(parts)} WHERE id=?", params)
            updates += 1
            
            if updates % 500 == 0:
                db.commit()
                print(f"  {updates:,} updates so far...")
    
    db.commit()
    
    # Update provenance log
    db.execute("""
        UPDATE provenance_log SET 
            completed_at=datetime('now'),
            churches_updated=?,
            fields_populated=?,
            status='completed',
            notes=?
        WHERE id=?
    """, (updates, f"website({new_websites}),email({emails_found}),people({people_found})",
          f"CC enrichment import: {updates} churches updated, {new_websites} new websites, {people_found} with people names, {emails_found} emails", 
          log_id))
    db.commit()
    
    # Final stats
    w = db.execute("SELECT COUNT(*) FROM churches WHERE website IS NOT NULL AND website != ''").fetchone()[0]
    v = db.execute("SELECT COUNT(*) FROM churches WHERE website_scrape_status='verified'").fetchone()[0]
    t = db.execute("SELECT COUNT(*) FROM churches").fetchone()[0]
    
    print(f"\n{'='*50}")
    print(f"IMPORT COMPLETE")
    print(f"{'='*50}")
    print(f"  Churches updated: {updates:,}")
    print(f"  New websites added: {new_websites:,}")
    print(f"  Emails found: {emails_found:,}")
    print(f"  Churches with people named: {people_found:,}")
    print(f"  Provenance log ID: {log_id}")
    print(f"\nDB totals: {t:,} churches, {w:,} websites ({v:,} verified)")
    
    db.close()


if __name__ == "__main__":
    main()
