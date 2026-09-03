-- =============================================================================
-- church_building_sqft.sql
-- Spatial join: churches → Overture Maps building footprints → square footage
--
-- Uses bigquery-public-data.overture_maps.building (2.5B buildings worldwide).
-- Filters to US/Canada via bbox. ST_AREA() computes m² from GEOGRAPHY polygons.
--
-- NOTE: Requires bigquery.jobs.create + bigquery.tables.getData permissions
-- on bigquery-public-data. If unavailable, load a subset to your own project.
-- =============================================================================

-- Step 1: Create/replace the geography view for churches
CREATE OR REPLACE VIEW `american-rel-infra.American_Religious_Infrastructure.vw_church_geo` AS
SELECT 
  *,
  ST_GEOGPOINT(longitude, latitude) AS geo
FROM `american-rel-infra.American_Religious_Infrastructure.churches`
WHERE latitude IS NOT NULL
  AND longitude IS NOT NULL;

-- Step 2: Spatial join — find the building each church falls within
-- For each church point, find the building polygon that contains it (or nearest)
-- and capture the building area in m² and sqft.
--
-- ADJUST the footprint table reference below to your source.
CREATE OR REPLACE TABLE `american-rel-infra.American_Religious_Infrastructure.church_building_sqft` AS

WITH churches AS (
  SELECT id, name, city, state, denomination, entity_type,
         parent_church_id, latitude, longitude, geo
  FROM `american-rel-infra.American_Religious_Infrastructure.vw_church_geo`
),

-- === ADJUST this CTE if loading your own subset ===
footprints AS (
  SELECT 
    geometry,                              -- GEOGRAPHY column (polygon)
    ST_AREA(geometry) AS area_m2,
    ST_AREA(geometry) * 10.7639 AS area_sqft
  FROM `bigquery-public-data.overture_maps.building`
  WHERE bbox.xmin BETWEEN -180 AND -50      -- US/Canada longitude range
    AND bbox.xmax BETWEEN -180 AND -50
    AND bbox.ymin BETWEEN 15 AND 72         -- US/Canada latitude range
    AND bbox.ymax BETWEEN 15 AND 72
),

-- Find all buildings within 75m of each church, rank by best match
church_buildings AS (
  SELECT 
    c.id AS church_id,
    c.name, c.city, c.state, c.denomination, c.entity_type,
    c.parent_church_id, c.latitude, c.longitude,
    f.area_m2, f.area_sqft,
    ST_WITHIN(c.geo, f.geometry) AS point_in_building,
    ST_DISTANCE(c.geo, f.geometry) AS distance_m,
    ROW_NUMBER() OVER (
      PARTITION BY c.id 
      ORDER BY 
        ST_WITHIN(c.geo, f.geometry) DESC,  -- building containing the point first
        f.area_sqft DESC,                     -- then largest building
        ST_DISTANCE(c.geo, f.geometry) ASC   -- then closest
    ) AS rn
  FROM churches c
  JOIN footprints f
    ON ST_DWITHIN(c.geo, f.geometry, 75)     -- 75 meter search radius
)

SELECT 
  church_id, name, city, state, denomination, entity_type,
  parent_church_id, latitude, longitude,
  ROUND(area_m2, 2) AS building_area_m2,
  ROUND(area_sqft, 2) AS building_area_sqft,
  ROUND(distance_m, 2) AS distance_to_building_m,
  point_in_building
FROM church_buildings
WHERE rn = 1;  -- best match per church
