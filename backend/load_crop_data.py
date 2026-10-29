#!/usr/bin/env python3
# load_crop_data.py
# One-time loader for the district-level crop recommendation data.
#
# Usage (from the backend folder, with the same DATABASE_URL as the platform):
#     python load_crop_data.py
#     python load_crop_data.py --keep     # upsert instead of a full refresh
#     python load_crop_data.py --csv path\to\crop_data_with_weather.csv
#
# The default CSV is data/crop_data_with_weather.csv in the project root.
# The script creates the two tables if needed and bulk-loads:
#   districts  (666 state-district pairs)
#   crop_stats (~153,000 district-year-season-crop rows)
#
# This is safe to re-run. A full refresh truncates ONLY these two tables and
# does not touch worker_profiles or usage_events.

import argparse
import os
import sys
from pathlib import Path

import pandas as pd
import psycopg2
from dotenv import load_dotenv
from psycopg2.extras import execute_values

BACKEND_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BACKEND_DIR.parent
DEFAULT_CSV = PROJECT_ROOT / "data" / "crop_data_with_weather.csv"

# Support both backend/.env (the documented location) and a root .env.
load_dotenv(BACKEND_DIR / ".env")
load_dotenv(PROJECT_ROOT / ".env")

CREATE_TABLES_SQL = [
    """
    CREATE TABLE IF NOT EXISTS districts (
        id SERIAL PRIMARY KEY,
        state VARCHAR(100) NOT NULL,
        district VARCHAR(100) NOT NULL,
        lat FLOAT NOT NULL,
        lon FLOAT NOT NULL,
        coord_source VARCHAR(20),
        UNIQUE(state, district)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS crop_stats (
        id SERIAL PRIMARY KEY,
        district_id INTEGER REFERENCES districts(id) ON DELETE CASCADE,
        year INTEGER NOT NULL,
        season VARCHAR(50) NOT NULL,
        crop VARCHAR(100) NOT NULL,
        area_ha FLOAT NOT NULL,
        production_t FLOAT NOT NULL,
        yield_t_ha FLOAT NOT NULL,
        temp_mean FLOAT NOT NULL,
        rain_total FLOAT NOT NULL,
        UNIQUE(district_id, year, season, crop)
    )
    """,
    "ALTER TABLE districts ADD COLUMN IF NOT EXISTS coord_source VARCHAR(20)",
    "CREATE INDEX IF NOT EXISTS idx_crop_stats_district_season "
    "ON crop_stats(district_id, season)",
    "CREATE INDEX IF NOT EXISTS idx_crop_stats_district_crop_season "
    "ON crop_stats(district_id, crop, season)",
    "CREATE INDEX IF NOT EXISTS idx_crop_stats_district_year "
    "ON crop_stats(district_id, year)",
]


