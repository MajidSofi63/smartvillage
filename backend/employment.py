# employment.py
# Real two-sided job board. Login/accounts are handled by Supabase (see auth.py) -
# this file only handles what logged-in users DO: post jobs, apply, review
# applicants, and now also delete a job posting or withdraw an application.
# All of this data persists in Postgres on Neon (see database.py).

import psycopg2
from datetime import datetime
from database import get_connection


# ---------- Worker profile (mirrors a few Supabase account fields for easy SQL joins) ----------

def save_worker_profile(worker_id, name, email, phone, location, skills):
    """
    Called right after a successful Supabase signup to keep a local copy of the
    profile fields needed for "view applicants" queries and the admin panel.
    Supabase's own account metadata remains the source of truth for login - this
    is just a working copy. ON CONFLICT means calling this again just refreshes it.
    """
    conn = get_connection()
    conn.execute("""
        INSERT INTO worker_profiles (id, name, email, phone, location, skills) VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name, email = EXCLUDED.email, phone = EXCLUDED.phone,
                                        location = EXCLUDED.location, skills = EXCLUDED.skills
    """, (worker_id, name, email, phone, location, skills.lower()))
    conn.commit()
    conn.close()


def save_employer_profile(employer_id, name, email):
    """Same idea as save_worker_profile, but for employers - lets the admin panel list them."""
    conn = get_connection()
    conn.execute("""
        INSERT INTO employer_profiles (id, name, email) VALUES (?, ?, ?)
        ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name, email = EXCLUDED.email
    """, (employer_id, name, email))
    conn.commit()
    conn.close()


def get_worker_skills(worker_id):
    """Fetches a worker's saved skills, used to sort the job list by relevance for them."""
    conn = get_connection()
    row = conn.execute("SELECT skills FROM worker_profiles WHERE id = ?", (worker_id,)).fetchone()
    conn.close()
    return row["skills"] if row else ""


# ---------- Jobs ----------

def post_job(employer_id, title, skills, location, job_type, contact):
    conn = get_connection()
    conn.execute(
        "INSERT INTO jobs (employer_id, title, skills, location, job_type, contact, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (employer_id, title, skills.lower(), location, job_type, contact, datetime.utcnow().isoformat())
    )
    conn.commit()
    conn.close()


def delete_job(employer_id, job_id):
    """Removes a job posting (and its applications, via ON DELETE CASCADE) - only if it's this employer's own job."""
    conn = get_connection()
    owns_it = conn.execute("SELECT id FROM jobs WHERE id = ? AND employer_id = ?", (job_id, employer_id)).fetchone()
    if owns_it is None:
        conn.close()
        return False
    conn.execute("DELETE FROM jobs WHERE id = ?", (job_id,))
    conn.commit()
    conn.close()
    return True


def _skill_overlap_score(required_skills_text, candidate_skills_text):
    required_words = [w.strip() for w in required_skills_text.lower().split(",") if w.strip()]
    return sum(1 for w in required_words if w in candidate_skills_text)


def list_jobs(worker_skills=None):
    """
    Returns every posted job. If worker_skills is given, jobs matching those skills
    are sorted to the top - this is a SORT ORDER, not a filter, so a worker can still
    see and apply to any job, the same way Indeed/Naukri rank listings for you but
    don't hide the rest.
    """
    conn = get_connection()
    jobs = conn.execute("SELECT * FROM jobs ORDER BY created_at DESC").fetchall()
    conn.close()

    job_list = []
    for job in jobs:
        score = _skill_overlap_score(worker_skills, job["skills"]) if worker_skills else 0
        job_list.append({
            "id": job["id"], "title": job["title"], "skills": job["skills"],
            "location": job["location"], "type": job["job_type"],
            "created_at": job["created_at"], "match_score": score
        })

    if worker_skills:
        job_list.sort(key=lambda j: j["match_score"], reverse=True)
    return job_list


