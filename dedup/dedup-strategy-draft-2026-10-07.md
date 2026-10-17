# GRID dedup strategy (draft, 2026-10-07)

## A. Church records: current state

- 4,979,550 rows. 383,661 marked `merged` (7.7%), pointing at 311,847 canonicals. Soft-merge model: dupes kept with `status='merged'` + `dedup_canonical_id` pointer. No hard deletes in the current generation (older scripts did delete; `_gps_dedup_map` no longer exists).
- Method used: `name_transliterated` + GPS rounded to 4dp (~11m); survivor = most non-null columns; NULLs merged onto survivor; child tables repointed.
- Graph audit (`quality_sprint/audit_dedup.py`, run 2026-10-07): 7,346 self-loops (merged rows pointing at themselves), 10,130 chained pointers (merged->merged->canonical), 0 dangling targets.
- Largest cluster: canonical 2297155 absorbed 489 CRA cross-year duplicates (same LDS church, cra_2011 vs cra_2018 filings). Legitimate.
- 131,502 merged rows (34%) disagree with their canonical on `taxonomy_id`; 11,705 on `movement_id`. Classification was never reconciled at merge time; survivor kept its own.
- Remaining volume: exact name+GPS dupes ~0 (2% sample found zero groups); fuzzy same-name/near-coords ~50 pairs table-wide; 111,018 rows have no GPS and can't be GPS-matched; 4.27M rows have NULL status (never confirmed either way).

## B. Taxonomy nodes: duplicate survey

- X-under-X pattern, 20 sets (rename, don't merge): the child is the "unspecified" bucket holding most churches. Biggest: Sunni 484 (130,538 direct) under Sunni 31; Baptist 281 (139,880) under Baptist 209; Methodist 380 (50,066) under Methodist 215. Fix = rename child to "X (unspecified)".
- True duplicates, mechanical: Zaydi 230 (0 churches) -> 487 (1,652), same parent 29; Ibadhi 224 (0) -> Ibadi 490 (82), spelling variant, same parent 28; 'Church of God (Cleveland)' 395 (4) -> 396 'Church of God (Cleveland, TN)' (7,753); LDS aliases 169/171/172 (0 each) -> 166 (18,290).
- Legitimately distinct (rename for clarity only): Orthodox 18 (Eastern Orthodox, 7,469) vs 542 (Orthodox Judaism, 3,223); Other 6/28/52/541 are per-parent buckets (root / Islam / root / Judaism).
- Judgment calls for Charles: UU 160 (380 churches, under Christian) vs 250 (55, under Non-religious); CoG Anderson 394 (under Pentecostal) vs 338 (under Holiness); Mountain Assembly 340 (under Holiness, 0) vs 399 (under Pentecostal, 12); Sufi 30 (0, under Islam) vs 482 (3,083, under Sunni).

## C. Recommended strategy

Church records:
1. Repair the graph first: clear 7,346 self-loops, flatten 10,130 chains to final canonicals. Mechanical, safe.
2. Get Charles's rule for the 131K taxonomy disagreements (canonical-wins vs most-confident-wins) before reconciling.
3. Next passes: (a) 111K no-GPS rows via name+website/phone/address matching; (b) fuzzy-name + tight-GPS for spelling variants; (c) exact name+GPS on new ingests only, not full rescans.
4. Enforce at ingest: dedup check before insert, so the queue stops growing.

Taxonomy nodes:
5. Apply mechanical renames + true merges with rollback SQL each (repoint churches' `taxonomy_id`, reparent children, fix `full_path`, delete loser, log provenance).
6. Present the 4 judgment-call sets to Charles before touching them.
