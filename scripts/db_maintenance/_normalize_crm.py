"""Normalize CRM columns out of churches into separate tables."""
import sqlite3, time

db = sqlite3.connect('E:/grid/churches.db')
total = db.execute("SELECT COUNT(*) FROM churches").fetchone()[0]

# ============================================================
# 1. church_contacts — email, phone, web, pastor, address, social
# ============================================================
print("Creating church_contacts...")
db.execute("DROP TABLE IF EXISTS church_contacts")
db.execute("""
    CREATE TABLE church_contacts (
        church_id INTEGER PRIMARY KEY REFERENCES churches(id),
        email TEXT,
        phone TEXT,
        website TEXT,
        pastor_name TEXT,
        address_standardized TEXT,
        address_zip4 TEXT,
        address_standardized_at TEXT,
        facebook_url TEXT,
        instagram_url TEXT,
        youtube_url TEXT,
        online_giving_link TEXT,
        livestream_link TEXT,
        email_validated INTEGER,
        has_website INTEGER,
        website_scrape_status TEXT,
        email_scrape_status TEXT,
        website_source TEXT,
        phone_source TEXT,
        email_source TEXT,
        website_last_verified TEXT,
        email_last_verified TEXT,
        phone_last_verified TEXT,
        website_last_updated TEXT,
        website_confidence REAL,
        email_confidence REAL,
        phone_confidence REAL,
        cms_type TEXT,
        has_annual_report INTEGER,
        giving_platform TEXT
    )
""")

# Migrate data
t0 = time.time()
db.execute("""
    INSERT OR IGNORE INTO church_contacts
    SELECT id, email, phone, website, pastor_name,
           address_standardized, address_zip4, address_standardized_at,
           facebook_url, instagram_url, youtube_url,
           online_giving_link, livestream_link,
           email_validated, has_website,
           website_scrape_status, email_scrape_status,
           website_source, phone_source, email_source,
           website_last_verified, email_last_verified, phone_last_verified,
           website_last_updated,
           website_confidence, email_confidence, phone_confidence,
           cms_type, has_annual_report, giving_platform
    FROM churches
    WHERE email IS NOT NULL OR phone IS NOT NULL OR website IS NOT NULL
       OR pastor_name IS NOT NULL OR facebook_url IS NOT NULL
""")
n = db.execute("SELECT changes()").fetchone()[0]
print(f"  church_contacts: {n:,} rows in {time.time()-t0:.1f}s")

# ============================================================
# 2. church_operations — services, ministries, programs, staff, attendance
# ============================================================
print("Creating church_operations...")
db.execute("DROP TABLE IF EXISTS church_operations")
db.execute("""
    CREATE TABLE church_operations (
        church_id INTEGER PRIMARY KEY REFERENCES churches(id),
        service_times TEXT,
        languages TEXT,
        primary_language TEXT,
        secondary_languages TEXT,
        spanish_language TEXT,
        spanish_detection_source TEXT,
        attendance_est INTEGER,
        attendance_confidence REAL,
        estimated_attendance INTEGER,
        staff_count INTEGER,
        campus_count INTEGER,
        campus_group_id INTEGER,
        campus_name TEXT,
        campus_type TEXT,
        parent_church_id INTEGER,
        has_youth INTEGER,
        has_children INTEGER,
        has_food_pantry INTEGER,
        has_preschool INTEGER,
        has_daycare INTEGER,
        has_seniors INTEGER,
        has_esl INTEGER,
        has_recovery INTEGER,
        has_missions INTEGER,
        has_counseling INTEGER,
        has_sports INTEGER,
        has_school TEXT,
        has_social_services TEXT,
        is_closed INTEGER,
        is_church_plant INTEGER,
        ministry_count INTEGER,
        worship_style TEXT,
        doctrinal_alignment TEXT,
        leadership_structure TEXT,
        statement_of_faith TEXT,
        community_impact TEXT,
        last_deep_scraped TEXT,
        founding_year INTEGER,
        historical_status TEXT,
        has_calendar INTEGER,
        calendar_type TEXT,
        calendar_frequency TEXT,
        org_type TEXT,
        entity_type TEXT,
        target_group TEXT,
        enrichment_version INTEGER
    )
""")

