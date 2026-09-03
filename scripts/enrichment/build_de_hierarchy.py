#!/usr/bin/env python3
"""
Build German church hierarchy: EKD Landeskirchen + Catholic Dioceses

Maps churches to their respective EKD Landeskirche (20) and Catholic Diocese (27)
using admin1 (Bundesland) + ADM2 (Regierungsbezirk) from church_census_DE.

Creates: ekd_hierarchy, catholic_diocese_de tables
Links: churches -> ekd_hierarchy / catholic_diocese_de via church_id

Authoritative source: German government Zensus 2022 church administrative units,
supplemented by DBK (Catholic Bishops Conference) and EKD official territory maps.
"""
import sqlite3
from datetime import datetime
from pathlib import Path
from collections import Counter

DB = Path(r'E:\grid\churches.db')

# ── EKD Landeskirchen mapping ──
# Key: (admin1_name, adm2_name) -> (landeskirche_name, body, notes)
# Based on official EKD territory maps as of 2026

EKD_MAPPING = {
    # === Baden-Württemberg ===
    ('Baden-Württemberg', 'Stuttgart'):   ('Evangelische Landeskirche in Württemberg', 'EKD', ''),
    ('Baden-Württemberg', 'Tübingen'):    ('Evangelische Landeskirche in Württemberg', 'EKD', ''),
    ('Baden-Württemberg', 'Karlsruhe'):   ('Evangelische Landeskirche in Baden', 'EKD', ''),
    ('Baden-Württemberg', 'Freiburg'):    ('Evangelische Landeskirche in Baden', 'EKD', ''),

    # === Bayern === (all one Landeskirche)
    ('Bayern', 'Oberbayern'):       ('Evangelisch-Lutherische Kirche in Bayern', 'EKD', ''),
    ('Bayern', 'Niederbayern'):     ('Evangelisch-Lutherische Kirche in Bayern', 'EKD', ''),
    ('Bayern', 'Oberpfalz'):        ('Evangelisch-Lutherische Kirche in Bayern', 'EKD', ''),
    ('Bayern', 'Oberfranken'):      ('Evangelisch-Lutherische Kirche in Bayern', 'EKD', ''),
    ('Bayern', 'Mittelfranken'):    ('Evangelisch-Lutherische Kirche in Bayern', 'EKD', ''),
    ('Bayern', 'Unterfranken'):     ('Evangelisch-Lutherische Kirche in Bayern', 'EKD', ''),
    ('Bayern', 'Schwaben'):         ('Evangelisch-Lutherische Kirche in Bayern', 'EKD', ''),

    # === Berlin + Brandenburg ===
    ('Berlin', 'Berlin'):           ('Evangelische Kirche Berlin-Brandenburg-schlesische Oberlausitz', 'EKD', ''),
    ('Brandenburg', 'Brandenburg'): ('Evangelische Kirche Berlin-Brandenburg-schlesische Oberlausitz', 'EKD', ''),

    # === Bremen ===
    ('Bremen', 'Bremen'):           ('Bremische Evangelische Kirche', 'EKD', ''),

    # === Hamburg + Schleswig-Holstein + Mecklenburg-Vorpommern === (Nordkirche)
    ('Hamburg', 'Hamburg'):                         ('Evangelisch-Lutherische Kirche in Norddeutschland', 'EKD', 'Nordkirche'),
    ('Schleswig-Holstein', 'Schleswig-Holstein'):    ('Evangelisch-Lutherische Kirche in Norddeutschland', 'EKD', 'Nordkirche'),
    ('Mecklenburg-Vorpommern', 'Mecklenburg-Vorpommern'): ('Evangelisch-Lutherische Kirche in Norddeutschland', 'EKD', 'Nordkirche'),

    # === Hessen ===
    ('Hessen', 'Darmstadt'):   ('Evangelische Kirche in Hessen und Nassau', 'EKD', ''),
    ('Hessen', 'Gießen'):      ('Evangelische Kirche in Hessen und Nassau', 'EKD', ''),
    ('Hessen', 'Kassel'):      ('Evangelische Kirche von Kurhessen-Waldeck', 'EKD', ''),

    # === Niedersachsen ===
    ('Niedersachsen', 'Hannover'):      ('Evangelisch-lutherische Landeskirche Hannovers', 'EKD', ''),
    ('Niedersachsen', 'Braunschweig'):  ('Evangelisch-lutherische Landeskirche in Braunschweig', 'EKD', ''),
    ('Niedersachsen', 'Lüneburg'):      ('Evangelisch-lutherische Landeskirche Hannovers', 'EKD', ''),
    ('Niedersachsen', 'Weser-Ems'):     ('Evangelisch-Lutherische Kirche in Oldenburg', 'EKD', 'Covers Oldenburg region; also Ev.-reformierte Kirche in NW'),

    # === Nordrhein-Westfalen ===
    ('Nordrhein-Westfalen', 'Düsseldorf'):  ('Evangelische Kirche im Rheinland', 'EKD', ''),
    ('Nordrhein-Westfalen', 'Köln'):        ('Evangelische Kirche im Rheinland', 'EKD', ''),
    ('Nordrhein-Westfalen', 'Münster'):     ('Evangelische Kirche von Westfalen', 'EKD', ''),
    ('Nordrhein-Westfalen', 'Arnsberg'):    ('Evangelische Kirche von Westfalen', 'EKD', ''),
    ('Nordrhein-Westfalen', 'Detmold'):     ('Lippische Landeskirche', 'EKD', 'Lippe region; includes parts in Ev. Kirche von Westfalen'),

    # === Rheinland-Pfalz + Saarland ===
    ('Rheinland-Pfalz', 'Koblenz'):          ('Evangelische Kirche im Rheinland', 'EKD', ''),
    ('Rheinland-Pfalz', 'Trier'):            ('Evangelische Kirche im Rheinland', 'EKD', ''),
    ('Rheinland-Pfalz', 'Rheinhessen-Pfalz'): ('Evangelische Kirche der Pfalz (Protestantische Landeskirche)', 'EKD', ''),
    ('Saarland', 'Saarland'):                ('Evangelische Kirche im Rheinland', 'EKD', ''),

    # === Sachsen ===
    ('Sachsen', 'Dresden'):   ('Evangelisch-Lutherische Landeskirche Sachsens', 'EKD', ''),
    ('Sachsen', 'Chemnitz'):  ('Evangelisch-Lutherische Landeskirche Sachsens', 'EKD', ''),
    ('Sachsen', 'Leipzig'):   ('Evangelisch-Lutherische Landeskirche Sachsens', 'EKD', ''),

    # === Sachsen-Anhalt ===
    ('Sachsen-Anhalt', 'Sachsen-Anhalt'): ('Evangelische Kirche in Mitteldeutschland', 'EKD', 'Most of S-A; small part Braunschweig in west'),

    # === Thüringen ===
    ('Thüringen', 'Thüringen'): ('Evangelische Kirche in Mitteldeutschland', 'EKD', ''),
}

