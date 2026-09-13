# database.py
# Real, permanent Postgres database (hosted free on Neon) for jobs, applications, and
# worker profile info. This matters because Render's free web services wipe their
# local filesystem on every restart/redeploy - a SQLite file living there would
# silently lose every job posting. Postgres lives on Neon's own servers, completely
# independent of wherever the backend itself happens to be hosted.
#
# NOTE: login/accounts (workers and employers) are handled separately by Supabase -
# see auth.py. This file only stores the data those logged-in users create.
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
    """Creates every table if it doesn't already exist. Safe to run on every startup."""
    conn = get_connection()

    # A local copy of a few worker profile fields (name, phone, location, skills).
    # Supabase's account metadata is the source of truth for these at signup time,
    # but keeping a plain Postgres copy here means the employer-facing "view
    # applicants" query can do a normal SQL JOIN, instead of reaching into
    # Supabase's own internal auth schema from here.
    conn.execute("""
        CREATE TABLE IF NOT EXISTS worker_profiles (
            id UUID PRIMARY KEY,
            name TEXT NOT NULL,
            email TEXT NOT NULL,
            phone TEXT NOT NULL,
            location TEXT NOT NULL,
            skills TEXT NOT NULL
        )
    """)

    # Safety net: if this table already existed from before "email" was added
    # (e.g. your first deployment), this adds the missing column automatically
    # instead of requiring you to manually edit the live database.
    conn.execute("ALTER TABLE worker_profiles ADD COLUMN IF NOT EXISTS email TEXT NOT NULL DEFAULT ''")

    # A local copy of employer profile fields too, for the same reason - lets the
    # admin panel list every employer with a plain SQL query instead of needing
    # Supabase's privileged admin API (which needs the service_role key - a much
    # more sensitive credential we'd rather not need on this server at all).
    conn.execute("""
        CREATE TABLE IF NOT EXISTS employer_profiles (
            id UUID PRIMARY KEY,
            name TEXT NOT NULL,
            email TEXT NOT NULL
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS jobs (
            id SERIAL PRIMARY KEY,
            employer_id UUID NOT NULL,
            title TEXT NOT NULL,
            skills TEXT NOT NULL,
            location TEXT NOT NULL,
            job_type TEXT NOT NULL,
            contact TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS applications (
            id SERIAL PRIMARY KEY,
            job_id INTEGER NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
            worker_id UUID NOT NULL REFERENCES worker_profiles(id),
            status TEXT NOT NULL DEFAULT 'Applied',
            applied_at TEXT NOT NULL,
            UNIQUE(job_id, worker_id)
        )
    """)

    conn.commit()
    conn.close()
