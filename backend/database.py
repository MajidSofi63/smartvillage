# database.py
# Real, permanent Postgres database (hosted free on Neon) for worker profiles - this
# is the whole "employee database" the admin panel gives you visibility into.
# Postgres lives on Neon's own servers, completely independent of wherever the
# backend itself happens to be hosted, so this data survives every Render redeploy.
#
# NOTE: login/accounts are handled separately by Supabase (see auth.py). This file
# only stores the PROFILE data (name, phone, location, skills, bio) that a logged-in
# worker fills in - which is also exactly what gets shown in the public feed.
#
# LOCAL DEVELOPMENT: create a free project at https://neon.tech, copy its connection
# string into a local .env file as DATABASE_URL=... (copy .env.example to .env and
# fill it in) - everything below then works identically locally and once deployed.

import os
import psycopg2
import psycopg2.extras
from dotenv import load_dotenv

load_dotenv()  # reads a local .env file if one exists (ignored by git - see .gitignore)

DATABASE_URL = os.environ.get("DATABASE_URL")


class _ConnectionWrapper:
    """
    A thin wrapper so the rest of the codebase (auth.py, employment.py) can keep using
    the same simple `conn.execute(query, params).fetchone()` style that worked with
    SQLite, without every single query call site needing to change for Postgres.
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
    """Creates the worker_profiles table if it doesn't already exist. Safe to run on every startup."""
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

    conn.commit()
    conn.close()

    # NOTE: if you had employer_profiles, jobs, or applications tables from an
    # earlier version of this project, they're no longer used and are safe to drop
    # manually in Neon's SQL editor if you want a clean database - not required
    # for anything to work, they're just unused leftovers otherwise.