# ── Catholic Diocese mapping ──
# Key: (admin1_name, adm2_name) -> (diocese_name, archdiocese, notes)

CATHOLIC_MAPPING = {
    # === Baden-Württemberg ===
    ('Baden-Württemberg', 'Stuttgart'):  ('Diözese Rottenburg-Stuttgart', 'Erzbistum Freiburg', ''),
    ('Baden-Württemberg', 'Tübingen'):   ('Diözese Rottenburg-Stuttgart', 'Erzbistum Freiburg', ''),
    ('Baden-Württemberg', 'Karlsruhe'):  ('Erzbistum Freiburg', 'Erzbistum Freiburg', ''),
    ('Baden-Württemberg', 'Freiburg'):   ('Erzbistum Freiburg', 'Erzbistum Freiburg', ''),

    # === Bayern ===
    ('Bayern', 'Oberbayern'):       ('Erzbistum München und Freising', 'Erzbistum München und Freising', ''),
    ('Bayern', 'Niederbayern'):     ('Bistum Passau', 'Erzbistum München und Freising', 'Eastern NB; also Bistum Regensburg'),
    ('Bayern', 'Oberpfalz'):        ('Bistum Regensburg', 'Erzbistum München und Freising', ''),
    ('Bayern', 'Oberfranken'):      ('Erzbistum Bamberg', 'Erzbistum Bamberg', ''),
    ('Bayern', 'Mittelfranken'):    ('Erzbistum Bamberg', 'Erzbistum Bamberg', ''),
    ('Bayern', 'Unterfranken'):     ('Bistum Würzburg', 'Erzbistum Bamberg', ''),
    ('Bayern', 'Schwaben'):         ('Bistum Augsburg', 'Erzbistum München und Freising', ''),

    # === Berlin + Brandenburg ===
    ('Berlin', 'Berlin'):           ('Erzbistum Berlin', 'Erzbistum Berlin', ''),
    ('Brandenburg', 'Brandenburg'): ('Erzbistum Berlin', 'Erzbistum Berlin', ''),

    # === Bremen ===
    ('Bremen', 'Bremen'):           ('Bistum Osnabrück', 'Erzbistum Hamburg', 'Bremen south; north is Bistum Hildesheim'),

    # === Hamburg + Schleswig-Holstein + Mecklenburg-Vorpommern ===
    ('Hamburg', 'Hamburg'):                         ('Erzbistum Hamburg', 'Erzbistum Hamburg', ''),
    ('Schleswig-Holstein', 'Schleswig-Holstein'):    ('Erzbistum Hamburg', 'Erzbistum Hamburg', ''),
    ('Mecklenburg-Vorpommern', 'Mecklenburg-Vorpommern'): ('Erzbistum Hamburg', 'Erzbistum Hamburg', ''),

    # === Hessen ===
    ('Hessen', 'Darmstadt'):   ('Bistum Mainz', 'Erzbistum Freiburg', ''),
    ('Hessen', 'Gießen'):      ('Bistum Limburg', 'Erzbistum Köln', ''),
    ('Hessen', 'Kassel'):      ('Bistum Fulda', 'Erzbistum Paderborn', ''),

    # === Niedersachsen ===
    ('Niedersachsen', 'Hannover'):      ('Bistum Hildesheim', 'Erzbistum Hamburg', ''),
    ('Niedersachsen', 'Braunschweig'):  ('Bistum Hildesheim', 'Erzbistum Hamburg', ''),
    ('Niedersachsen', 'Lüneburg'):      ('Bistum Hildesheim', 'Erzbistum Hamburg', ''),
    ('Niedersachsen', 'Weser-Ems'):     ('Bistum Osnabrück', 'Erzbistum Hamburg', 'Western part; also Bistum Münster for south'),

    # === Nordrhein-Westfalen ===
    ('Nordrhein-Westfalen', 'Düsseldorf'):  ('Bistum Essen', 'Erzbistum Köln', 'Ruhr area; also Erzbistum Köln for south'),
    ('Nordrhein-Westfalen', 'Köln'):        ('Erzbistum Köln', 'Erzbistum Köln', ''),
    ('Nordrhein-Westfalen', 'Münster'):     ('Bistum Münster', 'Erzbistum Köln', ''),
    ('Nordrhein-Westfalen', 'Arnsberg'):    ('Erzbistum Paderborn', 'Erzbistum Paderborn', ''),
    ('Nordrhein-Westfalen', 'Detmold'):     ('Erzbistum Paderborn', 'Erzbistum Paderborn', ''),

    # === Rheinland-Pfalz + Saarland ===
    ('Rheinland-Pfalz', 'Koblenz'):          ('Bistum Trier', 'Erzbistum Köln', ''),
    ('Rheinland-Pfalz', 'Trier'):            ('Bistum Trier', 'Erzbistum Köln', ''),
    ('Rheinland-Pfalz', 'Rheinhessen-Pfalz'): ('Bistum Speyer', 'Erzbistum Bamberg', ''),
    ('Saarland', 'Saarland'):                ('Bistum Trier', 'Erzbistum Köln', ''),

    # === Sachsen + Sachsen-Anhalt + Thüringen ===
    ('Sachsen', 'Dresden'):   ('Bistum Dresden-Meißen', 'Erzbistum Berlin', ''),
    ('Sachsen', 'Chemnitz'):  ('Bistum Dresden-Meißen', 'Erzbistum Berlin', ''),
    ('Sachsen', 'Leipzig'):   ('Bistum Dresden-Meißen', 'Erzbistum Berlin', ''),
    ('Sachsen-Anhalt', 'Sachsen-Anhalt'): ('Bistum Magdeburg', 'Erzbistum Paderborn', ''),
    ('Thüringen', 'Thüringen'): ('Bistum Erfurt', 'Erzbistum Paderborn', ''),
}