t0 = time.time()
db.execute("""
    INSERT OR IGNORE INTO church_operations
    SELECT id, service_times, languages, primary_language, secondary_languages,
           spanish_language, spanish_detection_source,
           attendance_est, attendance_confidence, estimated_attendance,
           staff_count, campus_count,
           campus_group_id, campus_name, campus_type, parent_church_id,
           has_youth, has_children, has_food_pantry, has_preschool, has_daycare,
           has_seniors, has_esl, has_recovery, has_missions, has_counseling, has_sports,
           has_school, has_social_services,
           is_closed, is_church_plant, ministry_count,
           worship_style, doctrinal_alignment, leadership_structure,
           statement_of_faith, community_impact, last_deep_scraped,
           founding_year, historical_status,
           has_calendar, calendar_type, calendar_frequency,
           org_type, entity_type, target_group, enrichment_version
    FROM churches
    WHERE attendance_est IS NOT NULL OR service_times IS NOT NULL
       OR has_youth IS NOT NULL OR has_children IS NOT NULL
       OR is_closed = 1 OR staff_count IS NOT NULL
""")
n = db.execute("SELECT changes()").fetchone()[0]
print(f"  church_operations: {n:,} rows in {time.time()-t0:.1f}s")

# ============================================================
# 3. church_enrichment — census, elections, geo, historic, broadcast, classification
# ============================================================
print("Creating church_enrichment...")
db.execute("DROP TABLE IF EXISTS church_enrichment")
db.execute("""
    CREATE TABLE church_enrichment (
        church_id INTEGER PRIMARY KEY REFERENCES churches(id),
        -- Census/ACS
        county_fips TEXT, county_name TEXT,
        county_total_pop REAL, county_median_hh_income REAL,
        county_poverty_rate REAL, county_unemployment_rate REAL,
        county_bachelors_25_64 REAL, county_graduate_degree REAL,
        county_white_pct REAL, county_black_pct REAL,
        county_asian_pct REAL, county_hispanic_pct REAL,
        county_median_home_value REAL, county_median_gross_rent REAL,
        county_owner_pct REAL, county_mean_commute_min REAL,
        county_drove_alone_pct REAL, county_wfh_pct REAL,
        county_gini_index REAL, county_income_per_capita REAL,
        county_median_age REAL, tract_count_in_county REAL,
        -- Elections
        dem_share_2024 REAL, rep_share_2024 REAL,
        dem_share_2020 REAL, rep_share_2020 REAL,
        dem_share_2016 REAL, rep_share_2016 REAL,
        dem_share_2012 REAL, rep_share_2012 REAL,
        active_reg_2024 INTEGER, total_ballots_2024 INTEGER, turnout_rate_2024 REAL,
        active_reg_2020 INTEGER, total_ballots_2020 INTEGER, turnout_rate_2020 REAL,
        -- Broadcast
        is_broadcaster INTEGER, fcc_facility_id TEXT, fcc_call_sign TEXT, fcc_service_type TEXT,
        cbsa_code TEXT, cbsa_name TEXT, cbsa_type TEXT, dma_name TEXT,
        -- Historic
        nrhp_ref TEXT, nrhp_listed_date TEXT, nrhp_category TEXT,
        nrhp_significance TEXT, nrhp_area_of_significance TEXT,
        -- Geo
        gnis_feature_id TEXT, gnis_lat REAL, gnis_lon REAL,
        tract_fips TEXT, tract_geocode_source TEXT, tract_geocode_date TEXT,
        county_fips_5 TEXT,
        here_geocode_quality TEXT, here_last_geocoded TEXT,
        rucc_code INTEGER, rucc_description TEXT, broadband_pct REAL,
        -- Classification confidences
        scrape_confidence REAL, kg_confidence REAL, zb_confidence REAL,
        geocode_confidence REAL,
        muslim_confidence REAL, jewish_confidence REAL,
        buddhist_confidence REAL, hindu_confidence REAL,
        sikh_confidence REAL, jain_confidence REAL, nrm_confidence REAL,
        classification_source TEXT,
        -- ARDA
        attendance_arda INTEGER, attendance_source TEXT,
        attendance_computed INTEGER, members_arda INTEGER, members_source TEXT,
        -- Denomination-specific classification
        jewish_movement TEXT, jewish_classification_source TEXT, jewish_updated TEXT,
        muslim_affiliation TEXT, muslim_classification_source TEXT, muslim_updated TEXT,
        buddhist_tradition TEXT, buddhist_classification_source TEXT, buddhist_updated TEXT,
        hindu_affiliation TEXT, hindu_region TEXT, hindu_classification_source TEXT, hindu_updated TEXT,
        sikh_affiliation TEXT, sikh_classification_source TEXT, sikh_updated TEXT,
        jain_affiliation TEXT, jain_classification_source TEXT, jain_updated TEXT,
        nrm_category TEXT, nrm_subcategory TEXT, nrm_classification_source TEXT, nrm_updated TEXT,
        -- Catholic
        rite TEXT, catholic_hierarchy_source TEXT,
        -- LDS
        lds_type TEXT, lds_confidence REAL, lds_source TEXT,
        -- Hierarchy
        diocese TEXT, archdiocese TEXT, deanery TEXT, synod TEXT,
        conference TEXT, district TEXT, presbytery TEXT, association TEXT,
        province TEXT, denom_region TEXT, denom_subgroup TEXT,
        -- Liturgical
        liturgical_tradition TEXT, liturgical_family TEXT,
        -- Other
        notes TEXT, last_updated TEXT,
        geocode_attempts INTEGER, geocode_last_attempt TEXT,
        denom_confidence REAL, manual_override_flag INTEGER,
        classification_timestamp TEXT, classification_version TEXT,
        mx_admin_level INTEGER, mx_division_id TEXT, mx_division_name TEXT, mx_admin_subtype TEXT
    )
""")

