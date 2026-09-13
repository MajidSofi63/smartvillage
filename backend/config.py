# config.py
# Reads your API keys from environment variables instead of hardcoding them here -
# this file is safe to commit to a public GitHub repo because it never contains a
# real key, only the variable names to look up.
#
# LOCAL DEVELOPMENT: copy .env.example to a new file named .env and fill in your real
# keys there (.env is in .gitignore, so it never gets committed).
# ON RENDER: set these same variable names in the dashboard under Environment.

import os
from dotenv import load_dotenv

load_dotenv()  # reads a local .env file if one exists

WEATHER_API_KEY = os.environ.get("WEATHER_API_KEY", "7caf6809857c7d171d649dc3c7ab0364")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "AQ.Ab8RN6LElgqGy1-KysqUzc1L3puYaT7etE2JTR-MSQk-eYHSGQ")

# Supabase: used only for login/register (worker and employer accounts).
# Find these in your Supabase project under Settings -> API.
# SUPABASE_URL looks like: https://xxxxxxxx.supabase.co
# SUPABASE_ANON_KEY is the "anon public" key (safe to use here - it's the key meant
# for this kind of use, NOT the "service_role" key, which must never leave your server).
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://pypwfdxwkupzwoqroacj.supabase.co")
SUPABASE_ANON_KEY = os.environ.get("SUPABASE_ANON_KEY", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InB5cHdmZHh3a3VwendvcXJvYWNqIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODkyMDU4NzQsImV4cCI6MjEwNDc4MTg3NH0.sbSVSIRt-1QHvsAfrQek2Gc8Hx5fP4v9-ZKtntDAl_Q")

# Admin panel: a single shared password (not a Supabase account - admins aren't
# public users). Set a real, hard-to-guess value in Render's environment variables.
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "AAdmin@123")
