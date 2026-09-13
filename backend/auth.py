# auth.py
# Uses Supabase Auth (a hosted, managed authentication service) instead of hand-rolled
# password hashing - Supabase handles secure password storage, session tokens, and
# account management for us. We store which role ("worker" or "employer") and basic
# profile info as metadata on each Supabase account at signup time.
#
# ONE-TIME SUPABASE SETTING NEEDED: in your Supabase project, go to
# Authentication -> Providers -> Email, and turn OFF "Confirm email". Without this,
# Supabase requires clicking a confirmation link (sent to a real inbox) before an
# account can log in - fine for a real product, but adds friction for a demo/project
# where you're creating test accounts quickly.
#
# NOTE: we use EMAIL (not phone) as the login identity. Supabase's phone-based auth
# requires a paid SMS provider (Twilio etc.) configured just to turn it on - there's
# no free path for phone login. Email is free and doesn't need any extra service.
# Phone number is still collected and stored as a separate CONTACT field on workers.

import requests
from config import SUPABASE_URL, SUPABASE_ANON_KEY

AUTH_URL = f"{SUPABASE_URL}/auth/v1"
HEADERS = {"apikey": SUPABASE_ANON_KEY, "Content-Type": "application/json"}


def sign_up(email, password, role, extra_metadata):
    """
    Creates a Supabase account with the given role ('worker' or 'employer') and any
    extra profile fields (name, location, skills, etc.) stored as account metadata.
    Always returns a dict with "success": True/False, so the real reason for a
    failure (weak password, email already used, etc.) can be shown to the person
    instead of a generic "something went wrong".
    """
    metadata = {"role": role, **extra_metadata}

    try:
        response = requests.post(
            f"{AUTH_URL}/signup",
            headers=HEADERS,
            json={"email": email, "password": password, "data": metadata},
            timeout=15,
        )
    except requests.exceptions.RequestException:
        return {"success": False, "message": "Could not reach Supabase. Check your internet connection."}

    if response.status_code not in (200, 201):
        message = _extract_error_message(response, "Registration failed.")
        return {"success": False, "message": message}

    data = response.json()
    token = data.get("access_token")
    user = data.get("user")

    if token is None or user is None:
        # Usually means "Confirm email" is still turned on in Supabase - see the
        # note at the top of this file for how to turn it off.
        return {"success": False, "message": "Account created, but no session was returned - check that 'Confirm email' is disabled in Supabase."}

    return {"success": True, "token": token, "id": user["id"], "metadata": user.get("user_metadata", {})}


def log_in(email, password):
    """Always returns a dict with "success": True/False and a real error message on failure."""
    try:
        response = requests.post(
            f"{AUTH_URL}/token?grant_type=password",
            headers=HEADERS,
            json={"email": email, "password": password},
            timeout=15,
        )
    except requests.exceptions.RequestException:
        return {"success": False, "message": "Could not reach Supabase. Check your internet connection."}

    if response.status_code != 200:
        message = _extract_error_message(response, "Incorrect email or password.")
        return {"success": False, "message": message}

    data = response.json()
    return {"success": True, "token": data["access_token"], "id": data["user"]["id"], "metadata": data["user"]["user_metadata"]}


def _extract_error_message(response, fallback):
    """Pulls Supabase's actual error text out of its response, falling back to a generic message."""
    try:
        body = response.json()
    except ValueError:
        return fallback
    return body.get("msg") or body.get("error_description") or body.get("error") or fallback


def get_user_from_token(token):
    """
    Verifies a login token with Supabase and returns the full user info (id, email,
    metadata), or None if the token is missing/invalid/expired. Used on every request
    to a protected route to confirm who's making it.
    """
    try:
        response = requests.get(
            f"{AUTH_URL}/user",
            headers={"apikey": SUPABASE_ANON_KEY, "Authorization": f"Bearer {token}"},
            timeout=15,
        )
    except requests.exceptions.RequestException:
        return None

    if response.status_code != 200:
        return None
    return response.json()
