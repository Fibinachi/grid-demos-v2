"""Process a church email update reply — update DB, CRM, and sent logs."""
import sqlite3, json
from datetime import datetime
from pathlib import Path

OLD = "stannesecretary@comcast.net"
NEW = "stanneukrchurchwarrington@yahoo.com"
NOW = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

db = sqlite3.connect("churches.db")
db.row_factory = sqlite3.Row
c = db.cursor()

# 1. Find the church
c.execute("""SELECT cv.church_id, c.name, c.city, c.state
    FROM church_contact_values cv JOIN churches c ON cv.church_id=c.id
    WHERE cv.contact_type='email' AND cv.value=?""", (OLD,))
row = c.fetchone()
if not row:
    print("Church not found for", OLD)
    db.close()
    exit(1)

church_id = row["church_id"]
print(f"Found: {row['name']} — {row['city']}, {row['state']} (ID #{church_id})")

# 2. Deprecate old email
c.execute("""UPDATE church_contact_values SET confidence=0, is_primary=0
    WHERE church_id=? AND contact_type='email' AND value=?""", (church_id, OLD))
print(f"  Deprecated old email: {c.rowcount} row(s)")

# 3. Insert new email
c.execute("""INSERT INTO church_contact_values
    (church_id, contact_type, value, confidence, source, last_verified, is_primary)
    VALUES (?, 'email', ?, 0.95, 'email_reply_update', ?, 1)""",
    (church_id, NEW, NOW))
print(f"  Inserted: {NEW}")

# 4. Enrichment change log
c.execute("""INSERT INTO enrichment_change_log
    (church_id, field_name, old_value, new_value, change_source, changed_at)
    VALUES (?, 'email', ?, ?, 'email_reply_update', ?)""",
    (church_id, OLD, NEW, NOW))

# 5. Show all contacts for this church
c.execute("""SELECT contact_type, value, is_primary
    FROM church_contact_values WHERE church_id=? ORDER BY contact_type""", (church_id,))
for ct in c.fetchall():
    mark = " [PRIMARY]" if ct["is_primary"] else ""
    print(f"  {ct['contact_type']}: {ct['value']}{mark}")

db.commit()
db.close()

# 6. Update sent logs (avoid re-sending to dead email)
out = Path("outputs/outreach")
for log_name in ["gmail_sent.txt", "church_campaign_sent.txt"]:
    lp = out / log_name
    if lp.exists():
        txt = lp.read_text()
        if OLD.lower() in txt.lower():
            lp.write_text(txt.replace(OLD.lower(), NEW.lower()))
            print(f"Updated {log_name}")

# 7. Update unified queue
qp = out / "unified_queue.jsonl"
if qp.exists():
    try:
        with open(qp, encoding='utf-8', errors='replace') as f:
            lines = f.read().splitlines()
    except:
        with open(qp, encoding='latin-1', errors='replace') as f:
            lines = f.read().splitlines()
    updated = False
    new_lines = []
    for line in lines:
        if OLD.lower() in line.lower():
            line = line.replace(OLD.lower(), NEW.lower())
            updated = True
        new_lines.append(line)
    if updated:
        with open(qp, 'w', encoding='utf-8') as f:
            f.write("\n".join(new_lines) + "\n")
        print("Updated unified_queue.jsonl")
    else:
        print("unified_queue.jsonl: no match (OK)")

# 8. Update CRM
crm_path = out / "sales_crm.db"
if crm_path.exists():
    crm = sqlite3.connect(str(crm_path))
    crm.row_factory = sqlite3.Row
    lead = crm.execute("SELECT id, org_name FROM leads WHERE contact_email=?", (OLD,)).fetchone()
    if lead:
        crm.execute("UPDATE leads SET contact_email=?, updated_at=datetime('now') WHERE id=?",
                    (NEW, lead["id"]))
        crm.execute("""INSERT INTO touch_log (lead_id, touch_type, replied, reply_text, reply_classification)
            VALUES (?, 'reply', 1, 'Email update: old inactive, new provided', 'other')""",
            (lead["id"],))
        crm.execute("""UPDATE leads SET pipeline_stage='engaged',
            replies_received=replies_received+1, last_contacted_at=datetime('now'),
            updated_at=datetime('now') WHERE id=?""", (lead["id"],))
        print(f"CRM: Lead #{lead['id']} ({lead['org_name']}) updated + reply logged")
    else:
        print("CRM: No lead with this email in campaign")
    crm.commit()
    crm.close()

print(f"\n✅ St. Anne Ukrainian Catholic, Warrington PA — email updated to {NEW}")
