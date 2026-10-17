# Cook County Longitudinal Church Benchmark — Pipeline Run Order

Staged 2026-10-17 from the originals (copies; no logic changed).
Provenance: scripts 1–5 from `~/workspace/zenodo-deposits/chicago-benchmark-v1.0/work/`,
scripts 6–8 from `~/workspace/grid/chicago-benchmark/`.

Methodology: `../zenodo-deposits/chicago-benchmark-v1.0/cook-benchmark-v1.0-2026-10-13-methodology.md`
Schema spec: `../zenodo-deposits/chicago-benchmark-v1.0/schema-spec-v01.md`
Zenodo deposit: DOI 10.5281/zenodo.23365873

## Run order

| # | Step | Script | Inputs | Outputs |
|---|---|---|---|---|
| 0 | 1926 acquisition | `1926-cook-scraper.py` (fetch/parse library) + `pull_worker.py --ids staging/ids_workerN.txt --out staging/1926_wN.jsonl` | religiousecologies.org record pages (polite scrape, 1.5s delay) | `staging/1926_cook_raw.jsonl`, `staging/1926_w{0,1,2}.jsonl` (in `../staging/`) |
| 1 | 1926 audit | `parse_1926.py` | `staging/1926_cook_raw.jsonl` | stdout audit (record counts, missing fields) — verification only |
| 2 | 1951/1963 directory extraction | **CODE MISSING** — see note below | archive.org phone-directory scans (call_nos `usteledirec*`) | `cook_phonebooks.db` tables `listings`, `directory_runs` |
| 3 | 1951/1963 geocoding | **NO DRIVING SCRIPT** — ad-hoc run 2026-08-13 | `cook_phonebooks.db` listings addresses | `cook_phonebooks.db` table `geocode` (addr_key, lat, lon, match_type) |
| 4 | Cross-era linkage (1951↔1963) | `link_1951_1963.py` (uses `linklib.py`) — run from the dir containing `cook_phonebooks.db` | `cook_phonebooks.db` (listings + geocode) | `linkage_1951_1963.json` |
| 5 | 2026 slice remap | `dedup_production_v1.py` + `mig_*.py` (in `../../repair-staging-global-2026-10/dedup/`) | 2026 GRID Cook County slice | `cook_remap.csv` |
| 6 | Build v1 | `build_v1.py` (uses `linklib.py`) — run from the dir containing `linkage_1951_1963.json`, `cook_phonebooks.db`, `cook_remap.csv` | linkage JSON + phonebooks DB + remap CSV | `observations_v1.csv`, `entities_v1.csv`, `linkage_log_v1.json` |
| 7 | 1926 integration | `integrate_1926.py` (uses `linklib.py`) — paths hardcoded to `../staging/` and `../zenodo-deposits/chicago-benchmark-v1.0/work/` | staging JSONL + `observations_v1.csv` + `entities_v1.csv` | `schedules_1926.csv`, `links_1926.json`, `observations_v2.csv`, `entities_v2.csv` |
| 8 | Export / deposit | `deposit4.py` (general uploader, in `../../repair-staging-global-2026-10/zenodo-deposits/`) | v2 CSVs + docs | Zenodo deposit |

## Known gaps (do not re-run blind)

1. **Step 2 extraction code is unrecovered.** The 1951/1963 listings were extracted
   2026-08-13 via the `multiparse` document-parsing service (per `directory_runs.provider`)
   from archive.org scans (`usteledirec04820x`, `usteledirec04826x`, `usteledirec04932x`,
   `usteledirec04875x`, `usteledirec04876x`). No driver script, prompt set, or scan-loop
   code was found on the VM workspace or on E:\grid (searched *.py/*.ipynb/*.md/*.txt for
   `multiparse`, `usteledirec`, `directory_runs`, `cook_phonebooks`). Re-running for a new
   metro requires reconstructing this stage. Reconstruction spec: feed each directory scan
   (PDF) to a document-vision parser, extract (name, address, phone, denomination,
   confidence) per listing, write `listings` + `directory_runs` rows with provider and
   timestamp provenance.
2. **Step 3 geocoding has no driving script.** 1,243 addresses geocoded 2026-08-13 with
   `match_type` in {Exact: 135, Non_Exact: 921, Tie: 21, No_Match: 166}. Generic geocoders
   exist (`E:\grid\scripts\enrichment\forward_geocode_nominatim.py`,
   `fill_addresses_mapbox.py`, `fill_addresses_reverse.py`) but the benchmark's historic
   pass was ad-hoc; staging DBs `cook_mapbox_results.db` / `cook_reverse_address_fill.db`
   survive on E:\grid as evidence of the Mapbox + reverse-fill passes.
3. **Hardcoded absolute paths.** `integrate_1926.py`, `parse_1926.py`, and `pull_worker.py`
   hardcode `/home/hatch/workspace/...` paths. Left as-is per preserved-script discipline;
   re-point (or run from the original dirs) before re-running.
4. **Export mismatch.** Schema spec says Parquet is the primary package; the Zenodo deposit
   shipped CSV only. No re-export performed — open item for Charles.

## For a new metro

Checklist: (a) acquire the era sources (1926-equivalent schedules, directory scans);
(b) reconstruct step 2 extraction; (c) geocode historic addresses (step 3);
(d) run steps 4–7 in order with the metro's DB; (e) deposit with step 8.
