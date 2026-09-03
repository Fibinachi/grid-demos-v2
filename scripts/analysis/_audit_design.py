import sqlite3
db = sqlite3.connect('E:/grid/churches.db')

# Check which enrichment tables have church_id FK (normalized) vs are columns on churches (denormalized)
tables = [r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'church_%' ORDER BY name")]
print("--- Enrichment tables (normalized — FK to churches) ---")
for t in tables:
    cols = [r[1] for r in db.execute(f"PRAGMA table_info({t})")]
    cnt = db.execute(f"SELECT COUNT(*) FROM [{t}]").fetchone()[0]
    has_church_id = 'church_id' in cols
    print(f"  {t:<25} {cnt:>10,} rows  church_id FK: {has_church_id}")

# What's on churches that could be in enrichment tables?
print("\n--- Columns on churches that should be in their own table ---")
categories = {
    "Contact": ['email','phone','website','pastor_name','address','city','state','zip','zip5','zip4'],
    "Operations": ['service_times','languages','attendance_est','staff_count','campus_count',
                   'has_youth','has_children','has_food_pantry','has_preschool','has_daycare',
                   'has_seniors','has_esl','has_recovery','has_missions','has_counseling','has_sports',
                   'is_closed','is_church_plant','ministry_count'],
    "Census": ['county_fips','county_name','county_total_pop','county_median_hh_income',
               'county_poverty_rate','county_unemployment_rate','county_bachelors_25_64',
               'county_graduate_degree','county_white_pct','county_black_pct','county_asian_pct',
               'county_hispanic_pct','county_median_home_value','county_median_gross_rent',
               'county_owner_pct','county_mean_commute_min','county_drove_alone_pct',
               'county_wfh_pct','county_gini_index','county_income_per_capita','county_median_age'],
    "Elections": ['dem_share_2024','rep_share_2024','dem_share_2020','rep_share_2020',
                  'dem_share_2016','rep_share_2016','dem_share_2012','rep_share_2012',
                  'active_reg_2024','total_ballots_2024','turnout_rate_2024',
                  'active_reg_2020','total_ballots_2020','turnout_rate_2020'],
    "Classification": ['scrape_confidence','kg_confidence','zb_confidence',
                       'website_confidence','email_confidence','phone_confidence',
                       'geocode_confidence','muslim_confidence','jewish_confidence',
                       'buddhist_confidence','hindu_confidence','sikh_confidence','jain_confidence',
                       'nrm_confidence','classification_source'],
    "ARDA": ['attendance_arda','attendance_source','attendance_computed','members_arda','members_source'],
    "Broadcast": ['is_broadcaster','fcc_facility_id','fcc_call_sign','fcc_service_type',
                  'cbsa_code','cbsa_name','cbsa_type','dma_name'],
    "Historic": ['nrhp_ref','nrhp_listed_date','nrhp_category','nrhp_significance','nrhp_area_of_significance'],
    "Geo": ['gnis_feature_id','gnis_lat','gnis_lon','tract_fips','tract_geocode_source','tract_geocode_date',
            'here_geocode_quality','here_last_geocoded','rucc_code','rucc_description','broadband_pct'],
}

ch_cols = {r[1] for r in db.execute("PRAGMA table_info(churches)")}
total_movable = 0
for cat, cols in categories.items():
    on_churches = [c for c in cols if c in ch_cols]
    if on_churches:
        total_movable += len(on_churches)
        print(f"  {cat}: {len(on_churches)} columns (e.g. {on_churches[0]}, {on_churches[-1]})")

print(f"\nTotal columns that could be normalized out: ~{total_movable}")

# What's left as "core"?
core = ch_cols - {c for cols in categories.values() for c in cols}
print(f"Core columns remaining: ~{len(core)}")
print(f"(id, name, denomination, family, faith, tradition, lat/lon, country, source, holy_site_id, etc.)")

db.close()
