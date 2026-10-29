# crop_db.py
# Database access for the district-level crop recommendation feature.
#
# Two tables are used, separate from the platform's worker_profiles and
# usage_events tables:
#   districts  - one row per Indian state-district pair, with coordinates
#   crop_stats - one row per district, year, season, and crop
#
# They are created automatically at startup and filled by
# backend/load_crop_data.py.

from database import get_connection


CREATE_DISTRICTS_SQL = """
    CREATE TABLE IF NOT EXISTS districts (
        id SERIAL PRIMARY KEY,
        state VARCHAR(100) NOT NULL,
        district VARCHAR(100) NOT NULL,
        lat FLOAT NOT NULL,
        lon FLOAT NOT NULL,
        coord_source VARCHAR(20),
        UNIQUE(state, district)
    )
"""

CREATE_CROP_STATS_SQL = """
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
"""

INDEX_SQL = [
    "CREATE INDEX IF NOT EXISTS idx_crop_stats_district_season "
    "ON crop_stats(district_id, season)",
    "CREATE INDEX IF NOT EXISTS idx_crop_stats_district_crop_season "
    "ON crop_stats(district_id, crop, season)",
    "CREATE INDEX IF NOT EXISTS idx_crop_stats_district_year "
    "ON crop_stats(district_id, year)",
]


def init_crop_tables():
    """Create the two crop tables and their indexes if they do not exist."""
    conn = get_connection()
    try:
        conn.execute(CREATE_DISTRICTS_SQL)
        conn.execute(CREATE_CROP_STATS_SQL)
        for statement in INDEX_SQL:
            conn.execute(statement)
        conn.commit()
    finally:
        conn.close()


def search_districts(query, limit=15):
    """Return up to `limit` districts matching the search text."""
    conn = get_connection()
    try:
        if query:
            cursor = conn.execute(
                """
                SELECT id, state, district, lat, lon
                FROM districts
                WHERE district ILIKE %s OR state ILIKE %s
                ORDER BY district, state
                LIMIT %s
                """,
                (f"%{query}%", f"%{query}%", limit),
            )
        else:
            cursor = conn.execute(
                """
                SELECT id, state, district, lat, lon
                FROM districts
                ORDER BY district, state
                LIMIT %s
                """,
                (limit,),
            )
        return [dict(row) for row in cursor.fetchall()]
    finally:
        conn.close()


def get_seasons():
    """Return the planting seasons present in the dataset."""
    conn = get_connection()
    try:
        cursor = conn.execute(
            "SELECT DISTINCT season FROM crop_stats "
            "WHERE season <> 'Total' ORDER BY season"
        )
        return [row["season"] for row in cursor.fetchall()]
    finally:
        conn.close()


def get_district(district_id):
    """Return one district plus the latest year present in crop_stats."""
    conn = get_connection()
    try:
        cursor = conn.execute(
            """
            SELECT d.id, d.state, d.district, d.lat, d.lon,
                   (SELECT MAX(year) FROM crop_stats) AS max_year
            FROM districts d
            WHERE d.id = %s
            """,
            (district_id,),
        )
        row = cursor.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def get_history(district_id, season):
    """Return every historical crop row for one district and season."""
    conn = get_connection()
    try:
        cursor = conn.execute(
            """
            SELECT crop, year, yield_t_ha, temp_mean, rain_total
            FROM crop_stats
            WHERE district_id = %s AND season = %s
            ORDER BY crop, year
            """,
            (district_id, season),
        )
        return [dict(row) for row in cursor.fetchall()]
    finally:
        conn.close()