def list_employer_jobs(employer_id):
    """Jobs posted by this employer, with how many people have applied to each."""
    conn = get_connection()
    jobs = conn.execute("SELECT * FROM jobs WHERE employer_id = ? ORDER BY created_at DESC", (employer_id,)).fetchall()

    result = []
    for job in jobs:
        count = conn.execute("SELECT COUNT(*) FROM applications WHERE job_id = ?", (job["id"],)).fetchone()["count"]
        result.append({
            "id": job["id"], "title": job["title"], "skills": job["skills"],
            "location": job["location"], "type": job["job_type"],
            "created_at": job["created_at"], "applicant_count": count
        })
    conn.close()
    return result


# ---------- Applications ----------

def apply_to_job(worker_id, job_id):
    """A worker applies to a job. Returns False if they've already applied to this one."""
    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO applications (job_id, worker_id, applied_at) VALUES (?, ?, ?)",
            (job_id, worker_id, datetime.utcnow().isoformat())
        )
        conn.commit()
    except psycopg2.IntegrityError:
        conn.close()
        return False  # the UNIQUE(job_id, worker_id) constraint caught a duplicate application
    conn.close()
    return True


def withdraw_application(worker_id, application_id):
    """Lets a worker withdraw their own application - only if it actually belongs to them."""
    conn = get_connection()
    owns_it = conn.execute(
        "SELECT id FROM applications WHERE id = ? AND worker_id = ?", (application_id, worker_id)
    ).fetchone()
    if owns_it is None:
        conn.close()
        return False
    conn.execute("DELETE FROM applications WHERE id = ?", (application_id,))
    conn.commit()
    conn.close()
    return True


def list_applicants(employer_id, job_id):
    """
    Applicants for a job - returns None if the job doesn't actually belong to this
    employer, so one employer can never see another employer's applicants.
    """
    conn = get_connection()
    job = conn.execute("SELECT id FROM jobs WHERE id = ? AND employer_id = ?", (job_id, employer_id)).fetchone()
    if job is None:
        conn.close()
        return None

    rows = conn.execute("""
        SELECT applications.id AS application_id, applications.status,
               worker_profiles.name, worker_profiles.phone, worker_profiles.location
        FROM applications
        JOIN worker_profiles ON applications.worker_id = worker_profiles.id
        WHERE applications.job_id = ?
        ORDER BY applications.applied_at DESC
    """, (job_id,)).fetchall()
    conn.close()

    return [{"application_id": r["application_id"], "name": r["name"], "phone": r["phone"],
             "location": r["location"], "status": r["status"]} for r in rows]


def update_application_status(employer_id, application_id, new_status):
    """Lets an employer mark an applicant as Contacted/Hired - only for their own job postings."""
    conn = get_connection()
    owns_it = conn.execute("""
        SELECT applications.id FROM applications
        JOIN jobs ON applications.job_id = jobs.id
        WHERE applications.id = ? AND jobs.employer_id = ?
    """, (application_id, employer_id)).fetchone()

    if owns_it is None:
        conn.close()
        return False

    conn.execute("UPDATE applications SET status = ? WHERE id = ?", (new_status, application_id))
    conn.commit()
    conn.close()
    return True


def list_worker_applications(worker_id):
    """A worker's own application history, with the current status of each - includes
    the application id so the frontend can offer a 'withdraw' button on each one."""
    conn = get_connection()
    rows = conn.execute("""
        SELECT applications.id AS application_id, jobs.title, jobs.location, jobs.job_type,
               applications.status, applications.applied_at
        FROM applications
        JOIN jobs ON applications.job_id = jobs.id
        WHERE applications.worker_id = ?
        ORDER BY applications.applied_at DESC
    """, (worker_id,)).fetchall()
    conn.close()
    return [{"application_id": r["application_id"], "title": r["title"], "location": r["location"],
             "type": r["job_type"], "status": r["status"], "applied_at": r["applied_at"]} for r in rows]


