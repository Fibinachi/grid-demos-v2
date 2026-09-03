#!/usr/bin/env python3
"""
Backfill missing landmark_type, taxonomy_id, and tradition via simple rules.
Runs in seconds. Logs to provenance.
"""
import sqlite3, json
from datetime import datetime

DB = "churches.db"

def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")

def run_backfill():
    db = sqlite3.connect(DB)
    c = db.cursor()
    total_fixes = 0

    # ── 1. LANDMARK_TYPE by faith ──
    log("=== LANDMARK_TYPE BACKFILL ===")
    faith_to_landmark = {
        "Christian": "church",
        "Islam": "mosque",
        "Hindu": "temple",
        "Buddhist": "temple",
        "Judaism": "synagogue",
        "Sikh": "gurdwara",
        "Shinto": "shrine",
        "Jain": "temple",
        "Taoist": "temple",
        "Confucian": "temple",
        "Bah\u00e1\u02bc\u00ed": "center",
        "Eastern Orthodox": "church",
    }
    for faith, ltype in faith_to_landmark.items():
        c.execute("""UPDATE churches SET landmark_type=?
                     WHERE (landmark_type IS NULL OR landmark_type='')
                       AND faith=?""", (ltype, faith))
        n = c.rowcount
        if n:
            log(f"  {faith}: {n:,} -> {ltype}")
            total_fixes += n
    db.commit()

    # ── 2. TAXONOMY_ID backfill ──
    log("\n=== TAXONOMY_ID BACKFILL ===")
    # Faith -> default taxonomy_id
    faith_tax = {
        "Christian": 2, "Islam": 4, "Hindu": 3, "Buddhist": 5,
        "Judaism": 8, "Sikh": 239, "Shinto": 228, "Jain": 236,
        "Taoist": 233, "Confucian": 235, "Other": 6,
        "Bah\u00e1\u02bc\u00ed": 42, "Eastern Orthodox": 2,
    }
    for faith, tid in faith_tax.items():
        c.execute("""UPDATE churches SET taxonomy_id=?
                     WHERE taxonomy_id IS NULL AND faith=?""", (tid, faith))
        n = c.rowcount
        if n:
            log(f"  {faith}: {n:,} -> tax_id={tid}")
            total_fixes += n
    db.commit()

    # ── 3. TRADITION backfill for non-Christian faiths ──
    log("\n=== TRADITION BACKFILL (non-Christian) ===")
    faith_default_trad = {
        "Islam": "Muslim",
        "Hindu": "Hindu",
        "Buddhist": "Buddhist",
        "Judaism": "Jewish",
        "Sikh": "Sikh",
        "Shinto": "Shrine Shinto",
        "Jain": "Jain",
        "Taoist": "Taoist",
        "Confucian": "Confucian",
        "Other": "Other",
        "Bah\u00e1\u02bc\u00ed": "Bah\u00e1\u02bc\u00ed",
        "Eastern Orthodox": "Eastern Orthodox",
    }
    for faith, trad in faith_default_trad.items():
        c.execute("""UPDATE churches SET tradition=?
                     WHERE (tradition IS NULL OR tradition='')
                       AND faith=?""", (trad, faith))
        n = c.rowcount
        if n:
            log(f"  {faith}: {n:,} -> {trad}")
            total_fixes += n
    db.commit()

    # ── 4. Christian tradition via country priors ──
    log("\n=== CHRISTIAN TRADITION (country priors) ===")
    # Country -> dominant Christian tradition
    country_trad = {
        "GB": "Anglican", "CA": "Catholic", "MX": "Catholic",
        "BR": "Catholic", "IT": "Catholic", "ES": "Catholic",
        "FR": "Catholic", "PL": "Catholic", "IE": "Catholic",
        "AT": "Catholic", "PT": "Catholic", "HR": "Catholic",
        "LT": "Catholic", "SK": "Catholic", "SI": "Catholic",
        "BE": "Catholic", "HU": "Catholic", "CZ": "Catholic",
        "DE": "Protestant", "SE": "Protestant", "NO": "Protestant",
        "DK": "Protestant", "FI": "Protestant", "NL": "Protestant",
        "CH": "Protestant", "LV": "Protestant", "EE": "Protestant",
        "IS": "Protestant", "GR": "Eastern Orthodox",
        "RU": "Eastern Orthodox", "UA": "Eastern Orthodox",
        "RO": "Eastern Orthodox", "BG": "Eastern Orthodox",
        "RS": "Eastern Orthodox", "MK": "Eastern Orthodox",
        "GE": "Eastern Orthodox", "MD": "Eastern Orthodox",
        "PH": "Catholic", "AR": "Catholic", "CL": "Catholic",
        "CO": "Catholic", "PE": "Catholic", "VE": "Catholic",
        "EC": "Catholic", "BO": "Catholic", "PY": "Catholic",
        "UY": "Catholic", "ZA": "Protestant", "AU": "Protestant",
        "NZ": "Protestant", "KE": "Protestant", "NG": "Protestant",
        "GH": "Protestant", "UG": "Protestant", "TZ": "Protestant",
    }
    for country, trad in country_trad.items():
        c.execute("""UPDATE churches SET tradition=?
                     WHERE (tradition IS NULL OR tradition='')
                       AND faith='Christian' AND country=?""", (trad, country))
        n = c.rowcount
        if n:
            log(f"  {country}: {n:,} -> {trad}")
            total_fixes += n
    db.commit()

    # ── 5. Christian via name keywords ──
    log("\n=== CHRISTIAN TRADITION (name keywords) ===")
    name_trads = [
        ("%catholic%", "Catholic"),
        ("%baptist%", "Baptist"),
        ("%methodist%", "Methodist"),
        ("%lutheran%", "Lutheran"),
        ("%presbyterian%", "Presbyterian"),
        ("%pentecostal%", "Pentecostal"),
        ("%orthodox%", "Eastern Orthodox"),
        ("%anglican%", "Anglican"),
        ("%episcopal%", "Anglican"),
        ("%evangelical%", "Evangelical"),
        ("%mormon%", "Latter-day Saints"),
        ("%latter%day%", "Latter-day Saints"),
        ("%adventist%", "Adventist"),
        ("%nazarene%", "Holiness"),
        ("%assembly%of%god%", "Pentecostal"),
        ("%church%of%god%", "Pentecostal"),
        ("%church%of%christ%", "Restorationist"),
        ("%congregational%", "Congregational"),
        ("%mennonite%", "Anabaptist"),
        ("%reformed%", "Reformed"),
        ("%salvation%army%", "Holiness"),
        ("%jehovah%", "Jehovah's Witnesses"),
        ("%wesleyan%", "Methodist"),
        ("%united%methodist%", "Methodist"),
        ("%ame%zion%", "Methodist"),
        ("%cme%church%", "Methodist"),
        ("%ame%church%", "Methodist"),
        ("%coptic%", "Eastern Orthodox"),
        ("%greek%orthodox%", "Eastern Orthodox"),
        ("%russian%orthodox%", "Eastern Orthodox"),
        ("%serbian%orthodox%", "Eastern Orthodox"),
        # Spanish/Portuguese denominations
        ("%asamblea%de%dios%", "Pentecostal"),
        ("%asambleas%de%dios%", "Pentecostal"),
        ("%iglesia%evangelica%", "Evangelical"),
        ("%igreja%evangelica%", "Evangelical"),
        ("%iglesia%pentecostal%", "Pentecostal"),
        ("%iglesia%luterana%", "Lutheran"),
        ("%iglesia%metodista%", "Methodist"),
        ("%iglesia%presbiteriana%", "Presbyterian"),
        ("%iglesia%catolica%", "Catholic"),
        ("%igreja%catolica%", "Catholic"),
        ("%iglesia%bautista%", "Baptist"),
        ("%igreja%batista%", "Baptist"),
        ("%iglesia%adventista%", "Adventist"),
        ("%iglesia%de%cristo%", "Restorationist"),
        ("%iglesia%anglicana%", "Anglican"),
        ("%iglesia%episcopal%", "Anglican"),
        ("%templo%asambleas%de%dios%", "Pentecostal"),
        ("%primera%iglesia%asamblea%", "Pentecostal"),
        # Abbreviations
        ("% umc%", "Methodist"),
        ("% umc %", "Methodist"),
        ("%elca%", "Lutheran"),
        ("%lcms%", "Lutheran"),
        ("%wels%", "Lutheran"),
        ("%pca%", "Presbyterian"),
        ("%pcusa%", "Presbyterian"),
        ("%sbc%", "Baptist"),
        ("%cogic%", "Pentecostal"),
        ("%iphc%", "Pentecostal"),
        ("%ucc%", "Congregational"),
        ("%cma%", "Evangelical"),
        ("%efca%", "Evangelical"),
        ("%crcna%", "Reformed"),
        ("%crc%church%", "Reformed"),
        # More English patterns
        ("%catholic%church%", "Catholic"),
        ("% community church%", "Evangelical"),
        ("% community %church%", "Evangelical"),
        ("%fellowship%church%", "Evangelical"),
        ("%bible%church%", "Evangelical"),
        ("%bible%chapel%", "Evangelical"),
        ("%grace%church%", "Evangelical"),
        ("%new%life%church%", "Evangelical"),
        ("%new%hope%church%", "Evangelical"),
        ("%living%word%", "Evangelical"),
        ("%vineyard%church%", "Evangelical"),
        ("%calvary%chapel%", "Evangelical"),
        ("%hope%church%", "Evangelical"),
        ("%life%church%", "Evangelical"),
        ("%victory%church%", "Evangelical"),
        ("%faith%church%", "Evangelical"),
        ("%crossroads%church%", "Evangelical"),
        ("%cornerstone%church%", "Evangelical"),
        ("%harvest%church%", "Evangelical"),
        ("%journey%church%", "Evangelical"),
        ("%the%rock%church%", "Evangelical"),
        ("%gateway%church%", "Evangelical"),
        ("%elevation%church%", "Evangelical"),
        ("%christian%center%", "Evangelical"),
        ("%worship%center%", "Evangelical"),
        ("%christian%fellowship%", "Evangelical"),
        # More specific Christian patterns
        ("%foursquare%", "Pentecostal"),
        ("%iglesia%ni%cristo%", "Restorationist"),
        ("%church%of%the%nazarene%", "Holiness"),
        ("%free%methodist%", "Methodist"),
        ("%global%methodist%", "Methodist"),
        ("%united%church%of%christ%", "Congregational"),
        ("%disciples%of%christ%", "Restorationist"),
        ("%christian%and%missionary%alliance%", "Evangelical"),
        ("%e-free%", "Evangelical"),
        ("%evangelical%free%", "Evangelical"),
        ("%evangelical%covenant%", "Evangelical"),
        ("%moravian%", "Moravian"),
        ("%unitarian%", "Unitarian"),
        ("%universalist%", "Unitarian"),
        ("%quaker%", "Quaker"),
        ("%friends%meeting%", "Quaker"),
        ("%friends%church%", "Quaker"),
        ("%brethren%church%", "Anabaptist"),
        ("%brethren%in%christ%", "Anabaptist"),
        ("%church%of%the%brethren%", "Anabaptist"),
    ]
    for pattern, trad in name_trads:
        c.execute("""UPDATE churches SET tradition=?
                     WHERE (tradition IS NULL OR tradition='')
                       AND faith='Christian' AND LOWER(name) LIKE ?""", (trad, pattern))
        n = c.rowcount
        if n > 0:
            log(f"  {pattern}: {n:,} -> {trad}")
            total_fixes += n
    db.commit()

    # ── Summary ──
    log(f"\n=== TOTAL FIXES: {total_fixes:,} ===")

    # Remaining gaps
    c.execute("SELECT COUNT(*) FROM churches WHERE (tradition IS NULL OR tradition='') AND faith IS NOT NULL")
    log(f"  Still missing tradition: {c.fetchone()[0]:,}")
    c.execute("SELECT COUNT(*) FROM churches WHERE (landmark_type IS NULL OR landmark_type='')")
    log(f"  Still missing landmark_type: {c.fetchone()[0]:,}")
    c.execute("SELECT COUNT(*) FROM churches WHERE taxonomy_id IS NULL")
    log(f"  Still missing taxonomy_id: {c.fetchone()[0]:,}")

    # Provenance
    c.execute("""INSERT INTO provenance_log
        (source, script_name, started_at, completed_at, status,
         churches_updated, fields_populated, notes)
        VALUES (?,?,?,?,'completed',?,?,?)""",
        ("pattern_backfill", __file__,
         datetime.now().isoformat(), datetime.now().isoformat(),
         total_fixes, "landmark_type,taxonomy_id,tradition",
         f"Faith-based defaults + country priors + name keywords. {total_fixes} total fixes."))
    db.commit()
    db.close()

if __name__ == "__main__":
    run_backfill()