def main():
    db = sqlite3.connect(str(DB))
    db.execute("PRAGMA journal_mode=WAL")
    c = db.cursor()

    print("GERMAN CHURCH HIERARCHY: EKD + CATHOLIC")
    print("=" * 60)

    # ── Build lookup from church_census_DE ──
    print("\nLoading ADM2 assignments from church_census_DE...")

    # Get admin1_name + adm2_name for each church
    c.execute("""
        SELECT c.rowid, c.admin1_name, cen.dist_name
        FROM churches c
        JOIN church_census_DE cen ON cen.church_rowid = c.rowid
        WHERE c.country = 'DE'
    """)
    church_adm2 = {}
    for row in c.fetchall():
        church_adm2[row[0]] = (row[1], row[2])

    print(f"  {len(church_adm2):,} churches with ADM2 mapping")

    # ── Create EKD hierarchy table ──
    print("\n── EKD Landeskirchen ──")
    c.execute("DROP TABLE IF EXISTS ekd_hierarchy_de")
    c.execute("""
        CREATE TABLE ekd_hierarchy_de (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            church_id INTEGER REFERENCES churches(id) ON DELETE CASCADE,
            landeskirche TEXT NOT NULL,
            body TEXT DEFAULT 'EKD',
            admin1_name TEXT,
            adm2_name TEXT,
            mapping_source TEXT DEFAULT 'adm2_manual',
            notes TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            UNIQUE(church_id)
        )
    """)

    ekd_counts = Counter()
    inserted = 0
    unmatched = 0

    for church_rowid, (admin1, adm2) in church_adm2.items():
        key = (admin1, adm2)
        if key in EKD_MAPPING:
            landeskirche, body, notes = EKD_MAPPING[key]
            c.execute("""
                INSERT OR IGNORE INTO ekd_hierarchy_de (church_id, landeskirche, body, admin1_name, adm2_name, notes)
                VALUES ((SELECT id FROM churches WHERE rowid=?), ?, ?, ?, ?, ?)
            """, (church_rowid, landeskirche, body, admin1, adm2, notes))
            inserted += c.rowcount
            ekd_counts[landeskirche] += 1
        else:
            unmatched += 1

    print(f"  Inserted: {inserted:,}")
    print(f"  Unmatched: {unmatched}")
    print(f"  Landeskirchen distribution:")
    for name, cnt in ekd_counts.most_common():
        print(f"    {name}: {cnt:,}")

    # ── Create Catholic Diocese table ──
    print("\n── Catholic Dioceses ──")
    c.execute("DROP TABLE IF EXISTS catholic_diocese_de")
    c.execute("""
        CREATE TABLE catholic_diocese_de (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            church_id INTEGER REFERENCES churches(id) ON DELETE CASCADE,
            diocese TEXT NOT NULL,
            archdiocese TEXT,
            admin1_name TEXT,
            adm2_name TEXT,
            mapping_source TEXT DEFAULT 'adm2_manual',
            notes TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            UNIQUE(church_id)
        )
    """)

    cath_counts = Counter()
    inserted_c = 0
    unmatched_c = 0

    for church_rowid, (admin1, adm2) in church_adm2.items():
        key = (admin1, adm2)
        if key in CATHOLIC_MAPPING:
            diocese, archdiocese, notes = CATHOLIC_MAPPING[key]
            c.execute("""
                INSERT OR IGNORE INTO catholic_diocese_de (church_id, diocese, archdiocese, admin1_name, adm2_name, notes)
                VALUES ((SELECT id FROM churches WHERE rowid=?), ?, ?, ?, ?, ?)
            """, (church_rowid, diocese, archdiocese, admin1, adm2, notes))
            inserted_c += c.rowcount
            cath_counts[diocese] += 1
        else:
            unmatched_c += 1

    print(f"  Inserted: {inserted_c:,}")
    print(f"  Unmatched: {unmatched_c}")
    print(f"  Diocese distribution:")
    for name, cnt in cath_counts.most_common():
        print(f"    {name}: {cnt:,}")

    # ── Summary ──
    print(f"\n{'='*60}")
    print(f"SUMMARY")
    print(f"{'='*60}")
    print(f"  EKD hierarchy: {inserted:,} churches → {len(ekd_counts)} Landeskirchen")
    print(f"  Catholic hierarchy: {inserted_c:,} churches → {len(cath_counts)} dioceses")

    # ── Update church census catalog ──
    c.execute("""
        INSERT OR REPLACE INTO church_census_catalog (country, table_name, category, description, geo_unit, row_count, source_date)
        VALUES ('DE', 'ekd_hierarchy_de', 'hierarchy', 'EKD Landeskirche per church via ADM2 mapping', 'Landeskirche', ?, '2026-07-08')
    """, (inserted,))
    c.execute("""
        INSERT OR REPLACE INTO church_census_catalog (country, table_name, category, description, geo_unit, row_count, source_date)
        VALUES ('DE', 'catholic_diocese_de', 'hierarchy', 'Catholic diocese per church via ADM2 mapping', 'diocese', ?, '2026-07-08')
    """, (inserted_c,))

    db.commit()
    db.close()
    print("\nDone.")

if __name__ == '__main__':
    main()
