PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS sources (
 id TEXT PRIMARY KEY,
 title TEXT NOT NULL,
 reference_year INTEGER NOT NULL,
 license TEXT NOT NULL,
 confidence TEXT NOT NULL CHECK (confidence IN ('verified','estimated','projected','synthetic')),
 is_demo INTEGER NOT NULL CHECK (is_demo IN (0,1))
);
CREATE TABLE IF NOT EXISTS geo_features (
 id TEXT PRIMARY KEY,
 layer TEXT NOT NULL CHECK (layer IN ('charging','candidates','grid','mobility')),
 name TEXT NOT NULL,
 district TEXT NOT NULL,
 lon REAL NOT NULL CHECK (lon BETWEEN -180 AND 180),
 lat REAL NOT NULL CHECK (lat BETWEEN -90 AND 90),
 properties_json TEXT NOT NULL,
 source_id TEXT NOT NULL REFERENCES sources(id)
);
CREATE INDEX IF NOT EXISTS idx_geo_layer_district ON geo_features(layer,district);
CREATE TABLE IF NOT EXISTS fleets (
 district TEXT NOT NULL,
 category TEXT NOT NULL,
 total_vehicles INTEGER NOT NULL CHECK (total_vehicles >= 0),
 electric_vehicles INTEGER NOT NULL CHECK (electric_vehicles >= 0 AND electric_vehicles <= total_vehicles),
 km_per_day REAL NOT NULL CHECK (km_per_day >= 0),
 kwh_per_km REAL NOT NULL CHECK (kwh_per_km >= 0),
 growth_rate REAL NOT NULL CHECK (growth_rate >= -1),
 source_id TEXT NOT NULL REFERENCES sources(id),
 PRIMARY KEY (district, category, source_id)
);
