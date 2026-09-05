## Recent Fixes & Builds (2026-09-05)
| Date | Task | Details |
|---|---|---|
| | 09-05 | **[DONE] MERGE: 354,441 wikidata holy_sites churches** | `_merge_wikidata.py --write` -- 780,737 wikidata_staging rows (QID-deduped to 354,441 unique QIDs) merged into churches.db. 9 coord-clusters excluded (admin centroids, not real churches, 320 QIDs). 100% taxonomy auto-mapped via 6 faith/landmark combos. Breakdown: Shinto shrine 287K | Christian church 255K | Hindu temple 180K | Islam mosque 55K | Jewish synagogue 1.7K | Christian abbey 1.6K. Each new church gets churches + church_location row (country from staging, admin0/1/2=NULL pending spatial join). IDs 6,701,015-7,055,455. Provenance: `merge_wikidata_staging`. |
09-05 | **[DONE] BACKFILL: US admin codes for 318,132 church_location rows** | `_backfill_us_admin.py --write` — 318,132 US rows had `country='US'` but NULL `admin0_code`. admin0 set to 'US'/'United States' for all; admin1_code/admin1_name filled from state column (TX, CA, FL, etc. mapped to full names) covering 260,182 rows; admin2_code filled from `county_fips_5` for 270,542 rows. Remaining NULLs (65K admin1, 115K admin2) are rows with no state/county data. Duration: 22s. Provenance: `provenance_log` id=1945. |
| 09-05 | **[DONE] MERGE: 32,344 foursquare_osp_2026 dupes into osage_japan** | `_dedup_foursquare_into_osage.py --write` — osage_japan is authoritative (human-verified). 32,344 foursquare_osp_2026 records within 50m with identical normalized names were soft-merged: `status='merged'`, `dedup_canonical_id` pointing to osage record, `merged_into` written to enrichment_change_log. Remaining: osage_japan 184,335 (all taxonomy_id=NULL), foursquare_osp_2026 ~849,010 active. |
| 09-05 | **[DONE] CLASSIFY: 184,335 osage_japan records into CFTLM taxonomy** | `_classify_osage_japan.py --write` — all 184,335 osage_japan records now have taxonomy_id + tradition. Breakdown: Buddhist general 82,852 (tax_id=9) | Shrine Shinto 75,674 (534) | Protestant unclassified 12,491 (330) | Folk Shinto 8,542 (538) | Other 986 (6) | Baptist 800 (219) | Zen 691 (70) | Jehovah's Witnesses 627 (16) | Nichiren 606 (66) | Pure Land 409 (67) | Tibetan/Esoteric 223 (72) | Catholic 206 (14) | Anglican 101 (13) | Sect Shinto 96+25 (537) | Tenrikyo 6 (670). 0 NULL taxonomy_id remaining. |
| 09-04 | **[DONE] PURGE: 29,254 WPA contamination records deleted** | IDs 5,226,591-5,255,844 (17,237 osage_japan-tagged + 12,017 wpa_historical_records_survey-tagged). Root cause: concurrent osage_japan + WPA imports interleaved IDs causing name swap. Verification: 0 enrichment_change_log entries for both sources = no downstream enrichment damage. churches.db now 4,545,544 records. WPA re-parse from scratch planned for later. Script: `_purge_wpa_contamination.py --write`. |
| 08-10 | **[DONE] 359,666 orphan address rows RESOLVED via spatial re-link (recovery, not deletion)** | **`_fix_orphan_relink.py --write`** — the NULL-`church_id` rows (all 359,666 had `church_id IS NULL`, stale `church_rowid`, parents gone) were NOT junk: 354,751 with GPS, 181,099 with street/city text, 97.8% osm_import. Fixed by cKDTree nearest-church spatial match (500 m, project pattern): **LINK 226,607** orphans → `church_id` backfill (one per church, richest wins → 226,607 distinct churches got an address), **MERGE 86,623** dup orphans' missing components/GPS/country into existing addresses (58,913 components + 20,852 GPS merged) then deleted, **DELETE 46,436** truly unlinkable (no GPS 4,915 + no church within 500 m 41,521). Result: **0 orphan rows, 0 orphan components**; church_addresses 690,297→557,238; address_components 882,266→818,064; address coverage 330,430→**557,037** churches. Provenance `orphan_relink_2026` (completed, 226,607 churches) + 359,666 change-log rows. Backup `D:\backups\churches_20260810_113035.db` + staging `data/staging/orphan_addr_backup_20260810_113035.db` (all 359,666 rows recoverable). Verified: churches 3,290,611 + GPS 3,204,070 intact. **Gotchas**: (1) `church_addresses` had NO index on `address_id` — first apply run stalled at ~201 rows (full table scan per UPDATE, would've taken hours); fixed by creating `idx_church_addresses_address_id` BEFORE writes → whole apply ran in 156 s; (2) dedup LINK to one-per-church avoids double-primary (226,607 links → 226,607 churches). **Pre-existing (NOT from this fix)**: 201 churches have 2 current primary osm_import addresses (address_ids 38 apart = duplicated OSM import block) — trivial future cleanup. |
| 08-10 | **[DONE] MERGE CORRUPTION REPAIRED: 2,952,751 corrupt address rows purged** | **`_fix_addr_shift_clean.py --write`** — deleted 2,952,751 `church_addresses` rows + 3,789,402 `address_components` for the ENTIRE `fix_addr_gps_shift_2026` population (the merge-06-18 positional-zip corruption). Scoping proved every fix church had EXACTLY 1 address row (100% NULL-GPS, `is_current=1`, `address_type=primary`, `valid_from=2026`) → the row IS corruption, nothing correct lost. This SINGLE population covers BOTH the ~1.2M country mismatches AND the 490,978 US state conflicts (84.2% in-fix; sample 500: 478/478 old addrGPS matched holy_sites rows = same-country positional shift). Exported deleted rows to staging `data/staging/addr_corrupt_backup_20260810_104218.db` (recoverable). Provenance `fix_addr_shift_clean_2026` (status=completed, 2,952,751) + 2,952,751 change-log rows (`address_row_deleted`). Backup `D:\backups\churches_20260810_104218.db`. Verified 8/8: counts 690,297/882,266; 0 fix-pop churches with remaining addr rows; 0 orphan components; churches 3,290,611 + GPS 3,204,070 intact. **LEGIT addresses UNTOUCHED** (77,328 non-fix state conflicts = IRS/overture mailing, kept; remaining 690K rows all non-fix sources). Gotcha: created `idx_address_components_address_id` (was MISSING — SQLite doesn't auto-create FK indexes). |
```python
from gw_db import get_db
db = get_db()  # returns sqlite3.Connection with provenance auto-logging
```

### Reconstructing past provenance
- `_reconstruct_provenance.py` — extracts provenance from the `churches.source` field
- Generates `data/provenance_reconstructed.json` (59 entries covering all churches)
- Apply with: `_reconstruct_provenance.py --apply`

## Schema (2026-07-29)

### Core Table: `churches` (33 columns, 3.29M rows)
Identity, classification, and spatial anchor only. **`id` is the immutable primary key.**

```raw
churches
  id (INT, PK)           — stable identifier, survives VACUUM/rebuild
  name, normalized_name   — name + canonical form
  name_original, name_transliterated, name_english
  faith, tradition, legacy, movement  — CFTLM classification
  civilizational_family
  taxonomy_id             — FK to taxonomy tree
  faith_id, culture_id, legacy_id, tradition_id, movement_id
  latitude, longitude      — spatial anchor
  source, confidence_score
  landmark_type, is_landmark
  last_updated, notes
  christ_class_*, bh_*, shinto_*  — classifier confidence columns
```

### Enrichment Join Tables (all keyed on `church_id` → `churches.id`)

| Table | Cols | Content | Key Scripts |
|---|---|---|---|
| `church_location` | 28 | address, city, state, county_fips_5, zip, country, continent, region_un, admin0-5 codes/names | `assign_admin_codes.py`, `rejoin_postal_codes.py`, `reverse_geocode_nominatim.py` |
| `church_infrastructure` | 20 | nearest_fire_km, nearest_police_km, nearest_hospital_km, nearest_clinic_km, nearest_school_km, nearest_cemetery_km, interfaith distances (mosque/synagogue/hindu/buddhist/sikh), same-faith density | `build_security_layer.py`, BQ OSM enrichment |
| `church_environment` | 13 | elevation_m, nearest_coast_km, nearest_city_km, flood_zone, flood_risk_score, pop_05km…pop_30km, catchment_updated, grid_source | `compute_euclidean_catchment.py`, BQ enrichment |
| `church_property` | 18 | building_sqft, parking_spots, capacity_estimate, building_source, building_year, closed_year, fl_parcel_id, fl_dor_uc, fl_market_value, fl_building_sqft, fl_year_built, tn_parcel_id, treasury_value, assessment_value, sale_price, **opened_year, opened_year_source, opened_year_updated** (08-08) | FL/TN parcel pipelines, `_add_opened_year.py` |
| `church_census` | 14 | cra_bn, cra_category, cra_sub_category, cra_designation, mapping_saints_*, ntee_code | Ireland charities, Mapping Saints, NTEE import |
| `church_land_holdings` | 24 | **One row per religious land parcel** (FL/WI): land_value, market_value (FL JV), improvement_value, land_acres, building_sqft, land_use_category (church/parsonage/cemetery/auxiliary), owner, county, GPS, match_method. Query via `v_church_land_holdings` | `build_land_holdings.py`, `query_land_holdings.py` (08-06) |

### Join Pattern (universal)

```sql
-- Get everything for a church
SELECT c.*, l.*, i.*, e.*, p.*, ce.*
FROM churches c
LEFT JOIN church_location l ON c.id = l.church_id
LEFT JOIN church_infrastructure i ON c.id = i.church_id
LEFT JOIN church_environment e ON c.id = e.church_id
LEFT JOIN church_property p ON c.id = p.church_id
LEFT JOIN church_census ce ON c.id = ce.church_id
WHERE c.id = 12345;

-- All enrichment tables have UNIQUE index on church_id
-- All legacy census/election tables also have church_id column (07-29 fix)
```

### Adding New Enrichment

1. Create the table: `CREATE TABLE church_xxx (church_id INTEGER PRIMARY KEY, ...)`
2. Populate via `churches.id` — never rowid
3. Create index: `CREATE UNIQUE INDEX idx_church_xxx_cid ON church_xxx(church_id)`
4. Add to BQ export list in `bq_export_all_tables.py`
5. Document here

## Database Rules

- **DB location**: `E:\grid\churches.db` (~14.4 GB, SQLite3, WAL mode)
- **Core table**: `churches` — 33 identity + classification + spatial columns. **`id` is the immutable primary key.**
- **Enrichment tables**: `church_location`, `church_infrastructure`, `church_environment`, `church_property`, `church_census` — all keyed on `church_id` → `churches.id`
- **Legacy tables**: 115 census/election tables now have `church_id` column (07-29 fix). `church_rowid` retained for reference. NULL `church_id` = census district with no matched church yet — not an error.
- **Geo DB**: `data/natural_earth/world_borders.db` — `world_borders` (241 countries), `state_borders` (~4,500 states/provinces), `diocese_boundaries` (69 hierarchy units), `ca_provinces` (13 Canadian provinces)
- **GeoBoundaries**: `data/world_boundaries/` — 334 GeoJSON files covering 162 countries at ADM0/1/2 levels (CC-BY-4.0). Used by `assign_admin_codes.py` to populate `admin0/1/2_code` and `admin0/1/2_name`.
- **Project**: GRID — Global Religious Infrastructure Database
- **Never** modify the `churches` table without recording provenance
- **Never use `rowid` for joins** — always use `churches.id` / `church_id`
- **New enrichment always as join tables**, never as columns on `churches`
- **Before any destructive operation**, test on a copy
- **After any import/update**, run: `python scripts/db_maintenance/enrichment_status.py`
- **After any text data import**, run: `python scripts/enrichment/cleanup_html_artifacts.py`

## Project Structure

| Dir | Purpose |
|---|---|
| `scripts/db_maintenance/` | DB recovery, verification, BigQuery export, schema migrations |
| `scripts/enrichment/` | Census, ARDA, geocoding, denomination classification, Boston property, Ireland charities |
| `scripts/scrapers/` | Denomination-specific scrapers |
| `scripts/outreach/` | Email campaigns, inbox monitoring, unified sender, lead generation |
| `scripts/orchestrator/` | EC2 pipeline management |
| `scripts/geodata/` | GIS data ingestion (borders, diocese boundaries) |
| `scripts/wikidata/` | Wikidata imports and enrichment |
| `data/denom/` | Scraped denomination CSVs |
| `data/natural_earth/` | world_borders.db, diocese boundaries, country shapefiles |
| `data/world_boundaries/` | 334 geoBoundaries GeoJSON files (162 countries with ADM0/1/2) |
| `docs/` | Dataset documentation |

## Email Outreach Pipeline (2026-07-02)

### Unified Continuous Sender
- **Script**: `scripts/outreach/send_unified.py` — runs 24/7, processes queue at 1 email per 3 minutes
- **Queue builder**: `scripts/outreach/build_unified_queue.py` — generates `unified_queue.jsonl` from all lead sources
- **Rate**: 1 per 180s = 20/hr = ~480/day (Gmail free tier limit)
## Current State (2026-08-05)
- **Church land holdings (08-06)**: `church_land_holdings` = 46,375 religious land parcels (FL 35,828 w/ full JV market values $42.6B, WI 10,547 w/ acres). **$32.5B matched market value / $10.3B land / 21,348 WI acres** across 18,613 churches. Query: `scripts/analysis/query_land_holdings.py` or view `v_church_land_holdings`.
- **Sent log**: `outputs/outreach/gmail_sent.txt` (prevents duplicates)
- **3,288,953 churches** in `churches.db` (~18.4 GB on disk, WAL). Core table: 33 columns.
- **Sweden historic verification (08-05)**: **11,700 SE churches** visually verified against Ekonomiska kartan 1935-78 (3,114 sheets, 100%). Verdicts: BUILDING_PRESENT 4,921 | AMBIGUOUS 4,981 | NO_BUILDING 1,798. Data: `data/staging/se_historic/`. **NEXT: `_fix_se_coords_from_maps.py`** (coordinate correction + vanished-church detection).
- **Gap layer (08-05)**: `admin_gap` 361 ADM1 rows, 14 countries (TZ/NG/ET/KE/UG/CD/IN/BD/ID/PH/BR/CO/PE/VE), 300:1 norm. Leaflet map `outputs/gap_layer/gap_layer.html`. Script `scripts/enrichment/build_gap_layer.py` (resumable).
- **Databricks export (08-05)**: 32 CSVs exported (4.85 GB), DBFS upload working, **Delta `COPY INTO` BLOCKED** — fix `run_sql()` `execute_statement()` to add `on_wait_timeout="CONTINUE"` (SDK defaults CANCEL, incompatible with `wait_timeout="0s"`). See 08-05 table row. Script: `scripts/db_maintenance/databricks_export_all_tables.py`.
- **Outreach (08-05)**: Phase 1 Helsinki (71) + Phase 2 (87) all delivered. Replies: Ahlstrand (referred Lundberg/Lövheim — thanked), Donnelly (soft pass — thanked), Justin Long (fresh public BQ demo links sent, meeting windows proposed, awaiting reply).
- **5 enrichment join tables**: `church_location` (28 cols), `church_infrastructure` (20), `church_environment` (13), `church_property` (18), `church_census` (14) — all on `church_id`
- **115 legacy tables** now have `church_id` column (07-29 rowid fix: 9.68M mapped, 713K NULL = unmatched census districts, not broken refs)
- **Coverage**: City 99.7% | State 99.9% | GPS 99.1% | Zip 74.9% | Address 71.0%
- **Denomination taxonomy expansion (07-16/17)**: ~68 new nodes (IDs 740–817) hold **~35.3K churches** (IEQ 5,200, IEAD 4,222, IURD 3,831, Congregação Cristã 3,545...). Generic evangelical pool: **149,370** remaining (BR 30,397, MX 3,040, IN 1,674, NG 1,550).
- **Catholic seat_of coverage**: **1,783/2,911 dioceses (61.3%)** — Wikipedia cathedral import in progress (`_import_cathedrals.py`, resumable via `_cat_import.json`, 1,128 orphans left).
- **Orphan contacts**: **78,522 orphaned `church_contact_values` rows** (16.95%, church_id → deleted churches). Exported to `data/orphan_contacts_backup.json`; repair script `_fix_orphan_contacts.py` ready, `--apply` pending. **Never join contact/flood tables on rowid — id-space only.**
- **Classification status**: Buddhist 100% | Hindu 100% (taxonomy tree rebuilt 07-18, 27 nodes/5 depths) | Islam 100% (17 traditions) | Judaism 100% (DeepSeek-verified worldwide) | Sikh 100% (DeepSeek-verified) | Jain 100% (7,530 via jain-wiki SPARQL) | US Christian 100%
- **Nominatim reverse geocode**: ✅ **604K processed** in 5h8m (32.6 rec/s, 8 workers). 165 fills. 603,863 no-city (bad coords). Script: `scripts/enrichment/reverse_geocode_nominatim.py`.
- **Admin1 city fill**: ✅ **50,933 filled** in 71s via Natural Earth admin1 spatial join. Yemen 31K→governorate names. 204 unmatched. Script: `scripts/enrichment/fill_city_from_admin1.py`.
- **Postal codes**: 74.9% globally (2.6M/3.5M). GeoNames codes across 41 countries.
- **Country breakdown**: US 1,032K | IN 232K | BR 205K | JP 158K | ID 149K | DE 106K | GB 101K | CA 95K | FR 94K | IT 86K | TH 66K | SA 60K | MX 56K | PH 55K | ES 50K | TR 43K | PL 35K | YE 33K | TW 32K | RU 32K
- **Enrichment log**: 2,194,313 changes | **463,273** contact values | **619,860** Nominatim operations | 14 hierarchy tables | 111 census/election tables
- **Sikh classification**: **100% DeepSeek-reviewed** — 5,619 Sikh entries, 5,617 with `sikh_affiliation` populated. Landmark types: gurdwara 5,353, community_center 147, shrine 78, temple 27, school 11.
- **Muslim tradition coverage**: **100%** — all 401K Islam entries classified (17 traditions). Extended geo-priors cover 80+ countries.
- **Jain expansion**: 981 → 7,530 via jain-wiki SPARQL import (07-03). Temple 7,312, Community Center 666, Dharamshala 119, Tirth 16.
- **Boston enrichment**: **924 Boston-area churches** enriched with property assessment data. 371 new entries from exempt property records (LUC=970/906). 7 religious schools from Boston Non-Public Schools. All DeepSeek-classified. 155 dupes merged. `boston_pid` column added for parcel IDs (457 unique PIDs). `boston_property_json` stores full assessment details (value, area, year built, condition).
- **Ireland enrichment**: **1,596 Irish churches** — 1,391 from Register of Charities (DeepSeek-classified), 196 from Dublin/DLR Places of Worship, 9 pre-existing. 13 internal dupes merged. `cra_bn` column for Irish charity numbers.
- **Tables dropped**: `church_contacts` (replaced by `church_contact_values`), `church_rucc` (replaced by `rucc_codes` reference table)
- **Column restructure**: `faith_tradition` → `tradition`, CFTLM taxonomy applied to all 3.29M records
- **LDS hierarchy**: 19,440 rows, 19,425 linked (99.99%). 19 Area Offices (5 PBOs + 14 intl). Maps at `data/lds_*.html`.
- **LOC Phone Directory import**: ✅ **20,143 churches** from 494 digitized LOC telephone directories (126 cities, 1908-1975). **2,365 matched** to GRID by name+city. **6,019 phones** modernized (exchange→numeric with area codes). **1,857 church deaths** detected from directory disappearance (avg 7-9yr lifespan). LA growth animation: `docs/la_growth_map.html`. Death registry: `data/loc_phone_dirs/results/church_deaths.json`. Pipeline: `scripts/ingest/loc_phone_directories.py`.
- **Security layer**: ✅ **940,618 US churches** have `nearest_fire_km` and `nearest_police_km`. Median fire 1.80 km, median police 3.43 km. 48,821 emergency stations sourced from OSM. Script: `scripts/enrichment/build_security_layer.py`.
- **CRA 2024 import**: **27,708 religious orgs** from open.canada.ca (83,762 total charities). 25,350 Christian (cat 30), 539 Muslim (40), 402 Jewish (50), 1,074 Buddhist/Other (60), 343 endowments (90). 8,042 names genuinely new. BN backfill matched 31,833 old + 35,079 non-CRA CA entries by exact name.
- **2010 ARDA**: **77,128 county-denomination rows** in `arda_counts_2010`. 234 denominations across 3,141 counties. SBC declined 22% adherents (19.9M→15.5M) and 10.7% congregations (50.8K→45.3K) from 2010→2020.
- **Bahrain mosques**: **974 new entries** from `data.gov.bh` (CC BY-like) — all MOSQUES, faith=Islam/Sunni. IDs 5,082,234–5,083,207. Total Bahrain: 1,266.
- **Bahrain religious schools**: **23 religious schools** from `data.gov.bh` private schools dataset — 20 Islamic, 3 Christian (Sacred Heart, St. Christopher's, Ebenezer). IDs 5,082,211–5,082,233.
- **Korea temples**: **154 new Buddhist temples** (Gyeongsangbuk-do shapefile from data.go.kr). IDs 5,083,208–5,083,361. 154 phone numbers added to church_contact_values. Korean Buddhism taxonomy.
- **TN parcel import**: **5,314 churches** imported from Tennessee IMPACT CAMA (86/95 counties). **4,714 churches**, **437 parsonages**, **135 schools**, **28 camp/retreat** facilities. 67.1% lack building_sqft, 47.0% have GPS. Script: `_filter_tn_parcels.py`, `_audit_tn_parcel_types.py`.
### Reference Tables

| `nashville_cemeteries` | 14,382 | Nashville/Davidson County cemetery records: name, locale, street, parcel, graveyard_type (07-13) |
| `county_census_us` | 3,213 | Census ACS county-level demographics |
| `church_census_catalog` | 150 | Metadata catalog for all census/election enrichment tables |
| `fcc_facilities` | 104,697 | FCC broadcast facilities |
| `church_census_catalog` | 76 | Metadata catalog for all census/election enrichment tables |
| `arda_counts` | 74,000 | 2020 ARDA county-denomination adherent counts |
| `arda_counts_2010` | 77,128 | 2010 ARDA county-denomination adherent counts (234 denominations) |
| `sba_ppp_loans` | 209,736 | SBA PPP COVID loans matched to churches |
| `geonames_postal` | 1,390,149 | GeoNames postal codes for 41 countries (imported 07-08) |
| `ca_sac_codes` | 293 | Canadian SAC rural-urban classification (07-08) |
| `nhl_ca_sites` | 1,014 | Canadian National Historic Sites from Wikidata (07-08) |
| `ca_health_regions` | 21 | Canadian health region reference (07-08) |
| `crtc_stations` | 1 | CRTC broadcast table (placeholder, pending import) (07-08) |
| `emergency_stations` | 48,821 | US fire (34,888) + police (13,933) stations from OSM (imported 07-07) |
| `emergency_stations_rtree` | 48,821 | R-tree spatial index for emergency_stations (07-07) |
| `ekd_hierarchy_de` | 104,412 | German EKD Landeskirchen assignments (17 Landeskirchen) (07-18) |
| `catholic_diocese_de` | ~24 | German Catholic diocese mapping (07-18) |
| `zensus_religion_de` | 16+ | Zensus 2022 religion percentages by state (07-18) |
| `genesis_pop_gemeinde_de` | 12,098 | German Gemeinde population from Genesis API (07-18) |
| 07-18 | **German hierarchy enrichment** | **104,412 DE churches** mapped to 17 EKD Landeskirchen + 24 Catholic dioceses via GeoBoundaries ADM2 spatial join. Tables: `ekd_hierarchy_de`, `catholic_diocese_de`. 99.995% coverage (0 unassigned). Script: `scripts/enrichment/build_de_hierarchy.py`. |
### Hierarchy Tables

| Table | Rows | Denomination | Status |
|---|---|---|---|
| `anglican_hierarchy` | 69,058 | Anglican Communion | ✅ Completed |
| `orthodox_hierarchy` | 60,104 | Eastern Orthodox | ✅ Completed |
| `lutheran_hierarchy` | 57,322 | Lutheran (ELCA/LCMS/WELS) | ✅ Completed |
| `baptist_hierarchy` | 35,655 | Baptist (SBC) | ✅ Completed |
| `catholic_hierarchy` | 33,087 | Catholic | ✅ Completed |
| `lds_hierarchy` | 19,440 | LDS/Mormon | ✅ Completed |
| `jw_hierarchy` | 10,664 | Jehovah's Witnesses | ✅ Completed |
| `sa_hierarchy` | 2,869 | Salvation Army | ✅ Completed |
| `ahmadiyya_hierarchy` | 140 | Ahmadiyya Islam | ✅ Completed |
| `chabad_hierarchy` | 2,885 | Chabad Lubavitch | ✅ Completed |
| `bahai_hierarchy` | 1,192 | Baháʼí | ✅ Completed |

| `moravian_hierarchy` | 608 | Moravian Church | ✅ Completed |

| `chabad_hierarchy` | 2,885 | Chabad Lubavitch | ✅ Completed || `moravian_hierarchy` | 608 | Moravian Church | ✅ Completed |
- **Admin1 city fill**: ✅ **50,933 filled** in 71s via Natural Earth admin1 spatial join. Yemen 31K→governorate names. 204 unmatched. Script: `scripts/enrichment/fill_city_from_admin1.py`.| `bahai_hierarchy` | 1,192 | Baháʼí | ✅ Completed |

| `bahai_hierarchy` | 1,192 | Baháʼí | ✅ Completed |
- **Postal codes**: 74.9% globally (2.6M/3.5M). GeoNames codes across 41 countries.| `chabad_hierarchy` | 2,885 | Chabad Lubavitch | ✅ Completed || `moravian_hierarchy` | 608 | Moravian Church | ✅ Completed |

- **Country breakdown**: US 1,032K | IN 232K | BR 205K | JP 158K | ID 149K | DE 106K | GB 101K | CA 95K | FR 94K | IT 86K | TH 66K | SA 60K | MX 56K | PH 55K | ES 50K | TR 43K | PL 35K | YE 33K | TW 32K | RU 32K| `moravian_hierarchy` | 608 | Moravian Church | ✅ Completed |

- **Enrichment log**: 2,194,313 changes | **463,273** contact values | **619,860** Nominatim operations | 14 hierarchy tables | 111 census/election tables

- **Sikh classification**: **100% DeepSeek-reviewed** — 5,619 Sikh entries, 5,617 with `sikh_affiliation` populated. Landmark types: gurdwara 5,353, community_center 147, shrine 78, temple 27, school 11.| `bahai_hierarchy` | 1,192 | Baháʼí | ✅ Completed |

- **Muslim tradition coverage**: **100%** — all 401K Islam entries classified (17 traditions). Extended geo-priors cover 80+ countries.| `chabad_hierarchy` | 2,885 | Chabad Lubavitch | ✅ Completed |

- **Jain expansion**: 981 → 7,530 via jain-wiki SPARQL import (07-03). Temple 7,312, Community Center 666, Dharamshala 119, Tirth 16.| `ahmadiyya_hierarchy` | 140 | Ahmadiyya Islam | ✅ Completed |

- **Boston enrichment**: **924 Boston-area churches** enriched with property assessment data. 371 new entries from exempt property records (LUC=970/906). 7 religious schools from Boston Non-Public Schools. All DeepSeek-classified. 155 dupes merged. `boston_pid` column added for parcel IDs (457 unique PIDs). `boston_property_json` stores full assessment details (value, area, year built, condition).| `sa_hierarchy` | 2,869 | Salvation Army | ✅ Completed |

- **Ireland enrichment**: **1,596 Irish churches** — 1,391 from Register of Charities (DeepSeek-classified), 196 from Dublin/DLR Places of Worship, 9 pre-existing. 13 internal dupes merged. `cra_bn` column for Irish charity numbers.| `jw_hierarchy` | 10,664 | Jehovah's Witnesses | ✅ Completed |

- **Tables dropped**: `church_contacts` (replaced by `church_contact_values`), `church_rucc` (replaced by `rucc_codes` reference table)| `lds_hierarchy` | 19,440 | LDS/Mormon | ✅ Completed |

- **Column restructure**: `faith_tradition` → `tradition`, CFTLM taxonomy applied to all 3.29M records| `catholic_hierarchy` | 33,087 | Catholic | ✅ Completed |

- **LDS hierarchy**: 19,440 rows, 19,425 linked (99.99%). 19 Area Offices (5 PBOs + 14 intl). Maps at `data/lds_*.html`.| `baptist_hierarchy` | 35,655 | Baptist (SBC) | ✅ Completed |

- **LOC Phone Directory import**: ✅ **20,143 churches** from 494 digitized LOC telephone directories (126 cities, 1908-1975). **2,365 matched** to GRID by name+city. **6,019 phones** modernized (exchange→numeric with area codes). **1,857 church deaths** detected from directory disappearance (avg 7-9yr lifespan). LA growth animation: `docs/la_growth_map.html`. Death registry: `data/loc_phone_dirs/results/church_deaths.json`. Pipeline: `scripts/ingest/loc_phone_directories.py`.| `lutheran_hierarchy` | 57,322 | Lutheran (ELCA/LCMS/WELS) | ✅ Completed |

- **Security layer**: ✅ **940,618 US churches** have `nearest_fire_km` and `nearest_police_km`. Median fire 1.80 km, median police 3.43 km. 48,821 emergency stations sourced from OSM. Script: `scripts/enrichment/build_security_layer.py`.| `orthodox_hierarchy` | 60,104 | Eastern Orthodox | ✅ Completed |

- **CRA 2024 import**: **27,708 religious orgs** from open.canada.ca (83,762 total charities). 25,350 Christian (cat 30), 539 Muslim (40), 402 Jewish (50), 1,074 Buddhist/Other (60), 343 endowments (90). 8,042 names genuinely new. BN backfill matched 31,833 old + 35,079 non-CRA CA entries by exact name.| `anglican_hierarchy` | 69,058 | Anglican Communion | ✅ Completed |

- **2010 ARDA**: **77,128 county-denomination rows** in `arda_counts_2010`. 234 denominations across 3,141 counties. SBC declined 22% adherents (19.9M→15.5M) and 10.7% congregations (50.8K→45.3K) from 2010→2020.|---|---|---|---|

- **Bahrain mosques**: **974 new entries** from `data.gov.bh` (CC BY-like) — all MOSQUES, faith=Islam/Sunni. IDs 5,082,234–5,083,207. Total Bahrain: 1,266.| Table | Rows | Denomination | Status |

- **Bahrain religious schools**: **23 religious schools** from `data.gov.bh` private schools dataset — 20 Islamic, 3 Christian (Sacred Heart, St. Christopher's, Ebenezer). IDs 5,082,211–5,082,233.

- **Korea temples**: **154 new Buddhist temples** (Gyeongsangbuk-do shapefile from data.go.kr). IDs 5,083,208–5,083,361. 154 phone numbers added to church_contact_values. Korean Buddhism taxonomy.### Hierarchy Tables

- **TN parcel import**: **5,314 churches** imported from Tennessee IMPACT CAMA (86/95 counties). **4,714 churches**, **437 parsonages**, **135 schools**, **28 camp/retreat** facilities. 67.1% lack building_sqft, 47.0% have GPS. Script: `_filter_tn_parcels.py`, `_audit_tn_parcel_types.py`.

### Reference Tables| `genesis_pop_gemeinde_de` | 12,098 | German Gemeinde population from Genesis API (07-18) |

| `zensus_religion_de` | 16+ | Zensus 2022 religion percentages by state (07-18) |

| `nashville_cemeteries` | 14,382 | Nashville/Davidson County cemetery records: name, locale, street, parcel, graveyard_type (07-13) || `catholic_diocese_de` | ~24 | German Catholic diocese mapping (07-18) |

| `county_census_us` | 3,213 | Census ACS county-level demographics || `ekd_hierarchy_de` | 104,412 | German EKD Landeskirchen assignments (17 Landeskirchen) (07-18) |

| `church_census_catalog` | 150 | Metadata catalog for all census/election enrichment tables || `emergency_stations_rtree` | 48,821 | R-tree spatial index for emergency_stations (07-07) |

| `fcc_facilities` | 104,697 | FCC broadcast facilities || `emergency_stations` | 48,821 | US fire (34,888) + police (13,933) stations from OSM (imported 07-07) |

| `church_census_catalog` | 76 | Metadata catalog for all census/election enrichment tables || `crtc_stations` | 1 | CRTC broadcast table (placeholder, pending import) (07-08) |

| `arda_counts` | 74,000 | 2020 ARDA county-denomination adherent counts || `ca_health_regions` | 21 | Canadian health region reference (07-08) |

| `arda_counts_2010` | 77,128 | 2010 ARDA county-denomination adherent counts (234 denominations) || `nhl_ca_sites` | 1,014 | Canadian National Historic Sites from Wikidata (07-08) |

| `sba_ppp_loans` | 209,736 | SBA PPP COVID loans matched to churches || `ca_sac_codes` | 293 | Canadian SAC rural-urban classification (07-08) |
| `geonames_postal` | 1,390,149 | GeoNames postal codes for 41 countries (imported 07-08) |
```raw
HQ (id=40546, Church Office Building, SLC)
  ├── administered_by → 5 Presiding Bishop Offices (not Area Presidencies)
  ├── administered_by → 232 Temples (worldwide)
  │     ├── administered_by → 264 Stake Houses (same-state preferred, else nearest)
  │     │     └── served_by → 18,573 Meetinghouses (city+state, then nearest)
  │     └── affiliated_with → 347 Special types
  │           ├── 123 Seminaries
  │           ├── 110 Institutes
  │           ├── 93 Employment Centers
  │           ├── 11 Family History Centers
  │           ├── 4 Mission Offices
  │           ├── 4 Other
  │           └── 2 Storehouses
```

**5 unlinked** (expected): HQ root + 4 meetinghouses without GPS (Bloomington ID, Goshen UT, Manassa CO, Paris ID).

### Notes
- The 5 `area_office` rows are **Corporation of the Presiding Bishop** offices (legal/corporate entity for properties/finances), NOT geographic Area Presidencies. Annotated in `notes` column. Real Area Presidencies absent from dataset.
- Temples correctly link directly to HQ since Area Presidency records don't exist in our data.

### Future Opportunity: Real Area Office Records
Wikipedia lists **24 Areas** (18 international + 6 US). International Area Offices are real buildings:
Nairobi, Johannesburg, Accra, Hong Kong, Tokyo, São Paulo, Calgary/Toronto, Santo Domingo,
Guatemala City, Moscow, Frankfurt, London, Mexico City, Auckland, Quezon City, Lima, Buenos Aires.
US Areas administered from SLC HQ. Scraping these + geocoding would enable the proper hierarchy:
HQ → Area Office (24) → Temple (232) → Stake House (264) → Meetinghouse (18,573).
**Status**: 🔴 Not started — logged in /memories/repo/data-fixes.md

### Remaining Work
| Task | Description | Status |
|---|---|---|
| Name standardizer | Normalize LDS names (like JW normalizer) | ✅ Completed 07-04 |


#### FLDS / Restorationist Taxonomy

All groups under `Abrahamic/Christian/Other/Latter-day Saints/`:#### Existing Taxonomy Nodes



| Group | Data Count | Notes || **Independent Fundamentalist** | 0 | Not found in DB |

|---|---|---|| **Centennial Park** | 0 | DB hits are Baptist |

| **Mainline** (Church of Jesus Christ of Latter-day Saints) | ~21K | Well covered || **Righteous Branch** | 0 | DB hits are Church of God, not LDS |

| **Community of Christ** (RLDS) | 1 | Willow Springs MO || **Church of the Firstborn** | 0 | Not found in DB |

| **FLDS** (Warren Jeffs) | 8 | ✅ Already tagged || **Bickertonite** | 0 | Not found in DB |

| **Restoration Branches** | 32 | Community of Christ / RLDS splinters — IA, IL, MO, MI, OH, NE, FL, AK, TX || **Cutlerite** | 1 | Independence MO |


| **Remnant Church** | 11 | Independence MO hub — AR, CO, FL, MI, ON CA || **True and Living Church (TLC)** | 2 | Manti UT || **Strangite** | 3 | Lyons/Burlington WI |

| **Hedrickite / Temple Lot** | 5 | Independence MO + Canada || **Apostolic United Brethren (AUB)** | 2 | Lima UT, Riverton UT |
```raw
id=17  Abrahamic/Christian/Other/Latter-day Saints
id=166   ├── Church of Jesus Christ of Latter-day Saints
id=167   ├── Community of Christ
id=458   ├── FLDS
id=168   ├── LDS
id=459   │   └── LDS
id=169   ├── LDS / Mormon
id=170   ├── Latter-day Saints
id=171   ├── Mormon/LDS
id=460   ├── Other LDS
id=585   │   ├── Church of Jesus Christ of Latter Day Saints (Cutlerite)
id=586   │   ├── The Church of Jesus Christ (Bickertonite)
id=587   │   ├── Church of Jesus Christ of Latter Day Saints (Strangite)
id=588   │   ├── Church of Christ (Temple Lot / Hedrickite)
id=589   │   ├── Remnant Church of Jesus Christ of Latter Day Saints
id=590   │   ├── Church of the Firstborn of the Fulness of Times
id=591   │   ├── Righteous Branch of the Church of Jesus Christ of Latter-day Saints
id=592   │   ├── Centennial Park / The Work
id=593   │   ├── Apostolic United Brethren (AUB)
id=594   │   ├── True and Living Church of Jesus Christ of Saints of the Last Days (TLC)
id=595   │   ├── Independent Fundamentalist / Independent Priesthood
id=596   │   └── Restoration Branches / Independent Restorationist
id=172   └── The Church of Jesus Christ of Latter-day Saints
```
**Action**: ✅ FLDS duplicate (461) deleted. 12 restorationist groups added under `Other LDS` (id=460). Broken `Restorationist` node (id=462) fixed.

### Notes
- All LDS entries with GPS → IS a building. The function name identifies the ministry that operates there.
- Institutes/Seminaries are CES, outside the stake hierarchy — link directly to HQ.
- Bishop's Office is a room in a meetinghouse — part of the ward ministry, not a separate entity.
- Area Offices are structural placeholder nodes — very sparse in current data.

```sql
CREATE TABLE jw_hierarchy (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    parent_id INTEGER REFERENCES jw_hierarchy(id),
    church_id INTEGER REFERENCES churches(id) ON DELETE CASCADE,
    name TEXT NOT NULL,               -- Normalized name
    original_name TEXT,               -- Pre-normalization name
    jw_type TEXT NOT NULL CHECK(jw_type IN (
        'kingdom_hall', 'assembly_hall', 'circuit',
        'congregation', 'study', 'convention', 'bethel', 'other'
    )),
    jw_detail TEXT,                   -- Extracted detail (circuit name, congregation name, language)
    circuit_code TEXT,                -- e.g. 'AB-4A' for Alberta Circuit 4A
    city TEXT,
    state TEXT,
    country TEXT,
    lat REAL,
    lon REAL,
    parent_jw_type TEXT,              -- Type of parent (for quick queries)
    relationship TEXT CHECK(relationship IN (
        'meets_at',          -- Congregation → Kingdom Hall it meets in
        'belongs_to_circuit', -- Congregation → Circuit
        'served_by',         -- Circuit → Assembly Hall
        'affiliated_with'    -- General link
    )),
    notes TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    CONSTRAINT unique_link UNIQUE(church_id, parent_id, relationship)
);

CREATE INDEX idx_jw_hierarchy_type ON jw_hierarchy(jw_type);
CREATE INDEX idx_jw_hierarchy_circuit ON jw_hierarchy(circuit_code);
CREATE INDEX idx_jw_hierarchy_parent ON jw_hierarchy(parent_id);
```

## ✅ COMPLETED — JW Hierarchy (2026-06-24)

### Name Normalization
- **Script**: `scripts/db_maintenance/standardize_jw_names.py`
- **6,824 entries** normalized to canonical formats (Kingdom Hall of Jehovah's Witnesses — City, Assembly Hall, etc.)
- 14+ languages translated, 101 cities extracted from name prefixes
- Provenance logged to `provenance_log` + `enrichment_change_log`

### Hierarchy Table (`jw_hierarchy`)
- **Script**: `scripts/db_maintenance/create_jw_hierarchy.py`
- Table: `jw_hierarchy` — 10,664 rows after all cleanup
- **Types**: kingdom_hall (9,422), other (1,022), assembly_hall (201), bethel (14), study (5), convention (1)

### Congregation → Ministries Collapse
- **Script**: `scripts/db_maintenance/collapse_jw_congregations.py`
- Congregations are ministries that meet in a building, not independent entities
- **849 ministries** stored as JSON `ministries` column on parent KH
- **2,453 congregation rows deleted** from jw_hierarchy

### Fake Entry Cleanup
- **Script**: `scripts/db_maintenance/cleanup_fake_jw.py`
- **303 misclassified entries removed** (Spanish `IGLESIA` evangelical churches using "Jehovah" biblically)
- 59 ministries rehomed to real KHs, exclusion patterns added to `detect_jw_type()`

### Structural Linking
| Step | Script | Links |
|---|---|---|
| KH → Assembly Hall (province) | `link_jw_circuits.py` | 6,606 KHs served_by AH |
| AH → Bethel (country) | `link_jw_bethels.py` | 137 AHs affiliated_with bethel |
| Bethel → World HQ | `link_jw_hq.py` | 13 bethels → HQ (#16976) |
| Circuits → AH ministries (JSON) | `link_jw_circuits.py` | 125 circuits collapsed |
| **Total structural links** | | **6,756** across 4 levels |

### Hierarchy
```raw
HQ (#16976 WORLD HEADQUARTERS, Warwick NY)
  └→ 13 Bethels / Branch Offices (by country)
       └→ 201 Assembly Halls (regional, affiliated_with)
            └→ 9,422 Kingdom Halls (local, served_by)
                 └→ ministries JSON: [congregations, circuits]
```
### Lessons
- **Commit before checkpoint**: Always `db.commit()` before `PRAGMA wal_checkpoint()` — checkpoint on locked DB silently drops uncommitted changes
- **Physical first**: Buildings are infrastructure, functions are ministries stored as JSON
- **Spanish/Portuguese exclusion**: `IGLESIA`, `IGREJA`, `SANTIDAD`, `AVIVAMIENTO` patterns reject evangelical churches that use "Jehovah" in their name

## ✅ COMPLETED — Lutheran Hierarchy (2026-06-25)

### Table: `lutheran_hierarchy`
- **Script**: `scripts/db_maintenance/build_lutheran_synods.py`
- **57,322 rows** across 4 bodies (ELCA, LCMS, WELS, Other + AFLC, LCMC, NALC)
- Schema: `lutheran_type` (hq/synod/district/congregation), `body` (ELCA/LCMS/WELS/Other), `parent_id` (self-ref), `relationship` (member_of/administered_by/affiliated_with)

### Classification
| Body | Congregations | How |
|---|---|---|
| **ELCA** | 12,990 | Name patterns (8,204) + State heuristic (3,429) + Pre-classified (1,357) |
| **LCMS** | 10,485 | Name patterns (8,751) + State heuristic (1,536) + Pre-classified (198) |
| **WELS** | 1,124 | Name patterns (781) + Improved heuristics (325) + Pre-classified (18) |
| **Other** | 32,448 | Mostly non-US (Germany 7K, Sweden 3K, Denmark 2K, Norway 1.7K, Brazil 1.2K, Finland 800, etc.) |
| **AFLC/LCMC/NALC** | 20 | Minor Lutheran bodies with dedicated taxonomy entries |

### Hierarchy Structure
```raw
ELCA HQ (Chicago, id=3549211)
  └→ 64 Synods (by state/geography)
       └→ 9,564 Congregations [member_of]

LCMS HQ (St. Louis — virtual, 8885 Ladue Rd)
  └→ 35 Districts (by state/geography)
       └→ 9,083 Congregations [member_of]

WELS HQ (Waukesha WI, id=683803)
  └→ 800 Congregations [member_of]  (no district breakdown yet)

Other HQ (virtual umbrella)
  └→ 37,752 Congregations [member_of]  (mostly non-US national Lutheran bodies)
```

### Linking
- **9,508 / 9,564** ELCA congregations linked to synod by state (99.4%)
- **9,053 / 9,083** LCMS congregations linked to district by state (99.7%)
- Synod/district definitions sourced from Wikipedia (64 ELCA synods, 35 LCMS districts)
- Congregations matched by `churches.state` → synod/district state coverage map

### API Status for Lutheran Directories
| Body | API | Status |
|---|---|---|
| **ELCA** | `elca.org/directory/congregations` | 🔴 Auth0-gated (Webflow/Wized app) |
| **LCMS** | `locator.lcms.org/api/congregations` | 🔴 401 Unauthorized (was open) |
| **WELS** | `locator.wels.net`, `wels.net` | 🔴 403 Forbidden |

### Remaining Work
- WELS district breakdown (12 districts)
- Populate `synod`/`district` columns in `church_enrichment`
- Name-based classification for remaining US "Other" Lutherans (~10.5K US)
- Non-US Lutheran body assignment (Germany→EKD, Sweden→Church of Sweden, etc.)

## ✅ COMPLETED — Church Contact Values Migration (2026-06-25)

### New Table: `church_contact_values`
- **463,195 rows** — normalized contact storage replacing `church_contacts`
- Schema: `church_id`, `contact_type` (phone/email/website/facebook/etc.), `value`, `confidence`, `source`, `last_verified`, `is_primary`
- Per-value confidence tracking instead of per-record
- **Script**: `scripts/db_maintenance/create_contact_values.py`

### Migration
| Type | Migrated | From |
|---|---|---|
| Website | 398,913 | `church_contacts.website` |
| Phone | 47,467 | `church_contacts.phone` |
| Email | 16,815 | `church_contacts.email` |

### Cleanup
- Old `church_contacts` table **dropped** (627,565 rows, 30 columns) — data lives in `church_contact_values` only
- `e164_normalize` enrichment deduplicated (3,075 duplicate rows collapsed, 45% reduction)
- Provenance logged as `deprecate_church_contacts` and `dedup_e164`

## ✅ COMPLETED — ABRN Alaska Scrape (2026-06-25)
- **80 new Alaska Baptist (SBC) churches** imported from `alaskabrn.com/about/affiliated-churches/`
- 15 existing AK churches enriched with pastor names, phones, websites
- Source: `abrn_scraper`
- Church IDs: 5,077,611–5,077,690
- Associations: Chugach Baptist (29), Tanana Valley (19), Hatcher Pass (15), Tongass Baptist (8), At Large (6)

### ✅ 06-26 Europe + Israel Jewish scans
| Region | Entries | Moved out | Enrichment |
|---|---|---|---|
| Europe (39 countries) | 4,516 | 329 | 3,725 changes (3 phases) |
| Israel | 2,110 | 1 | 2,254 changes |

**Worldwide Judaism: 23,451 entries, 0 problematic landmark_types, 8,842 enrichment log entries, 393 faith corrections.**


### ✅ 06-26 — Jewish Confidence Backfill + IRS Verification
| Task | Result |
|---|---|
| **Confidence columns** | `jewish_confidence`, `jewish_classification_source`, `jewish_updated` created (mirrors Muslim pattern) |
| **Coverage** | 100% — all 23,451 Judaism entries scored |
| **Tier 0.95** | 6,247 entries — DeepSeek AI-verified |
| **Tier 0.85** | 17,202 entries — explicit CFTLM tradition |
| **Tier 0.70** | 2 entries — generic confidence_score fallback |
| **Tradition cleanup** | 1,621 entries normalized (Jewish→Rabbinic, Chabad→Orthodox (Chabad), etc.) |
| **IRS verification** | ✅ 6,099 entries all clean — 0 misclassifications |


### ✅ 06-26 — Jewish CFTLM Alignment Fix
| Task | Result |
|---|---|
| **Tradition normalization** | 286 non-canonical values → 12 canonical CFTLM traditions (Neolog→Conservative, Liberal→Reform, etc.) |
| **Taxonomy reassignment** | All 23,450 entries remapped from catch-all "Jewish" (id=242) to proper sub-nodes |
| **Tree restructure** | Old inverted tree (Orthodox/Hasidic under Reform) fixed; 16 stale nodes detached |
| **Edge cases** | 6 Christian-mapped entries fixed, 1 NULL taxonomy_id filled, 1 Messianic(Netzarita)→Christian |
| **Final state** | 0 NULL taxonomy_id, 0 Christian-mapped, 0 on old nodes, 0 non-canonical traditions |

### Taxonomy Distribution (post-fix)
| Tradition Node | Entries | % |
|---|---|---|
| Rabbinic (general) | 13,551 | 57.8% |
| Orthodox | 3,339 | 14.2% |
| Orthodox (Chabad) | 2,974 | 12.7% |
| Reform | 2,085 | 8.9% |
| Sephardic | 615 | 2.6% |
| Orthodox (Yeshiva) | 327 | 1.4% |
| Conservative | 326 | 1.4% |
| Orthodox (Hasidic) | 147 | 0.6% |
| Reconstructionist | 31 | 0.1% |
| Humanistic | 30 | 0.1% |
| Karaite (general) | 23 | 0.1% |
| Mizrahi | 2 | 0.0% |


## ✅ COMPLETED — Sikh DeepSeek Classification (2026-06-27)

### Scan Overview
- **Script**: `_scan_sikh_deepseek.py` (initial) + `_resume_sikh_deepseek.py` (resume after quota top-up)
- **5,925 entries** scanned across 70 countries via DeepSeek API
- Provenance logged as `scan_sikh_deepseek` + `scan_sikh_deepseek_resume`

### Results
| Metric | Initial Scan | Resume Scan | **Total** |
|--------|-------------|-------------|-----------|
| Moved out of Sikh | 67 | 241 | **308** |
| Landmark type changes | 3,508 | 1,907 | **5,415** |
| Tradition updates | 304 | 140 | **444** |
| IDs changed | 3,700 | 2,345 | **~5,925** |

### Where the 308 moved out went
| Faith | Count |
|-------|-------|
| Other | 170 |
| Buddhist | 100 |
| Hindu | 23 |
| Christian | 13 |
| Islam | 2 |

### Final Sikh State (5,619 entries)

**Landmark Types (dramatic improvement):**
| Type | Before | After | Change |
|------|--------|-------|--------|
| gurdwara | 136 | 5,353 | **+5,217** ✅ |
| community_center | 0 | 147 | +147 |
| shrine | 1,202 | 78 | -1,124 ✅ |
| temple | 4,567 | 27 | -4,540 ✅ |
| school | 0 | 11 | +11 |
| museum/library/other | 0 | 3 | +3 |

**Traditions:** Khalsa 5,016 · Singh Sabha 243 · Sikh (general) 142 · Nanaksar 93 · Ravidassia 53 · Ramgarhia 47 · Nirmala 7 · Namdhari 7 · Sikh (Ram Rai) 1

**Sikh Affiliations:** Gurdwara 4,501 · Sikh Shrine 752 · Gurdwara (Singh Sabha) 177 · Gurdwara (Nanaksar) 61 · Sikh Center 45 · Gurdwara (Ramgarhia) 40 · Gurdwara (Ravidassia) 29 · Khalsa School 9 · Gurdwara (Nirmala) 2 · Sikh Museum 1

**Enrichment log:** 6,539 entries from `deepseek_sikh_scan`, 5,736 unique IDs

### Columns Added
- `sikh_affiliation` — Gurdwara, Sikh Shrine, Sikh Center, Khalsa School, etc.
- `sikh_confidence` — 0.85 for DeepSeek-verified entries
- `sikh_classification_source` — `deepseek_sikh_scan`
- `sikh_updated` — timestamp

### Remaining Work
- 2 entries still unclassified (no sikh_affiliation)

---

### ✅ 06-27 — CFTLM Taxonomy: Indigenous + Ancient branches
| Task | Details |
|---|---|
| **Indigenous / Traditional** (id=609) | New umbrella under `Other` (id=6) for living oral traditions |
| **Australian Aboriginal** (id=610) | Dreaming traditions, mainland Australia |
| **Torres Strait Islander** (id=611) | Distinct Melanesian culture |
| **Ancient / Historical** (id=612) | New umbrella under `Other` (id=6) for dead/archaeological traditions |
| **Mesoamerican** (id=613) | Aztec, Maya, Olmec, Inca — extinct |

Note: European/Mediterranean/NE ancient traditions (Roman, Hellenistic, Egyptian, Mesopotamian, Norse, Celtic, etc.) were already classified under **Pagan** (id=53) with a rich subtree (IDs 614–637):
- `Ancient Mediterranean` → Roman Religion, Hellenistic Religion, Ancient Egyptian, Phoenician, Minoan, Etruscan
- `European Pagan` → Celtiberian, Celtic, Germanic, Slavic, Norse, Baltic
- `Ancient Near Eastern` → Mesopotamian, Parthian, Canaanite, Anatolian, Elamite
- `Prehistoric Religion` → Paleolithic, Neolithic, Megalithic

### Taxonomy Distinction
- **Indigenous / Traditional** = living continuous traditions tied to specific peoples (Australian Aboriginal, Torres Strait Islander, African Traditional, etc.)
- **Pagan** = European/Mediterranean polytheism (both ancient and neo-pagan revival)
- **Ancient / Historical** = non-European dead traditions, archaeological only
- **Animist** (id=39) = generic catch-all for unaffiliated animistic concepts

## ✅ COMPLETED — Aragón BIC Import (2026-06-27)

### Overview
- **Source**: Aragón Open Data — Bienes de Interés Cultural (CC BY 4.0)
- **Dataset**: 1,021 BIC entries in Aragón (Spain), **30 religious buildings** imported
- **Script**: `scripts/enrichment/_import_aragon_bic.py`
- **Data files saved**: `data/aragon_bic_puntos.csv`, `data/aragon_bic_puntos.geojson`, `data/aragon_bic_entornos.csv`, `data/aragon_bic_limites.csv`

### Imported Entries (IDs 5,078,892–5,078,921)
| Category | Count |
|---|---|
| Fortified churches (Iglesias Fortificadas) | 8 |
| Hermitages (Ermitas) | 7 |
| Church towers (Torres de Iglesia) | 11 |
| Marian / Virgin sites | 2 |
| Air-raid shelter under church | 1 |
| Castle-hermitage | 1 |

### Technical Notes
- Coordinates converted from UTM (EPSG:25830) → WGS84 via `pyproj.Transformer`
- All entries tagged as Christian (taxonomy_id=2) via `denomination` field
- Lesson: `churches.id` is NOT autoincrement — must compute `MAX(id)+1` manually (UNIQUE constraint on id column, which conflicts with rowid)
## ✅ COMPLETED — Pleiades Ancient Sites Import (2026-06-27)

### Overview
- **Source**: Pleiades gazetteer of ancient places (CC BY 3.0) — https://pleiades.stoa.org
- **Data package**: GIS CSV (`pleiades_gis_data.zip`, 42,170 places) at `data/pleiades/`
- **Filter**: temple, temple-2, sanctuary, shrine, altar, grove, pyramid place types
- **Script**: `scripts/enrichment/_import_pleiades.py`
- **1,702 ancient religious sites imported** (IDs 5,078,922–5,080,623)

### Taxonomy Breakdown
| Tradition | Taxonomy ID | Count |
|---|---|---|
| Roman Religion | 618 | 720 |
| Ancient Mediterranean (general) | 614 | 646 |
| Hellenistic Religion | 619 | 154 |
| Mesopotamian Religion | 630 | 97 |
| Ancient Egyptian Religion | 620 | 72 |
| Parthian Religion | 631 | 11 |
| Celtiberian Religion | 624 | 2 |

### Sample Sites
- Temple of Sulis Minerva (Bath, GB) — Roman Religion
- Pyramid of Khendjer (Egypt) — Ancient Egyptian
- Mithraeum of Lucretius Menander (Rome) — Roman Religion
- Sacred Area of S. Omobono (Rome) — Roman Religion
- Temple of Zeus at Cyrene (Libya) — Hellenistic
- Ehulhul (Harran, TR) — Mesopotamian
- Eanna (Uruk, IQ) — Mesopotamian
- Shrine of Venus Cloacina (Rome) — Roman Religion

### Reclassification (same day)
- **11 pre-existing entries retagged** to appropriate ancient faith nodes
- 2 Roman temples misclassified as Hindu (3) → Roman Religion (618)
- 5 megaliths/prehistoric sites → Megalithic/Neolithic (637/636)
- 1 dolmen misclassified as Islam (4) → Megalithic (637)
- 3 Pagan-named sites misclassified → Pagan (53)
### Ancient Faith Taxonomy (added 2026-06-27)

24 nodes added under `Other(6) > Pagan(53)` for pre-Christian religious classification:

```raw
Other (6)
  └── Pagan (53)
       ├── Ancient Mediterranean (614)
       │    ├── Roman Religion (618)         — Roman temples, mithraea, altars
       │    ├── Hellenistic Religion (619)   — Greek temples, oracles
       │    ├── Ancient Egyptian Religion (620) — pyramids, Egyptian temples
       │    ├── Phoenician / Carthaginian (621)
       │    ├── Minoan / Mycenaean (622)
       │    └── Etruscan Religion (623)
       ├── European Pagan (615)
       │    ├── Celtiberian Religion (624)   — Pre-Roman Iberia
       │    ├── Celtic Paganism (625)
       │    ├── Germanic Paganism (626)
       │    ├── Slavic Paganism (627)
       │    ├── Norse Religion (628)
       │    └── Baltic Paganism (629)
       ├── Ancient Near Eastern (616)
       │    ├── Mesopotamian Religion (630)  — Ziggurats, Babylonian/Assyrian temples
       │    ├── Parthian Religion (631)
       │    ├── Canaanite Religion (632)
       │    ├── Anatolian Religion (633)
       │    └── Elamite Religion (634)
       └── Prehistoric Religion (617)
            ├── Paleolithic Ritual Site (635)
            ├── Neolithic Ritual Site (636)  — Menhirs, henges
            └── Megalithic Religion (637)    — Dolmens, stone circles
```
## ✅ COMPLETED — Denomination Over/Under-Built Point Maps (2026-07-18)

### Script: `scripts/analysis/map_denom_over_under.py`
County-level church density vs. national average for 21 major US denomination groups.
Interactive Leaflet maps with layer toggles per category.

### Output: `outputs/denom_maps/index.html` + 21 per-denomination HTML maps

### Methodology
- **Rate** = churches per 100K population (county level, `county_fips_5` join to `county_census_us.total_pop`)
- **Ratio** = county rate / national average rate for that denomination
- **Over-built** (red) = ratio ≥ 2.0× | **Under-built** (blue) = ratio ≤ 0.33× | **Zero presence** (dark) = top-100 most populous counties with 0 churches
- Marker radius ∝ √(church count); popups show churches/pop/rate/ratio

### Key Results (validated visually)
| Denomination | Churches | Natl /100K | Over | Under |
|---|---|---|---|---|
| Baptist (non-SBC) | 105,506 | 32.3 | 1,185 | 293 |
| Non-Denominational | 37,288 | 11.5 | 911 | 44 |
| Methodist (mainline) | 35,742 | 11.1 | 1,337 | 187 |
| SBC | 31,894 | 10.2 | 1,215 | 411 |
| Pentecostal (broad) | 21,688 | 6.8 | 1,055 | 122 |
| Roman Catholic | 21,537 | 6.8 | 977 | 185 |
| Churches of Christ | 10,474 | 3.5 | 975 | 116 |
| Assemblies of God | 10,380 | 3.4 | 1,007 | 116 |

- **SBC**: over-built Bible Belt, under-built Northeast/Mountain West (textbook)
- **Catholic**: perfect inverse — over-built Upper Midwest/Northeast/S.Texas, under-built Bible Belt
- Patterns validate county FIPS + census joins end-to-end

### Taxonomy Lessons
- Always verify taxonomy IDs with **exact-name + church-count** queries before mapping — name LIKE matches hit noise nodes (e.g., "Episcopal" id=79 has 7,436 churches; "Episcopal Church" id=80 has only 43)
- Big generic nodes: Baptist=209/281, Methodist=380, Episcopal=79, Christian Church=317, Presbyterian=219
- Catholic rollup requires 42 taxonomy IDs (14 + Eastern rites + all religious orders 101–120)


**Distinction**: Indigenous/Traditional (living oral traditions) and Ancient/Historical (dead non-European) are separate branches under `Other(6)`. Pagan covers European/Mediterranean polytheism (both ancient and revival).

## Cloud-Native Operations (2026-07-18)

### Principle: Cloud-First When Possible
All GRID operations should prefer cloud-native patterns over local-only workflows. The workstation is the development environment; production data and publishing should live in the cloud.

### Git
- **Remote**: `git@github.com:charlesprescott/grid.git` (set up with: `git remote add origin git@github.com:charlesprescott/grid.git`)
- **Push after every session**: `git push origin master`
- **What's committed**: scripts/, gw_db/, gw_geo/, gw_filters/, reports/, docs/, pipeline/, sql/, requirements.txt, AGENTS.md, README.md
- **What's excluded** (.gitignore): churches.db (14.8GB), .venv/, backups/, data/staging/, .db files, temp scripts

### BigQuery
- **Project**: `american-rel-infra` / `American_Religious_Infrastructure`
- **Export**: `python scripts/db_maintenance/bq_export_all_tables.py` — exports all 27 tables as CSV → BQ
- **Auth**: gcloud ADC (`fibinachi@gmail.com`)
- **Demo views**: Vermont, NWT, Tamil Nadu slices for outreach demos
- **Run after any major DB change** to keep BQ in sync

### Substack
- **Subdomain**: `gridkeeper.substack.com`
- **Auth**: `SUBSTACK_COOKIE` env var (connect.sid cookie)
- **Publish**: `python scripts/outreach/publish_<topic>.py` (see `/memories/repo/substack-flow.md`)
- **Contact email**: `charles@gridataset.com`

### Backup Strategy
1. **Local**: Timestamped DB copies to `D:\backups\` after imports (GRID workflow Rule 3)
2. **Cloud**: BigQuery (full table export) after major changes
3. **Code**: Git push after every session
4. **Reports**: Committed to git (in `reports/`) + published to Substack

### Checklist: End-of-Session
- [ ] Git commit + push
- [ ] BQ export if DB was modified
- [ ] Update AGENTS.md with new entries
- [ ] Clean up temp `_check_*.py` / `_fix_*.py` scripts (remove or archive)
- [ ] Substack draft/publish if report was generated


## Cloud-Native Operations (2026-07-18)

### Principle: Cloud-First When Possible
All GRID operations should prefer cloud-native patterns over local-only workflows. The workstation is the development environment; production data and publishing should live in the cloud.

### Git
- **Remote**: `git@github.com:charlesprescott/grid.git` (set up with: `git remote add origin git@github.com:charlesprescott/grid.git`)
- **Push after every session**: `git push origin master`
- **What's committed**: scripts/, gw_db/, gw_geo/, gw_filters/, reports/, docs/, pipeline/, sql/, requirements.txt, AGENTS.md, README.md
- **What's excluded** (.gitignore): churches.db (14.8GB), .venv/, backups/, data/staging/, .db files, temp scripts

### BigQuery
- **Project**: `american-rel-infra` / `American_Religious_Infrastructure`
- **Export**: `python scripts/db_maintenance/bq_export_all_tables.py` -- exports all 27 tables as CSV -> BQ
- **Auth**: gcloud ADC (`fibinachi@gmail.com`)
- **Demo views**: Vermont, NWT, Tamil Nadu slices for outreach demos
- **Run after any major DB change** to keep BQ in sync

### Substack
- **Subdomain**: `gridkeeper.substack.com`
- **Auth**: `SUBSTACK_COOKIE` env var (connect.sid cookie)
- **Publish**: `python scripts/outreach/publish_<topic>.py` (see `/memories/repo/substack-flow.md`)
- **Contact email**: `charles@gridataset.com`

### Backup Strategy
1. **Local**: Timestamped DB copies to `D:\backups\` after imports (GRID workflow Rule 3)
2. **Cloud**: BigQuery (full table export) after major changes
3. **Code**: Git push after every session
4. **Reports**: Committed to git (in `reports/`) + published to Substack

### Checklist: End-of-Session
- [ ] Git commit + push
- [ ] BQ export if DB was modified
- [ ] Update AGENTS.md with new entries
- [ ] Clean up temp `_check_*.py` / `_fix_*.py` scripts (remove or archive)
- [ ] Substack draft/publish if report was generated


## Cloud-Native Operations (2026-07-18)

### Principle: Cloud-First When Possible
All GRID operations should prefer cloud-native patterns over local-only workflows. The workstation is the development environment; production data and publishing should live in the cloud.

### Git
- **Remote**: git@github.com:charlesprescott/grid.git
- **Push after every session**: git push origin master
- **What is committed**: scripts/, gw_db/, gw_geo/, gw_filters/, reports/, docs/, pipeline/, sql/, requirements.txt, AGENTS.md, README.md
- **What is excluded** (.gitignore): churches.db (14.8GB), .venv/, backups/, data/staging/, .db files, temp scripts

### BigQuery
- **Project**: american-rel-infra / American_Religious_Infrastructure
- **Export**: python scripts/db_maintenance/bq_export_all_tables.py
- **Auth**: gcloud ADC (fibinachi@gmail.com)
- **Run after any major DB change** to keep BQ in sync

### Substack
- **Subdomain**: gridkeeper.substack.com
- **Auth**: SUBSTACK_COOKIE env var
- **Contact email**: charles@gridataset.com

### Backup Strategy
1. **Local**: Timestamped DB copies to D:\backups\ after imports
2. **Cloud**: BigQuery after major changes
3. **Code**: Git push after every session
4. **Reports**: Committed to git + published to Substack

### End-of-Session Checklist
- [ ] Git commit + push
- [ ] BQ export if DB was modified
- [ ] Update AGENTS.md with new entries
- [ ] Clean up temp scripts
- [ ] Substack draft/publish if report was generated
