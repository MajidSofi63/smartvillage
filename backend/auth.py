# auth.py
# Uses Supabase Auth when configured, and automatically falls back to secure local
# PostgreSQL authentication (PBKDF2-SHA256 password hashing + HMAC tokens) so worker
# registration and login work 100% out of the box with zero external configuration.

import hashlib
import hmac
import os
import time
import uuid
from datetime import datetime, timezone

import requests
from config import SUPABASE_URL, SUPABASE_ANON_KEY, SUPABASE_SERVICE_ROLE_KEY
from database import get_connection

AUTH_SECRET = os.environ.get("AUTH_SECRET", "smart-village-secret-key-2026")
AUTH_URL = f"{SUPABASE_URL}/auth/v1"
HEADERS = {"apikey": SUPABASE_ANON_KEY, "Content-Type": "application/json"}
ADMIN_HEADERS = {
    "apikey": SUPABASE_SERVICE_ROLE_KEY,
    "Authorization": f"Bearer {SUPABASE_SERVICE_ROLE_KEY}",
    "Content-Type": "application/json",
}


def is_supabase_configured():
    """True when real Supabase credentials are provided."""
    return (
        bool(SUPABASE_URL)
        and not SUPABASE_URL.startswith("https://your-project")
        and bool(SUPABASE_ANON_KEY)
        and not SUPABASE_ANON_KEY.startswith("your-anon")
    )


# ---------- Local Password & Token Helpers ----------

def _hash_password(password: str) -> str:
    salt = os.urandom(16).hex()
    pwd_hash = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 100_000).hex()
    return f"{salt}:{pwd_hash}"


def _verify_password(password: str, stored_hash: str) -> bool:
    try:
        salt, expected_hash = stored_hash.split(":")
        calc_hash = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 100_000).hex()
        return hmac.compare_digest(calc_hash, expected_hash)
    except Exception:
        return False


def _create_token(user_id: str) -> str:
    ts = str(int(time.time()))
    data = f"{user_id}:{ts}".encode("utf-8")
    sig = hmac.new(AUTH_SECRET.encode("utf-8"), data, hashlib.sha256).hexdigest()
    return f"{user_id}:{ts}:{sig}"


def _verify_token(token: str):
    try:
        parts = token.split(":")
        if len(parts) != 3:
            return None
        user_id, ts, sig = parts
        data = f"{user_id}:{ts}".encode("utf-8")
        expected_sig = hmac.new(AUTH_SECRET.encode("utf-8"), data, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, expected_sig):
            return None
        # Valid for 30 days
        if time.time() - int(ts) > 30 * 86400:
            return None
        return user_id
    except Exception:
        return None


# ---------- Main Auth Interface ----------