def load(csv_path, keep=False):
    """Create the tables and load the CSV into PostgreSQL."""
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        print("[ERROR] DATABASE_URL is not set.")
        print("[ACTION] Copy backend/.env.example to backend/.env and fill it in.")
        sys.exit(1)

    if not csv_path.exists():
        print(f"[ERROR] Missing {csv_path}")
        print("[ACTION] Copy crop_data_with_weather.csv into the data folder.")
        sys.exit(1)

    print("=" * 72)
    print("CROP RECOMMENDATION DATA LOADER")
    print("=" * 72)
    print(f"[INFO] Reading {csv_path}")
    df = pd.read_csv(csv_path)
    print(f"[INFO] Loaded {len(df):,} rows")

    required = {
        "state", "district", "year", "season", "crop", "area_ha",
        "production_t", "yield_t_ha", "temp_mean", "rain_total",
        "latitude", "longitude", "coord_source",
    }
    missing = required - set(df.columns)
    if missing:
        print(f"[ERROR] CSV is missing columns: {', '.join(sorted(missing))}")
        sys.exit(1)

    # Refuse synthetic constant weather.
    if df["temp_mean"].nunique() <= 1 or df["rain_total"].nunique() <= 1:
        print("[ERROR] Weather columns are constant; refusing to load fake data.")
        sys.exit(1)

    # The Total season is a Kharif + Rabi roll-up and must not be recommended.
    if (df["season"] == "Total").any():
        removed = int((df["season"] == "Total").sum())
        df = df[df["season"] != "Total"].copy()
        print(f"[INFO] Dropped {removed} 'Total' rows")

    print("[INFO] Connecting to PostgreSQL")
    try:
        conn = psycopg2.connect(database_url)
        cur = conn.cursor()
    except Exception as exc:
        print(f"[ERROR] Could not connect: {exc}")
        sys.exit(1)

    try:
        print("[INFO] Creating/verifying tables and indexes")
        for statement in CREATE_TABLES_SQL:
            cur.execute(statement)
        conn.commit()

        if not keep:
            print("[INFO] Full refresh: truncating districts and crop_stats")
            cur.execute(
                "TRUNCATE TABLE crop_stats, districts RESTART IDENTITY CASCADE;"
            )
            conn.commit()

        districts_df = (
            df[["state", "district", "latitude", "longitude", "coord_source"]]
            .drop_duplicates(subset=["state", "district"])
            .reset_index(drop=True)
        )
        print(f"[INFO] Inserting {len(districts_df):,} districts")
        execute_values(
            cur,
            """
            INSERT INTO districts (state, district, lat, lon, coord_source)
            VALUES %s
            ON CONFLICT (state, district) DO UPDATE
            SET lat = EXCLUDED.lat,
                lon = EXCLUDED.lon,
                coord_source = EXCLUDED.coord_source
            """,
            [
                (
                    row["state"],
                    row["district"],
                    float(row["latitude"]),
                    float(row["longitude"]),
                    row["coord_source"],
                )
                for _, row in districts_df.iterrows()
            ],
            page_size=500,
        )
        conn.commit()

        cur.execute("SELECT id, state, district FROM districts")
        district_map = {
            (state, district): district_id
            for district_id, state, district in cur.fetchall()
        }

        crop_rows = []
        for _, row in df.iterrows():
            district_id = district_map.get((row["state"], row["district"]))
            if district_id is None:
                continue
            crop_rows.append(
                (
                    int(district_id),
                    int(row["year"]),
                    row["season"],
                    row["crop"],
                    float(row["area_ha"]),
                    float(row["production_t"]),
                    float(row["yield_t_ha"]),
                    float(row["temp_mean"]),
                    float(row["rain_total"]),
                )
            )

        print(f"[INFO] Inserting {len(crop_rows):,} crop statistics rows")
        batch_size = 5000
        inserted = 0
        for start in range(0, len(crop_rows), batch_size):
            batch = crop_rows[start:start + batch_size]
            execute_values(
                cur,
                """
                INSERT INTO crop_stats
                    (district_id, year, season, crop, area_ha, production_t,
                     yield_t_ha, temp_mean, rain_total)
                VALUES %s
                ON CONFLICT (district_id, year, season, crop) DO UPDATE
                SET area_ha = EXCLUDED.area_ha,
                    production_t = EXCLUDED.production_t,
                    yield_t_ha = EXCLUDED.yield_t_ha,
                    temp_mean = EXCLUDED.temp_mean,
                    rain_total = EXCLUDED.rain_total
                """,
                batch,
                page_size=1000,
            )
            conn.commit()
            inserted += len(batch)
            print(f"  Progress: {inserted:,}/{len(crop_rows):,}")

        cur.execute("ANALYZE districts")
        cur.execute("ANALYZE crop_stats")
        conn.commit()

        print("\n" + "=" * 72)
        print("DATABASE STATISTICS")
        print("=" * 72)
        cur.execute("SELECT COUNT(*) FROM districts")
        print(f"[INFO] districts: {cur.fetchone()[0]:,} rows")
        cur.execute("SELECT COUNT(*) FROM crop_stats")
        print(f"[INFO] crop_stats: {cur.fetchone()[0]:,} rows")
        cur.execute("SELECT MIN(year), MAX(year) FROM crop_stats")
        min_year, max_year = cur.fetchone()
        print(f"[INFO] Years: {min_year} to {max_year}")
        cur.execute("SELECT COUNT(DISTINCT season) FROM crop_stats")
        print(f"[INFO] Seasons: {cur.fetchone()[0]}")
        cur.execute("SELECT COUNT(DISTINCT crop) FROM crop_stats")
        print(f"[INFO] Crops: {cur.fetchone()[0]}")
        print("=" * 72)
        print("[INFO] Done. Start the server and open the Crop Recommendation tab.")
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Load district crop data into PostgreSQL"
    )
    parser.add_argument(
        "--keep",
        action="store_true",
        help="Upsert instead of truncating the two crop tables",
    )
    parser.add_argument(
        "--csv",
        type=Path,
        default=DEFAULT_CSV,
        help=f"CSV to load (default: {DEFAULT_CSV})",
    )
    args = parser.parse_args()
    load(args.csv, keep=args.keep)
