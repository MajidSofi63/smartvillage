# crop_weather.py
# Fetches live conditions and a 7-day forecast for the selected district from
# Open-Meteo (no API key needed).
#
# This data is shown for context only. The recommendation model uses the
# historical seasonal weather stored in the crop_stats table, never this live
# reading, so a weather outage cannot break a recommendation.

import threading
import time

import requests


class WeatherService:
    """Fetch live weather and a short forecast from Open-Meteo."""

    def __init__(self):
        self.forecast_url = "https://api.open-meteo.com/v1/forecast"
        # Reuse one HTTP connection instead of opening a new one per request.
        self.session = requests.Session()
        self.cache = {}
        self.cache_lock = threading.Lock()
        # Successful payloads stay valid for ten minutes.
        self.cache_ttl_seconds = 600
        # Failures are retried sooner so a transient outage can recover.
        self.failure_ttl_seconds = 60

    def get_live_weather_and_forecast(self, lat, lon):
        """Return current conditions and a 7-day forecast for display only."""
        key = (round(float(lat), 4), round(float(lon), 4))
        now = time.time()

        with self.cache_lock:
            entry = self.cache.get(key)
            if entry is not None and now - entry[0] < entry[2]:
                return entry[1]

        result = self._fetch(lat, lon)
        ttl = (
            self.cache_ttl_seconds
            if result.get("success")
            else self.failure_ttl_seconds
        )
        with self.cache_lock:
            self.cache[key] = (now, result, ttl)
        return result

    def _fetch(self, lat, lon):
        """Call Open-Meteo once and shape the response for the UI."""
        params = {
            "latitude": lat,
            "longitude": lon,
            "current": (
                "temperature_2m,relative_humidity_2m,precipitation,wind_speed_10m"
            ),
            "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum",
            "forecast_days": 7,
            "timezone": "Asia/Kolkata",
        }
        try:
            # A short timeout keeps recommendations responsive.
            response = self.session.get(self.forecast_url, params=params, timeout=8)
            response.raise_for_status()
            data = response.json()

            current = data.get("current", {})
            current_weather = {
                "temperature": current.get("temperature_2m"),
                "humidity": current.get("relative_humidity_2m"),
                "precipitation": current.get("precipitation"),
                "wind_speed": current.get("wind_speed_10m"),
                "time": current.get("time"),
            }

            daily = data.get("daily", {})
            forecast = []
            for index in range(len(daily.get("time", []))):
                forecast.append(
                    {
                        "date": daily["time"][index],
                        "temp_max": daily["temperature_2m_max"][index],
                        "temp_min": daily["temperature_2m_min"][index],
                        "precipitation": daily["precipitation_sum"][index],
                    }
                )

            return {"current": current_weather, "forecast": forecast, "success": True}
        except Exception as exc:
            # Live display data is optional; never break the recommendation.
            return {
                "current": None,
                "forecast": [],
                "success": False,
                "error": str(exc),
            }


weather_service = WeatherService()