# ---------- Admin: full visibility into everyone on the platform ----------
# These have no "owner" restriction (unlike everything above) - they're only
# reachable through the /admin/* routes in main.py, which check the admin
# password before any of these ever get called.

def list_all_workers():
    conn = get_connection()
    rows = conn.execute("SELECT * FROM worker_profiles ORDER BY name").fetchall()
    conn.close()
    return [{"id": r["id"], "name": r["name"], "email": r["email"], "phone": r["phone"],
             "location": r["location"], "skills": r["skills"]} for r in rows]


def list_all_employers():
    conn = get_connection()
    rows = conn.execute("SELECT * FROM employer_profiles ORDER BY name").fetchall()
    conn.close()
    return [{"id": r["id"], "name": r["name"], "email": r["email"]} for r in rows]


def list_all_jobs():
    """Every job on the platform, with the posting employer's name/email attached."""
    conn = get_connection()
    rows = conn.execute("""
        SELECT jobs.*, employer_profiles.name AS employer_name, employer_profiles.email AS employer_email,
               (SELECT COUNT(*) FROM applications WHERE applications.job_id = jobs.id) AS applicant_count
        FROM jobs
        LEFT JOIN employer_profiles ON jobs.employer_id = employer_profiles.id
        ORDER BY jobs.created_at DESC
    """).fetchall()
    conn.close()
    return [{"id": r["id"], "title": r["title"], "skills": r["skills"], "location": r["location"],
             "type": r["job_type"], "contact": r["contact"], "created_at": r["created_at"],
             "employer_name": r["employer_name"] or "(unknown)", "employer_email": r["employer_email"] or "",
             "applicant_count": r["applicant_count"]} for r in rows]


def list_all_applications():
    """Every application on the platform, with worker and job details attached."""
    conn = get_connection()
    rows = conn.execute("""
        SELECT applications.id AS application_id, applications.status, applications.applied_at,
               worker_profiles.name AS worker_name, worker_profiles.phone AS worker_phone,
               jobs.title AS job_title
        FROM applications
        JOIN worker_profiles ON applications.worker_id = worker_profiles.id
        JOIN jobs ON applications.job_id = jobs.id
        ORDER BY applications.applied_at DESC
    """).fetchall()
    conn.close()
    return [{"application_id": r["application_id"], "status": r["status"], "applied_at": r["applied_at"],
             "worker_name": r["worker_name"], "worker_phone": r["worker_phone"], "job_title": r["job_title"]} for r in rows]


def admin_delete_worker(worker_id):
    """Removes a worker's local profile/listing. Does NOT delete their Supabase login
    account - that would need Supabase's own dashboard (Authentication -> Users)."""
    conn = get_connection()
    conn.execute("DELETE FROM worker_profiles WHERE id = ?", (worker_id,))
    conn.commit()
    conn.close()


def admin_delete_employer(employer_id):
    """Same as above, for employers. Their posted jobs are left in place but will
    show '(unknown)' as the employer name once the profile is gone."""
    conn = get_connection()
    conn.execute("DELETE FROM employer_profiles WHERE id = ?", (employer_id,))
    conn.commit()
    conn.close()


def admin_delete_job(job_id):
    """Admin version of delete_job - no ownership check, since the admin can moderate anything."""
    conn = get_connection()
    conn.execute("DELETE FROM jobs WHERE id = ?", (job_id,))
    conn.commit()
    conn.close()


def get_public_stats():
    """
    Simple aggregate counts (no names, no contact info - safe to show publicly)
    for the Employment tab's landing screen, so it reads as an active platform
    instead of an empty shell before anyone's logged in.
    """
    conn = get_connection()
    worker_count = conn.execute("SELECT COUNT(*) FROM worker_profiles").fetchone()["count"]
    employer_count = conn.execute("SELECT COUNT(*) FROM employer_profiles").fetchone()["count"]
    job_count = conn.execute("SELECT COUNT(*) FROM jobs").fetchone()["count"]
    conn.close()
    return {"worker_count": worker_count, "employer_count": employer_count, "job_count": job_count}
