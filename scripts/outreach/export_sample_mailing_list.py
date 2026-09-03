"""
Export sample mailing list for josh@infofreeleads.com
- 1,000 US fully mailable addresses (random sample)
- 250 Canada fully mailable addresses (random sample)
- Plus a quality summary for the entire US set
"""
import sqlite3
import csv
import random
from pathlib import Path
from datetime import datetime

DB_PATH = Path("E:/grid/churches.db")
OUT_DIR = Path("E:/grid/outputs/outreach")
OUT_DIR.mkdir(parents=True, exist_ok=True)
TIMESTAMP = datetime.now().strftime("%Y%m%d_%H%M%S")

# USPS state name → code mapping for normalization
STATE_NAME_TO_CODE = {
    "Alabama": "AL", "Alaska": "AK", "Arizona": "AZ", "Arkansas": "AR",
    "California": "CA", "Colorado": "CO", "Connecticut": "CT", "Delaware": "DE",
    "Florida": "FL", "Georgia": "GA", "Hawaii": "HI", "Idaho": "ID",
    "Illinois": "IL", "Indiana": "IN", "Iowa": "IA", "Kansas": "KS",
    "Kentucky": "KY", "Louisiana": "LA", "Maine": "ME", "Maryland": "MD",
    "Massachusetts": "MA", "Michigan": "MI", "Minnesota": "MN", "Mississippi": "MS",
    "Missouri": "MO", "Montana": "MT", "Nebraska": "NE", "Nevada": "NV",
    "New Hampshire": "NH", "New Jersey": "NJ", "New Mexico": "NM", "New York": "NY",
    "North Carolina": "NC", "North Dakota": "ND", "Ohio": "OH", "Oklahoma": "OK",
    "Oregon": "OR", "Pennsylvania": "PA", "Rhode Island": "RI", "South Carolina": "SC",
    "South Dakota": "SD", "Tennessee": "TN", "Texas": "TX", "Utah": "UT",
    "Vermont": "VT", "Virginia": "VA", "Washington": "WA", "West Virginia": "WV",
    "Wisconsin": "WI", "Wyoming": "WY",
    "District of Columbia": "DC", "Puerto Rico": "PR",
    "American Samoa": "AS", "Guam": "GU", "Northern Mariana Islands": "MP",
    "U.S. Virgin Islands": "VI",
}

VALID_US_STATES_CODES = set(STATE_NAME_TO_CODE.values())
VALID_US_STATES_CODES.update({"DC", "PR", "AS", "GU", "MP", "VI", "AE", "AP", "AA", "MH", "PW", "FM"})
VALID_CA_PROVINCES = {"AB", "BC", "MB", "NB", "NL", "NS", "NT", "NU", "ON", "PE", "QC", "SK", "YT"}


def normalize_state(raw: str) -> str:
    """Normalize a state field: full name → code, or return 2-letter code as-is."""
    if not raw:
        return ""
    raw = raw.strip()
    if raw in STATE_NAME_TO_CODE:
        return STATE_NAME_TO_CODE[raw]
    if len(raw) == 2 and raw.isalpha():
        return raw.upper()
    return raw