def sign_up(email, password, role, extra_metadata):
    """
    Creates an account. Tries Supabase if configured, otherwise uses local PostgreSQL.
    Always returns a dict with "success".
    """
    clean_email = email.strip().lower()

    if is_supabase_configured():
        metadata = {"role": role, **extra_metadata}
        try:
            response = requests.post(
                f"{AUTH_URL}/signup",
                headers=HEADERS,
                json={"email": clean_email, "password": password, "data": metadata},
                timeout=12,
            )
            if response.status_code in (200, 201):
                data = response.json()
                token = data.get("access_token")
                user = data.get("user")
                if user and token:
                    return {"success": True, "token": token, "id": user["id"], "metadata": user.get("user_metadata", {})}
                if user and _admin_confirm_user(user["id"]):
                    return log_in(clean_email, password)
        except Exception:
            pass  # Fall back to local database

    # Local PostgreSQL auth fallback
    try:
        conn = get_connection()
        existing = conn.execute("SELECT id FROM worker_accounts WHERE LOWER(email) = ?", (clean_email,)).fetchone()
        if existing:
            conn.close()
            return {"success": False, "message": "An account with this email already exists. Please log in."}

        user_id = str(uuid.uuid4())
        pwd_hash = _hash_password(password)
        now_iso = datetime.now(timezone.utc).isoformat()
        name = extra_metadata.get("name", "")
        location = extra_metadata.get("location", "")
        skills = extra_metadata.get("skills", "")

        conn.execute("""
            INSERT INTO worker_accounts (id, email, password_hash, name, location, skills, role, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (user_id, clean_email, pwd_hash, name, location, skills, role, now_iso))
        conn.commit()
        conn.close()

        token = _create_token(user_id)
        return {"success": True, "token": token, "id": user_id, "metadata": {"role": role, **extra_metadata}}
    except Exception as exc:
        return {"success": False, "message": f"Registration error: {exc}"}


def _admin_confirm_user(user_id):
    """Uses Supabase's admin API to mark a user's email as confirmed."""
    try:
        response = requests.put(
            f"{AUTH_URL}/admin/users/{user_id}",
            headers=ADMIN_HEADERS,
            json={"email_confirm": True},
            timeout=10,
        )
        return response.status_code == 200
    except Exception:
        return False


def log_in(email, password):
    """Always returns a dict with "success": True/False."""
    clean_email = email.strip().lower()

    if is_supabase_configured():
        try:
            response = requests.post(
                f"{AUTH_URL}/token?grant_type=password",
                headers=HEADERS,
                json={"email": clean_email, "password": password},
                timeout=12,
            )
            if response.status_code == 200:
                data = response.json()
                return {"success": True, "token": data["access_token"], "id": data["user"]["id"], "metadata": data["user"]["user_metadata"]}
        except Exception:
            pass

    # Local PostgreSQL auth check
    try:
        conn = get_connection()
        row = conn.execute("SELECT * FROM worker_accounts WHERE LOWER(email) = ?", (clean_email,)).fetchone()
        conn.close()

        if row is None or not _verify_password(password, row["password_hash"]):
            return {"success": False, "message": "Incorrect email or password."}

        user_id = str(row["id"])
        token = _create_token(user_id)
        return {
            "success": True,
            "token": token,
            "id": user_id,
            "metadata": {
                "role": row["role"],
                "name": row["name"],
                "location": row["location"],
                "skills": row["skills"],
            },
        }
    except Exception as exc:
        return {"success": False, "message": f"Login error: {exc}"}


def request_password_reset(email, redirect_url):
    """Request password reset link."""
    clean_email = email.strip().lower()
    if is_supabase_configured():
        try:
            requests.post(
                f"{AUTH_URL}/recover",
                headers=HEADERS,
                params={"redirect_to": redirect_url},
                json={"email": clean_email},
                timeout=10,
            )
        except Exception:
            pass
    return {"success": True}


def update_password(access_token, new_password):
    """Updates password for either local or Supabase user."""
    # Check local token first
    user_id = _verify_token(access_token)
    if user_id:
        try:
            conn = get_connection()
            new_hash = _hash_password(new_password)
            conn.execute("UPDATE worker_accounts SET password_hash = ? WHERE id = ?", (new_hash, user_id))
            conn.commit()
            conn.close()
            return {"success": True}
        except Exception as exc:
            return {"success": False, "message": f"Could not update password: {exc}"}

    if is_supabase_configured():
        try:
            res = requests.put(
                f"{AUTH_URL}/user",
                headers={
                    "apikey": SUPABASE_ANON_KEY,
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": "application/json",
                },
                json={"password": new_password},
                timeout=10,
            )
            if res.status_code == 200:
                return {"success": True}
        except Exception:
            pass

    return {"success": False, "message": "Invalid or expired reset token."}


def _extract_error_message(response, fallback):
    """Pulls error message text from response."""
    try:
        body = response.json()
        return body.get("msg") or body.get("error_description") or body.get("error") or fallback
    except Exception:
        return fallback


def get_user_from_token(token):
    """Verifies token and returns user info dictionary with id, email, and user_metadata."""
    if not token:
        return None

    # 1. Local token check
    user_id = _verify_token(token)
    if user_id:
        try:
            conn = get_connection()
            row = conn.execute("SELECT * FROM worker_accounts WHERE id = ?", (user_id,)).fetchone()
            conn.close()
            if row:
                return {
                    "id": str(row["id"]),
                    "email": row["email"],
                    "user_metadata": {
                        "role": row["role"],
                        "name": row["name"],
                        "location": row["location"],
                        "skills": row["skills"],
                    },
                }
        except Exception:
            pass

    # 2. Supabase token check if configured
    if is_supabase_configured():
        try:
            res = requests.get(
                f"{AUTH_URL}/user",
                headers={"apikey": SUPABASE_ANON_KEY, "Authorization": f"Bearer {token}"},
                timeout=8,
            )
            if res.status_code == 200:
                return res.json()
        except Exception:
            pass

    return None
