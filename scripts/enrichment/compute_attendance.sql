-- ==========================================================================
-- SQL ATTENDANCE COMPUTATION
-- ==========================================================================
-- Computes estimated_attendance and attendance_confidence for every church
-- using ARDA county-level adherent and congregation counts.
--
-- Algorithm (per denomination + county pair):
--   C = arda_congregations  (from arda_counts)
--   A = arda_adherents      (from arda_counts)
--   N = count of our churches in that county/denom pair
--
--   C=0 or A=0           → NULL, 0.0
--   C=1 AND N=1          → A, 1.0
--   C=N                  → A/N, 0.9
--   C>N                  → A/C, 0.7
--   C<N                  → A/N, 0.8
--
-- PREREQUISITES:
--   1. arda_counts table exists (run build_arda_counts.py)
--   2. arda_denom_map table exists (code → denomination_name)
--   3. churches table has denomination (text) and county_fips columns
--
-- USAGE:
--   Run this SQL against churches.db via:
--   sqlite3 churches.db < scripts/enrichment/compute_attendance.sql
--   or in Python: cur.executescript(open('file.sql').read())
-- ==========================================================================

-- ── Step 1: Add output columns ──────────────────────────────────────────
ALTER TABLE churches ADD COLUMN estimated_attendance INTEGER;
ALTER TABLE churches ADD COLUMN attendance_confidence REAL DEFAULT 0.0;

-- ── Step 2: Create denomination code lookup table ──────────────────────
-- This stores keyword patterns that map denomination text → ARDA code.
DROP TABLE IF EXISTS arda_denom_lookup;

CREATE TABLE arda_denom_lookup (
    arda_code TEXT NOT NULL,
    keyword TEXT NOT NULL,
    match_type TEXT NOT NULL DEFAULT 'keyword'  -- 'exact' or 'keyword'
);

-- Insert exact matches from arda_denom_map
INSERT INTO arda_denom_lookup (arda_code, keyword, match_type)
SELECT m.code, LOWER(m.denomination_name), 'exact'
FROM arda_denom_map m
WHERE m.code IN (SELECT DISTINCT denom_code FROM arda_counts);

