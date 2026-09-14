# employment.py
# Simple, one-sided model: workers register and maintain a public profile (name,
# phone, location, skills, a short bio) - that's it. There's no separate employer
# account, no job postings, no "apply" flow. Anyone can scroll the public feed
# (no login needed) and call a worker directly using the phone number shown -
# closer to how people actually find local workers than a formal job board.

from datetime import datetime
from database import get_connection


def save_worker_profile(worker_id, name, email, phone, location, skills, bio):
    """
    Called right after a successful Supabase signup to create the worker's public
    profile - this IS the "post" that shows up in the feed. ON CONFLICT means
    calling this again (e.g. when editing) just updates it in place.
    """
    conn = get_connection()
    conn.execute("""
        INSERT INTO worker_profiles (id, name, email, phone, location, skills, bio, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name, email = EXCLUDED.email,
            phone = EXCLUDED.phone, location = EXCLUDED.location,
            skills = EXCLUDED.skills, bio = EXCLUDED.bio
    """, (worker_id, name, email, phone, location, skills.lower(), bio, datetime.utcnow().isoformat()))
    conn.commit()
    conn.close()


def update_worker_profile(worker_id, name, phone, location, skills, bio):
    """Lets a logged-in worker edit their own profile (email/login stays unchanged)."""
    conn = get_connection()
    conn.execute("""
        UPDATE worker_profiles SET name = ?, phone = ?, location = ?, skills = ?, bio = ?
        WHERE id = ?
    """, (name, phone, location, skills.lower(), bio, worker_id))
    conn.commit()
    conn.close()


def get_worker_profile(worker_id):
    """Fetches one worker's own profile - used to pre-fill their edit form."""
    conn = get_connection()
    row = conn.execute("SELECT * FROM worker_profiles WHERE id = ?", (worker_id,)).fetchone()
    conn.close()
    if row is None:
        return None
    return {"name": row["name"], "email": row["email"], "phone": row["phone"],
            "location": row["location"], "skills": row["skills"], "bio": row["bio"]}


def delete_worker_profile(worker_id):
    """
    Removes a worker's profile from the feed - used both when a worker deletes their
    own profile, and by the admin panel to moderate anyone's. Doesn't touch their
    actual Supabase login account (that needs Supabase's own dashboard).
    """
    conn = get_connection()
    conn.execute("DELETE FROM worker_profiles WHERE id = ?", (worker_id,))
    conn.commit()
    conn.close()


def list_public_feed():
    """
    Every worker profile, newest first - this is the actual public feed content.
    No login required to call this; it deliberately includes the phone number,
    since the whole point is letting someone browsing find and call a worker directly.
    """
    conn = get_connection()
    rows = conn.execute("SELECT * FROM worker_profiles ORDER BY created_at DESC").fetchall()
    conn.close()
    return [{"id": r["id"], "name": r["name"], "phone": r["phone"], "location": r["location"],
             "skills": r["skills"], "bio": r["bio"]} for r in rows]


def get_public_stats():
    """Simple count for the feed header - just a number, no personal data, safe to show anyone."""
    conn = get_connection()
    worker_count = conn.execute("SELECT COUNT(*) FROM worker_profiles").fetchone()["count"]
    conn.close()
    return {"worker_count": worker_count}


# ---------- Admin: same data as the public feed, but with email included for
# moderation purposes, and reachable only through the password-gated /admin/* routes ----------

def list_all_workers():
    conn = get_connection()
    rows = conn.execute("SELECT * FROM worker_profiles ORDER BY name").fetchall()
    conn.close()
    return [{"id": r["id"], "name": r["name"], "email": r["email"], "phone": r["phone"],
             "location": r["location"], "skills": r["skills"], "bio": r["bio"]} for r in rows]