t0 = time.time()
db.execute("""
    INSERT OR IGNORE INTO church_enrichment
    SELECT id,
        county_fips, county_name,
        county_total_pop, county_median_hh_income, county_poverty_rate, county_unemployment_rate,
        county_bachelors_25_64, county_graduate_degree, county_white_pct, county_black_pct,
        county_asian_pct, county_hispanic_pct, county_median_home_value, county_median_gross_rent,
        county_owner_pct, county_mean_commute_min, county_drove_alone_pct, county_wfh_pct,
        county_gini_index, county_income_per_capita, county_median_age, tract_count_in_county,
        dem_share_2024, rep_share_2024, dem_share_2020, rep_share_2020,
        dem_share_2016, rep_share_2016, dem_share_2012, rep_share_2012,
        active_reg_2024, total_ballots_2024, turnout_rate_2024,
        active_reg_2020, total_ballots_2020, turnout_rate_2020,
        is_broadcaster, fcc_facility_id, fcc_call_sign, fcc_service_type,
        cbsa_code, cbsa_name, cbsa_type, dma_name,
        nrhp_ref, nrhp_listed_date, nrhp_category, nrhp_significance, nrhp_area_of_significance,
        gnis_feature_id, gnis_lat, gnis_lon,
        tract_fips, tract_geocode_source, tract_geocode_date, county_fips_5,
        here_geocode_quality, here_last_geocoded,
        rucc_code, rucc_description, broadband_pct,
        scrape_confidence, kg_confidence, zb_confidence, geocode_confidence,
        muslim_confidence, jewish_confidence, buddhist_confidence, hindu_confidence,
        sikh_confidence, jain_confidence, nrm_confidence,
        classification_source,
        attendance_arda, attendance_source, attendance_computed, members_arda, members_source,
        jewish_movement, jewish_classification_source, jewish_updated,
        muslim_affiliation, muslim_classification_source, muslim_updated,
        buddhist_tradition, buddhist_classification_source, buddhist_updated,
        hindu_affiliation, hindu_region, hindu_classification_source, hindu_updated,
        sikh_affiliation, sikh_classification_source, sikh_updated,
        jain_affiliation, jain_classification_source, jain_updated,
        nrm_category, nrm_subcategory, nrm_classification_source, nrm_updated,
        rite, catholic_hierarchy_source,
        lds_type, lds_confidence, lds_source,
        diocese, archdiocese, deanery, synod,
        conference, district, presbytery, association,
        province, denom_region, denom_subgroup,
        liturgical_tradition, liturgical_family,
        notes, last_updated,
        geocode_attempts, geocode_last_attempt,
        confidence_score, manual_override_flag,
        classification_timestamp, classification_version,
        mx_admin_level, mx_division_id, mx_division_name, mx_admin_subtype
    FROM churches
    WHERE county_fips IS NOT NULL OR dem_share_2024 IS NOT NULL
       OR is_broadcaster = 1 OR nrhp_ref IS NOT NULL
       OR gnis_feature_id IS NOT NULL OR attendance_arda IS NOT NULL
       OR diocese IS NOT NULL OR notes IS NOT NULL
       OR classification_source IS NOT NULL
""")
n = db.execute("SELECT changes()").fetchone()[0]
print(f"  church_enrichment: {n:,} rows in {time.time()-t0:.1f}s")

db.commit()

# Stats
for table in ['church_contacts', 'church_operations', 'church_enrichment']:
    cnt = db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    cols = len([r for r in db.execute(f"PRAGMA table_info({table})")])
    print(f"  {table}: {cnt:,} rows, {cols} columns")

# Core churches columns left
core = len([r for r in db.execute("PRAGMA table_info(churches)")])
print(f"\nchurches still has {core} columns (need to drop the migrated ones next)")
db.close()