-- Insert keyword-based matches (ordered most-specific first)
INSERT INTO arda_denom_lookup (arda_code, keyword, match_type) VALUES
    ('COGIC', 'church of god in christ', 'keyword'),
    ('AMEZ', 'african methodist episcopal zion', 'keyword'),
    ('AME', 'african methodist episcopal', 'keyword'),
    ('CME', 'christian methodist episcopal', 'keyword'),
    ('PCUSA', 'presbyterian church (u.s.a.)', 'keyword'),
    ('PCUSA', 'presbyterian church usa', 'keyword'),
    ('PCUSA', 'presbyterian church (usa)', 'keyword'),
    ('PCUSA', 'pcusa', 'keyword'),
    ('PCA', 'presbyterian church in america', 'keyword'),
    ('PCA', 'pca', 'keyword'),
    ('EPC', 'evangelical presbyterian', 'keyword'),
    ('OPC', 'orthodox presbyterian', 'keyword'),
    ('RCA', 'reformed church in america', 'keyword'),
    ('CRC', 'christian reformed', 'keyword'),
    ('ELCA', 'evangelical lutheran', 'keyword'),
    ('ELCA', 'elca', 'keyword'),
    ('LCMS', 'lutheran church--missouri synod', 'keyword'),
    ('LCMS', 'missouri synod', 'keyword'),
    ('LCMS', 'lcms', 'keyword'),
    ('UMC', 'united methodist', 'keyword'),
    ('UMC', 'free methodist', 'keyword'),
    ('WES', 'wesleyan', 'keyword'),
    ('SBC', 'southern baptist', 'keyword'),
    ('NMBC', 'national baptist convention usa', 'keyword'),
    ('ABC', 'american baptist', 'keyword'),
    ('FWB', 'free will baptist', 'keyword'),
    ('ABC', 'american baptist', 'keyword'),
    ('COC', 'church of christ', 'keyword'),
    ('COC', 'churches of christ', 'keyword'),
    ('CCCC', 'christian church (disciples', 'keyword'),
    ('CCCC', 'disciples of christ', 'keyword'),
    ('UCC', 'united church of christ', 'keyword'),
    ('UCC', 'congregational christian', 'keyword'),
    ('NAZ', 'nazarene', 'keyword'),
    ('NAZ', 'church of the nazarene', 'keyword'),
    ('AGC', 'assemblies of god', 'keyword'),
    ('AGC', 'assembly of god', 'keyword'),
    ('CGCT', 'church of god (cleveland', 'keyword'),
    ('CGAI', 'church of god of prophecy', 'keyword'),
    ('CCNA', 'calvary chapel', 'keyword'),
    ('EFCA', 'evangelical free church', 'keyword'),
    ('ECC', 'evangelical covenant', 'keyword'),
    ('CMA', 'christian and missionary alliance', 'keyword'),
    ('VINE', 'vineyard', 'keyword'),
    ('SDAC', 'seventh-day adventist', 'keyword'),
    ('SDAC', 'seventh day adventist', 'keyword'),
    ('FOUR', 'foursquare', 'keyword'),
    ('EC', 'episcopal church', 'keyword'),
    ('EC', 'episcopal', 'keyword'),
    ('CATH', 'roman catholic', 'keyword'),
    ('CATH', 'catholic', 'keyword'),
    ('LDS', 'latter-day saint', 'keyword'),
    ('LDS', 'mormon', 'keyword'),
    ('LDS', 'community of christ', 'keyword'),
    ('JW', 'jehovah', 'keyword'),
    ('UUA', 'unitarian universalist', 'keyword'),
    ('UUA', 'unitarian', 'keyword'),
    ('SALV', 'salvation army', 'keyword'),
    ('ORTH', 'orthodox', 'keyword'),
    ('GRK', 'greek orthodox', 'keyword'),
    ('OCA', 'orthodox church in america', 'keyword'),
    ('BRN', 'brethren', 'keyword'),
    ('MENN', 'mennonite', 'keyword'),
    ('FRND', 'quaker', 'keyword'),
    ('FRND', 'religious society of friends', 'keyword'),
    ('NOND', 'non-denominational', 'keyword'),
    ('NOND', 'interdenominational', 'keyword'),
    ('NOND', 'non denominational', 'keyword'),
    ('BAPT', 'baptist', 'keyword'),
    ('BAPT', 'missionary baptist', 'keyword'),
    ('MUS', 'muslim', 'keyword'),
    ('MUS', 'islam', 'keyword'),
    ('MUS', 'mosque', 'keyword'),
    ('JEW', 'jewish', 'keyword'),
    ('JEW', 'synagogue', 'keyword'),
    ('JEW', 'judaism', 'keyword');

-- Create index for faster lookup
CREATE INDEX idx_denom_lookup_keyword ON arda_denom_lookup(keyword);

-- ── Step 3: Build a temp table with resolved ARDA codes ─────────────────
DROP TABLE IF EXISTS _church_arda;

-- First try exact matches, then keyword matches
-- Using a LEFT JOIN approach to handle multiple possible matches
CREATE TABLE _church_arena AS
WITH church_denom AS (
    SELECT c.id, c.denomination, c.county_fips,
           LOWER(TRIM(c.denomination)) AS denom_lower
    FROM churches c
    WHERE c.county_fips IS NOT NULL AND c.county_fips != ''
      AND c.denomination IS NOT NULL AND c.denomination != ''
),
exact_matches AS (
    SELECT cd.id, cd.county_fips, lk.arda_code
    FROM church_denom cd
    JOIN arda_denom_lookup lk ON lk.match_type = 'exact'
                              AND cd.denom_lower = lk.keyword
),
keyword_matches AS (
    SELECT cd.id, cd.county_fips, lk.arda_code,
           ROW_NUMBER() OVER (
               PARTITION BY cd.id
               ORDER BY LENGTH(lk.keyword) DESC  -- most specific match first
           ) AS rn
    FROM church_denom cd
    JOIN arda_denom_lookup lk ON lk.match_type = 'keyword'
                              AND cd.denom_lower LIKE '%' || lk.keyword || '%'
)
SELECT em.id, em.county_fips, em.arda_code
FROM exact_matches em
UNION
SELECT km.id, km.county_fips, km.arda_code
FROM keyword_matches km
WHERE km.rn = 1
  AND km.id NOT IN (SELECT id FROM exact_matches)
ORDER BY id;

-- ── Step 4: Count N = how many of our churches per (code, county) ──────
DROP TABLE IF EXISTS _county_denom_counts;

