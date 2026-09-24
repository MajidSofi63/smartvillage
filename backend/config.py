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

WEATHER_API_KEY = os.environ.get("WEATHER_API_KEY", "PUT_YOUR_OPENWEATHER_API_KEY_HERE")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "PUT_YOUR_GEMINI_API_KEY_HERE")

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://your-project.supabase.co")
SUPABASE_ANON_KEY = os.environ.get("SUPABASE_ANON_KEY", "your-anon-key-here")
SUPABASE_SERVICE_ROLE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "your-service-role-key-here")

ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "changeme")