def main():
    db = sqlite3.connect(str(DB_PATH))
    db.row_factory = sqlite3.Row
    cur = db.cursor()

    # ── US: fully mailable query ──
    cur.execute("""
        SELECT id, name, address, city, state, zip, zip5, country,
               faith, landmark_type, latitude, longitude, source
        FROM churches
        WHERE country = 'US'
          AND address IS NOT NULL AND address != ''
          AND city IS NOT NULL AND city != ''
          AND state IS NOT NULL AND state != ''
          AND (zip5 IS NOT NULL AND zip5 != '' OR zip IS NOT NULL AND zip != '')
    """)
    all_us = cur.fetchall()
    print(f"US fully mailable (raw): {len(all_us):,}")

    # Filter: only valid US state codes (after normalization)
    us_filtered = []
    us_skipped_bad_state = 0
    us_skipped_po_box = 0
    for r in all_us:
        s = normalize_state(r["state"])
        if s not in VALID_US_STATES_CODES:
            us_skipped_bad_state += 1
            continue
        # Optionally skip PO Boxes for physical mailing? No — PO Box is a valid mailing address.
        # But let's flag them.
        r_dict = dict(r)
        r_dict["state_norm"] = s
        r_dict["zip_code"] = r["zip5"] or r["zip"]
        r_dict["is_po_box"] = 1 if r["address"] and "PO Box" in r["address"] else 0
        us_filtered.append(r_dict)

    print(f"After state filter: {len(us_filtered):,} (skipped {us_skipped_bad_state} bad state)")
    po_boxes = sum(1 for r in us_filtered if r["is_po_box"])
    print(f"PO Box addresses: {po_boxes:,} ({po_boxes/len(us_filtered)*100:.1f}%)")

    # Random sample 1,000
    random.seed(42)
    us_sample = random.sample(us_filtered, min(1000, len(us_filtered)))

    # ── Canada: fully mailable query ──
    cur.execute("""
        SELECT id, name, address, city, state, zip, zip5, country,
               faith, landmark_type, latitude, longitude, source
        FROM churches
        WHERE country = 'CA'
          AND address IS NOT NULL AND address != ''
          AND city IS NOT NULL AND city != ''
          AND state IS NOT NULL AND state != ''
          AND (zip5 IS NOT NULL AND zip5 != '' OR zip IS NOT NULL AND zip != '')
    """)
    all_ca = cur.fetchall()
    print(f"\nCA fully mailable (raw): {len(all_ca):,}")

    ca_filtered = []
    ca_skipped_bad_province = 0
    for r in all_ca:
        s = normalize_state(r["state"])
        if s not in VALID_CA_PROVINCES:
            ca_skipped_bad_province += 1
            continue
        r_dict = dict(r)
        r_dict["state_norm"] = s
        r_dict["zip_code"] = r["zip5"] or r["zip"]
        r_dict["is_po_box"] = 1 if r["address"] and "PO Box" in r["address"] else 0
        ca_filtered.append(r_dict)

    print(f"After province filter: {len(ca_filtered):,} (skipped {ca_skipped_bad_province} bad)")
    ca_po = sum(1 for r in ca_filtered if r["is_po_box"])
    print(f"PO Box addresses: {ca_po:,} ({ca_po/len(ca_filtered)*100:.1f}%)")

    ca_sample = random.sample(ca_filtered, min(250, len(ca_filtered)))

    # ── Export CSV ──
    csv_path = OUT_DIR / f"sample_mailing_list_{TIMESTAMP}.csv"
    fields = ["id", "name", "address", "city", "state_norm", "zip_code", "country",
              "faith", "landmark_type", "is_po_box", "latitude", "longitude", "source"]
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        for r in us_sample:
            w.writerow(r)
        for r in ca_sample:
            w.writerow(r)

    print(f"\n✅ Exported {len(us_sample)} US + {len(ca_sample)} CA = {len(us_sample)+len(ca_sample)} total")
    print(f"   → {csv_path}")

    # ── Quality Summary ──
    summary_path = OUT_DIR / f"us_quality_summary_{TIMESTAMP}.txt"
    lines = []
    lines.append("=" * 60)
    lines.append("GRID — US Mailing List Quality Summary")
    lines.append(f"Generated: {datetime.now().isoformat()}")
    lines.append("=" * 60)
    lines.append("")

    # Total US
    cur.execute("SELECT COUNT(*) FROM churches WHERE country = 'US'")
    total_us = cur.fetchone()[0]

    # By field
    cur.execute("""
        SELECT
            COUNT(*) as total,
            SUM(CASE WHEN address IS NOT NULL AND address != '' THEN 1 ELSE 0 END) as addr,
            SUM(CASE WHEN city IS NOT NULL AND city != '' THEN 1 ELSE 0 END) as city_ok,
            SUM(CASE WHEN state IS NOT NULL AND state != '' THEN 1 ELSE 0 END) as state_ok,
            SUM(CASE WHEN zip5 IS NOT NULL AND zip5 != '' THEN 1 ELSE 0 END) as zip5_ok,
            SUM(CASE WHEN zip IS NOT NULL AND zip != '' THEN 1 ELSE 0 END) as zip_ok
        FROM churches WHERE country = 'US'
    """)
    r = cur.fetchone()
    lines.append(f"Total US Records: {total_us:,}")
    lines.append(f"  Street Address: {r['addr']:>10,}  ({r['addr']/total_us*100:.1f}%)")
    lines.append(f"  City:           {r['city_ok']:>10,}  ({r['city_ok']/total_us*100:.1f}%)")
    lines.append(f"  State:          {r['state_ok']:>10,}  ({r['state_ok']/total_us*100:.1f}%)")
    lines.append(f"  ZIP5:           {r['zip5_ok']:>10,}  ({r['zip5_ok']/total_us*100:.1f}%)")
    lines.append(f"  ZIP (any):      {r['zip_ok']:>10,}  ({r['zip_ok']/total_us*100:.1f}%)")
    lines.append(f"  FULLY MAILABLE: {len(us_filtered):>10,}  ({len(us_filtered)/total_us*100:.1f}%)")
    lines.append("")

    # PO Box breakdown
    lines.append(f"PO Box Addresses: {po_boxes:,} ({po_boxes/len(us_filtered)*100:.1f}% of mailable)")
    lines.append(f"Street Addresses: {len(us_filtered)-po_boxes:,} ({(len(us_filtered)-po_boxes)/len(us_filtered)*100:.1f}% of mailable)")
    lines.append("")

    # By faith
    cur.execute("""
        SELECT COALESCE(faith, 'Unknown') as faith, COUNT(*) as cnt
        FROM churches WHERE country = 'US'
          AND address IS NOT NULL AND address != ''
          AND city IS NOT NULL AND city != ''
          AND state IS NOT NULL AND state != ''
          AND (zip5 IS NOT NULL AND zip5 != '' OR zip IS NOT NULL AND zip != '')
        GROUP BY faith ORDER BY cnt DESC
    """)
    lines.append("BY FAITH (fully mailable US):")
    for row in cur.fetchall():
        lines.append(f"  {row['faith']:25s} {row['cnt']:>10,}")
    lines.append("")

    # By state (top + bottom)
    cur.execute("""
        SELECT state, COUNT(*) as cnt
        FROM churches WHERE country = 'US'
          AND address IS NOT NULL AND address != ''
          AND city IS NOT NULL AND city != ''
          AND state IS NOT NULL AND state != ''
          AND (zip5 IS NOT NULL AND zip5 != '' OR zip IS NOT NULL AND zip != '')
        GROUP BY state ORDER BY cnt DESC
    """)
    states = cur.fetchall()
    lines.append(f"BY STATE (all {len(states)} entries, fully mailable US, raw state values):")
    for row in states:
        norm = normalize_state(row["state"])
        flag = " ⚠" if norm not in VALID_US_STATES_CODES else ""
        lines.append(f"  {row['state']:25s} → {norm:4s}  {row['cnt']:>10,}{flag}")
    lines.append("")

    # Contact availability
    cur.execute("""
        SELECT COUNT(DISTINCT cv.church_id)
        FROM church_contact_values cv
        JOIN churches c ON cv.church_id = c.id
        WHERE c.country = 'US'
          AND c.address IS NOT NULL AND c.address != ''
          AND c.city IS NOT NULL AND c.city != ''
          AND c.state IS NOT NULL AND c.state != ''
          AND (c.zip5 IS NOT NULL AND c.zip5 != '' OR c.zip IS NOT NULL AND c.zip != '')
          AND cv.contact_type = 'email'
    """)
    with_email = cur.fetchone()[0]
    cur.execute("""
        SELECT COUNT(DISTINCT cv.church_id)
        FROM church_contact_values cv
        JOIN churches c ON cv.church_id = c.id
        WHERE c.country = 'US'
          AND c.address IS NOT NULL AND c.address != ''
          AND c.city IS NOT NULL AND c.city != ''
          AND c.state IS NOT NULL AND c.state != ''
          AND (c.zip5 IS NOT NULL AND c.zip5 != '' OR c.zip IS NOT NULL AND c.zip != '')
          AND cv.contact_type = 'phone'
    """)
    with_phone = cur.fetchone()[0]
    lines.append(f"Contact Availability (among {len(us_filtered):,} fully mailable US):")
    lines.append(f"  With Email: {with_email:>10,}  ({with_email/len(us_filtered)*100:.1f}%)")
    lines.append(f"  With Phone: {with_phone:>10,}  ({with_phone/len(us_filtered)*100:.1f}%)")

    # Write summary
    summary_text = "\n".join(lines)
    with open(summary_path, "w", encoding="utf-8") as f:
        f.write(summary_text)
    print(f"\n✅ Quality summary: {summary_path}")
    print()
    print(summary_text)

    db.close()


if __name__ == "__main__":
    main()
