# database.py
# Real, permanent Postgres database (hosted free on Neon) for worker profiles and
# usage analytics. This matters because Render's free web services wipe their local
# filesystem on every restart/redeploy - a SQLite file living there would silently
# lose everything. Postgres lives on Neon's own servers, completely independent of
# wherever the backend itself happens to be hosted.
#
# NOTE: login/accounts are handled separately by Supabase (see auth.py). This file
# only stores the PROFILE data (name, phone, location, skills, bio) that a logged-in
# worker fills in, plus lightweight usage counts for the admin panel.
#
# LOCAL DEVELOPMENT: create a free project at https://neon.tech, copy its connection
# string into a local .env file as DATABASE_URL=... (copy .env.example to .env and
# fill it in) - everything below then works identically locally and once deployed.

import os
from pathlib import Path

import psycopg2
import psycopg2.extras
from dotenv import load_dotenv

# Always look for backend/.env first, then fall back to the working directory.
BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")
load_dotenv()

DATABASE_URL = os.environ.get("DATABASE_URL")


class _ConnectionWrapper:
    """
    A thin wrapper so the rest of the codebase (auth.py, employment.py, analytics.py)
    can keep using the same simple `conn.execute(query, params).fetchone()` style
    that worked with SQLite, without every single query call site needing to change.
    """

    def __init__(self, pg_connection):
        self._conn = pg_connection

    def execute(self, query, params=()):
        # SQLite uses "?" placeholders, Postgres uses "%s" - translate automatically
        # so the query strings elsewhere in the codebase don't need to change.
        cursor = self._conn.cursor()
        cursor.execute(query.replace("?", "%s"), params)
        return cursor

    def commit(self):
        self._conn.commit()

    def close(self):
        self._conn.close()


def get_connection():
    """Opens a connection to Postgres, with dict-like rows (row['name'] works, like sqlite3.Row did)."""
    pg_connection = psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)
    return _ConnectionWrapper(pg_connection)


def init_db():
    """Creates every table if it doesn't already exist. Safe to run on every startup."""
    conn = get_connection()

    conn.execute("""
        CREATE TABLE IF NOT EXISTS worker_profiles (
            id UUID PRIMARY KEY,
            name TEXT NOT NULL,
            email TEXT NOT NULL,
            phone TEXT NOT NULL,
            location TEXT NOT NULL,
            skills TEXT NOT NULL,
            bio TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL DEFAULT ''
        )
    """)

    # Safety net: adds any columns that didn't exist yet on a table created by an
    # earlier version of this project, instead of requiring manual database edits.
    conn.execute("ALTER TABLE worker_profiles ADD COLUMN IF NOT EXISTS email TEXT NOT NULL DEFAULT ''")
    conn.execute("ALTER TABLE worker_profiles ADD COLUMN IF NOT EXISTS bio TEXT NOT NULL DEFAULT ''")
    conn.execute("ALTER TABLE worker_profiles ADD COLUMN IF NOT EXISTS created_at TEXT NOT NULL DEFAULT ''")

    # Usage analytics - lets the admin panel show real platform activity (how many
    # times each module has actually been used), not just who registered.
    conn.execute("""
        CREATE TABLE IF NOT EXISTS usage_events (
            id SERIAL PRIMARY KEY,
            event_type TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)

    # Local worker accounts table (fallback when Supabase auth is not configured)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS worker_accounts (
            id UUID PRIMARY KEY,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            name TEXT NOT NULL DEFAULT '',
            location TEXT NOT NULL DEFAULT '',
            skills TEXT NOT NULL DEFAULT '',
            role TEXT NOT NULL DEFAULT 'worker',
            created_at TEXT NOT NULL DEFAULT ''
        )
    """)

    conn.commit()
    conn.close()
