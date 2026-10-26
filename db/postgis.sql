-- Optional target schema for later managed deployment. Requires PostgreSQL + PostGIS.
-- Only create with a properly configured PostGIS database administrator.
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE SCHEMA IF NOT EXISTS uev;
CREATE TABLE IF NOT EXISTS uev.sources (
 id text PRIMARY KEY, title text NOT NULL, reference_year integer NOT NULL,
 license text NOT NULL, confidence text NOT NULL, is_demo boolean NOT NULL DEFAULT false
);
CREATE TABLE IF NOT EXISTS uev.spatial_assets (
 id text PRIMARY KEY,
 layer text NOT NULL CHECK (layer IN ('charging','candidates','grid','mobility')),
 name text NOT NULL, district text NOT NULL,
 geometry geometry(Point,4326) NOT NULL,
 properties jsonb NOT NULL DEFAULT '{}'::jsonb,
 source_id text NOT NULL REFERENCES uev.sources(id)
);
CREATE INDEX IF NOT EXISTS spatial_assets_gix ON uev.spatial_assets USING GIST(geometry);
CREATE INDEX IF NOT EXISTS spatial_assets_layer_district ON uev.spatial_assets(layer,district);
CREATE TABLE IF NOT EXISTS uev.fleet_inventory (
 district text NOT NULL, vehicle_class text NOT NULL,
 total_vehicles bigint NOT NULL CHECK (total_vehicles >= 0),
 electric_vehicles bigint NOT NULL CHECK (electric_vehicles >= 0 AND electric_vehicles <= total_vehicles),
 km_per_day double precision NOT NULL CHECK (km_per_day >= 0),
 kwh_per_km double precision NOT NULL CHECK (kwh_per_km >= 0),
 growth_rate double precision NOT NULL,
 source_id text NOT NULL REFERENCES uev.sources(id),
 PRIMARY KEY (district,vehicle_class,source_id)
);
-- Migration + spatial overlay procedures are subsequent tasks, not implemented here.
