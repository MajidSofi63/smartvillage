# auth.py
# Uses Supabase Auth (a hosted, managed authentication service) instead of hand-rolled
# password hashing - Supabase handles secure password storage, session tokens, and
# account management for us. We store which role ("worker") and basic profile info
# as metadata on each Supabase account at signup time.
#
# ONE-TIME SUPABASE SETTING NEEDED: in your Supabase project, go to
# Authentication -> Sign In / Providers, and turn OFF "Confirm email". Without this,
# Supabase requires clicking a confirmation link before an account can log in.
#
# NOTE: we use EMAIL (not phone) as the login identity. Supabase's phone-based auth
# requires a paid SMS provider (Twilio etc.) configured just to turn it on - there's
# no free path for phone login. Email is free and doesn't need any extra service.
# Phone number is still collected and stored as a separate CONTACT field on workers.

import requests
from config import SUPABASE_URL, SUPABASE_ANON_KEY, SUPABASE_SERVICE_ROLE_KEY

AUTH_URL = f"{SUPABASE_URL}/auth/v1"
HEADERS = {"apikey": SUPABASE_ANON_KEY, "Content-Type": "application/json"}

# Headers for privileged admin calls - uses the service_role key, never sent to the browser
ADMIN_HEADERS = {
    "apikey": SUPABASE_SERVICE_ROLE_KEY,
    "Authorization": f"Bearer {SUPABASE_SERVICE_ROLE_KEY}",
    "Content-Type": "application/json",
}


def sign_up(email, password, role, extra_metadata):
    """
    Creates a Supabase account with the given role and any extra profile fields
    stored as account metadata. If the account comes back unconfirmed, this
    force-confirms it via the admin API and logs in immediately, so the person
    gets a working session either way. Always returns a dict with "success".
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

    if user is None:
        return {"success": False, "message": "Registration failed - no user was returned."}

    if token is not None:
        return {"success": True, "token": token, "id": user["id"], "metadata": user.get("user_metadata", {})}

    # No session means the account is sitting unconfirmed - force-confirm it ourselves
    if not _admin_confirm_user(user["id"]):
        return {"success": False, "message": "Account created but could not be auto-confirmed. Check SUPABASE_SERVICE_ROLE_KEY is set correctly."}

    login_result = log_in(email, password)
    if not login_result["success"]:
        return {"success": False, "message": "Account was confirmed but automatic login failed - please try logging in manually."}
    return login_result


def _admin_confirm_user(user_id):
    """Uses Supabase's admin API to mark a user's email as confirmed, bypassing the need to click a link."""
    try:
        response = requests.put(
            f"{AUTH_URL}/admin/users/{user_id}",
            headers=ADMIN_HEADERS,
            json={"email_confirm": True},
            timeout=15,
        )
    except requests.exceptions.RequestException:
        return False
    return response.status_code == 200


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
    metadata), or None if the token is missing/invalid/expired.
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