CREATE TABLE _county_denom_counts AS
SELECT ca.arda_code, ca.county_fips, COUNT(*) AS our_churches
FROM _church_arena ca
GROUP BY ca.arda_code, ca.county_fips;

CREATE INDEX idx_cdc ON _county_denom_counts(arda_code, county_fips);

-- ── Step 5: Compute attendance using the algorithm ─────────────────────
-- For each (code, county) pair, apply rules:
--   C=0 or A=0  → NULL, 0.0
--   C=1 AND N=1 → A, 1.0
--   C=N         → A/N, 0.9
--   C>N         → A/C, 0.7
--   C<N         → A/N, 0.8

DROP TABLE IF EXISTS _attendance_results;

CREATE TABLE _attendance_results AS
SELECT ca.id AS church_id,
       CASE
           WHEN ac.arda_congregations = 0 OR ac.arda_adherents = 0 THEN NULL
           WHEN ac.arda_congregations = 1 AND cdc.our_churches = 1
               THEN ac.arda_adherents
           WHEN ac.arda_congregations = cdc.our_churches
               THEN ROUND(CAST(ac.arda_adherents AS REAL) / cdc.our_churches)
           WHEN ac.arda_congregations > cdc.our_churches
               THEN ROUND(CAST(ac.arda_adherents AS REAL) / ac.arda_congregations)
           ELSE  -- ac.arda_congregations < cdc.our_churches
               ROUND(CAST(ac.arda_adherents AS REAL) / cdc.our_churches)
       END AS estimated_attendance,
       CASE
           WHEN ac.arda_congregations = 0 OR ac.arda_adherents = 0 THEN 0.0
           WHEN ac.arda_congregations = 1 AND cdc.our_churches = 1 THEN 1.0
           WHEN ac.arda_congregations = cdc.our_churches THEN 0.9
           WHEN ac.arda_congregations > cdc.our_churches THEN 0.7
           ELSE 0.8  -- ac.arda_congregations < cdc.our_churches
       END AS attendance_confidence
FROM _church_arena ca
JOIN _county_denom_counts cdc
    ON cdc.arda_code = ca.arda_code AND cdc.county_fips = ca.county_fips
JOIN arda_counts ac
    ON ac.denom_code = ca.arda_code AND ac.county_fips = ca.county_fips;

-- ── Step 6: Write results back to churches table ───────────────────────
-- SQLite doesn't support UPDATE ... FROM, so use correlated subqueries
BEGIN TRANSACTION;

UPDATE churches
SET estimated_attendance = (
    SELECT ar.estimated_attendance
    FROM _attendance_results ar
    WHERE ar.church_id = churches.id
),
    attendance_confidence = (
    SELECT ar.attendance_confidence
    FROM _attendance_results ar
    WHERE ar.church_id = churches.id
)
WHERE id IN (SELECT church_id FROM _attendance_results WHERE estimated_attendance IS NOT NULL);

COMMIT;

-- Also set confidence to 0.0 for churches that had no ARDA match
UPDATE churches
SET attendance_confidence = 0.0
WHERE county_fips IS NOT NULL AND county_fips != ''
  AND denomination IS NOT NULL AND denomination != ''
  AND estimated_attendance IS NULL;

-- ── Step 7: Cleanup temp tables ────────────────────────────────────────
DROP TABLE IF EXISTS _church_arena;
DROP TABLE IF EXISTS _county_denom_counts;
DROP TABLE IF EXISTS _attendance_results;

-- ── Step 8: Verify results ─────────────────────────────────────────────
SELECT 'Total churches' AS metric, COUNT(*) AS value FROM churches
UNION ALL
SELECT 'With estimated_attendance', COUNT(*) FROM churches WHERE estimated_attendance IS NOT NULL
UNION ALL
SELECT 'conf=1.0 (C=1, N=1)', COUNT(*) FROM churches WHERE attendance_confidence = 1.0
UNION ALL
SELECT 'conf=0.9 (C=N)', COUNT(*) FROM churches WHERE attendance_confidence = 0.9
UNION ALL
SELECT 'conf=0.8 (C<N)', COUNT(*) FROM churches WHERE attendance_confidence = 0.8
UNION ALL
SELECT 'conf=0.7 (C>N)', COUNT(*) FROM churches WHERE attendance_confidence = 0.7
UNION ALL
SELECT 'conf=0.0 (no match)', COUNT(*) FROM churches WHERE attendance_confidence = 0.0
ORDER BY metric;
