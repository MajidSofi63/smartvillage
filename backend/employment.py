import psycopg2
from datetime import datetime
from database import get_connection


def save_worker_profile(worker_id, name, email, phone, location, skills, bio):
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
    conn = get_connection()
    conn.execute("""
        UPDATE worker_profiles SET name = ?, phone = ?, location = ?, skills = ?, bio = ?
        WHERE id = ?
    """, (name, phone, location, skills.lower(), bio, worker_id))
    conn.commit()
    conn.close()


def get_worker_profile(worker_id):
    conn = get_connection()
    row = conn.execute("SELECT * FROM worker_profiles WHERE id = ?", (worker_id,)).fetchone()
    conn.close()
    if row is None:
        return None
    return {"name": row["name"], "email": row["email"], "phone": row["phone"],
            "location": row["location"], "skills": row["skills"], "bio": row["bio"]}


def delete_worker_profile(worker_id):
    conn = get_connection()
    conn.execute("DELETE FROM worker_profiles WHERE id = ?", (worker_id,))
    conn.commit()
    conn.close()


def list_public_feed():
    conn = get_connection()
    rows = conn.execute("SELECT * FROM worker_profiles ORDER BY created_at DESC").fetchall()
    conn.close()
    return [{"id": r["id"], "name": r["name"], "phone": r["phone"], "location": r["location"],
             "skills": r["skills"], "bio": r["bio"]} for r in rows]


def get_public_stats():
    conn = get_connection()
    worker_count = conn.execute("SELECT COUNT(*) FROM worker_profiles").fetchone()["count"]
    conn.close()
    return {"worker_count": worker_count}


def list_all_workers():
    conn = get_connection()
    rows = conn.execute("SELECT * FROM worker_profiles ORDER BY name").fetchall()
    conn.close()
    return [{"id": r["id"], "name": r["name"], "email": r["email"], "phone": r["phone"],
             "location": r["location"], "skills": r["skills"], "bio": r["bio"]} for r in rows]
