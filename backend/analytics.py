# analytics.py
# Lightweight usage logging - lets the admin panel show real platform ACTIVITY
# (how many times each module has actually been used), not just who registered.
# This is the piece that was missing for "fully develop backend": before this,
# there was no way to see whether the platform was actually being used, only
# who had signed up.
#
# Logging failures are deliberately swallowed (never raised) - a broken
# analytics write should NEVER break the actual feature someone is using.
# Losing one usage count is fine; breaking crop prediction over it is not.

from datetime import datetime, timezone
from database import get_connection


def log_event(event_type):
    """
    Records that something happened (e.g. "crop_prediction", "telemedicine_query").
    Called right after a feature succeeds - fire-and-forget, never blocks or
    breaks the response if it fails for any reason.
    """
    try:
        conn = get_connection()
        conn.execute(
            "INSERT INTO usage_events (event_type, created_at) VALUES (?, ?)",
            (event_type, datetime.now(timezone.utc).isoformat())
        )
        conn.commit()
        conn.close()
    except Exception:
        pass  # analytics is best-effort - never let it break the real feature


def get_usage_counts():
    """Returns {"crop_prediction": 42, "telemedicine_query": 17, ...} for the admin panel."""
    conn = get_connection()
    rows = conn.execute("SELECT event_type, COUNT(*) AS count FROM usage_events GROUP BY event_type").fetchall()
    conn.close()
    return {r["event_type"]: r["count"] for r in rows}
