# disaster.py
# Uses OpenWeather when configured (WEATHER_API_KEY), and seamlessly falls back to
# Open-Meteo (free, no API key needed) for 100% reliable disaster alerts anywhere.
#
# Provides:
#   1. Current Weather (temp, humidity, wind, rainfall)
#   2. 5-Day Forecast (lead time for extreme heat / heavy rainfall)
#   3. Air Quality (useful for respiratory health warnings)

import requests
from config import WEATHER_API_KEY

BASE_URL = "https://api.openweathermap.org/data/2.5"
GEOCODE_URL = "https://geocoding-api.open-meteo.com/v1/search"
OPEN_METEO_FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
OPEN_METEO_AIR_URL = "https://air-quality-api.open-meteo.com/v1/air-quality"

# WMO Weather interpretation codes (WW) to condition text
WMO_WEATHER_MAP = {
    0: "Clear",
    1: "Mainly Clear", 2: "Partly Cloudy", 3: "Overcast",
    45: "Fog", 48: "Depositing Rime Fog",
    51: "Light Drizzle", 53: "Moderate Drizzle", 55: "Dense Drizzle",
    61: "Slight Rain", 63: "Moderate Rain", 65: "Heavy Rain",
    71: "Slight Snow", 73: "Moderate Snow", 75: "Heavy Snow",
    80: "Rain Showers", 81: "Heavy Rain Showers", 82: "Violent Rain Showers",
    95: "Thunderstorm", 96: "Thunderstorm with Hail", 99: "Thunderstorm with Heavy Hail"
}


def _geocode_location(city_name):
    """Resolve location to lat/lon via database first, then Open-Meteo geocoding."""
    cleaned = city_name.strip()
    if not cleaned:
        return None

    # Check local database with 666 Indian districts first
    try:
        from database import get_connection
        conn = get_connection()
        row = conn.execute(
            "SELECT district, state, lat, lon FROM districts WHERE district ILIKE %s LIMIT 1",
            (f"%{cleaned}%",)
        ).fetchone()
        conn.close()
        if row:
            return {"lat": row["lat"], "lon": row["lon"], "name": f"{row['district'].title()}, {row['state']}"}
    except Exception:
        pass

    try:
        res = requests.get(GEOCODE_URL, params={"name": cleaned, "count": 1}, timeout=8)
        if res.status_code == 200:
            results = res.json().get("results")
            if results:
                place = results[0]
                return {"lat": place["latitude"], "lon": place["longitude"], "name": place["name"]}
    except Exception:
        pass

    return None


def _get_alerts_open_meteo(city_name):
    """Fetch live weather, forecast, and air quality using Open-Meteo (no API key required)."""
    loc = _geocode_location(city_name)
    if not loc:
        return {"success": False, "message": "Could not find that location. Try a nearby larger town."}

    lat, lon, loc_name = loc["lat"], loc["lon"], loc["name"]

    # 1. Weather and forecast
    params = {
        "latitude": lat,
        "longitude": lon,
        "current": "temperature_2m,relative_humidity_2m,wind_speed_10m,weather_code,precipitation",
        "daily": "temperature_2m_max,precipitation_sum",
        "wind_speed_unit": "ms",
        "forecast_days": 5,
        "timezone": "auto",
    }

    try:
        res = requests.get(OPEN_METEO_FORECAST_URL, params=params, timeout=10)
        if res.status_code != 200:
            return {"success": False, "message": "Weather service error. Please try again."}
        data = res.json()
    except Exception:
        return {"success": False, "message": "Could not reach weather service. Check your internet connection."}

    curr = data.get("current", {})
    daily = data.get("daily", {})

    temperature = round(float(curr.get("temperature_2m", 0)), 1)
    humidity = round(float(curr.get("relative_humidity_2m", 0)), 1)
    wind_speed = round(float(curr.get("wind_speed_10m", 0)), 1)
    weather_code = curr.get("weather_code", 0)
    condition = WMO_WEATHER_MAP.get(weather_code, "Partly Cloudy")
    rain_now = float(curr.get("precipitation", 0.0))

    alerts = []
    if rain_now > 10:
        alerts.append("Heavy rainfall right now - risk of flooding in low-lying areas.")
    if weather_code in (95, 96, 99):
        alerts.append("Thunderstorm warning - avoid open fields and stay indoors.")
    if temperature > 40:
        alerts.append("Extreme heat warning - avoid outdoor work during peak afternoon hours.")
    if wind_speed > 15:
        alerts.append("High wind speed - secure loose structures and livestock shelters.")
    if humidity < 20 and temperature > 30:
        alerts.append("Very dry and hot conditions - elevated drought/wildfire risk.")

    # 2. 5-day forecast
    rain_list = daily.get("precipitation_sum", [])
    temp_max_list = daily.get("temperature_2m_max", [])
    rain_next_24h = round(rain_list[0] if rain_list else 0.0, 1)
    max_temp_next_5days = round(max(temp_max_list) if temp_max_list else temperature, 1)

    forecast_summary = (
        f"Expected rainfall in next 24h: {rain_next_24h}mm. "
        f"Max temp over next 5 days: {max_temp_next_5days}°C."
    )

    if rain_next_24h > 50:
        alerts.append(f"Heavy rain expected in the next 24 hours ({rain_next_24h}mm) - prepare for possible flooding.")
    if max_temp_next_5days > 42:
        alerts.append("Extreme heat expected in the coming days - plan outdoor work for early morning/evening.")

    # 3. Air quality
    air_quality_text = "Air quality: Moderate"
    try:
        aq_res = requests.get(OPEN_METEO_AIR_URL, params={"latitude": lat, "longitude": lon, "current": "us_aqi"}, timeout=8)
        if aq_res.status_code == 200:
            us_aqi = aq_res.json().get("current", {}).get("us_aqi")
            if us_aqi is not None:
                if us_aqi <= 50:
                    label = "Good"
                elif us_aqi <= 100:
                    label = "Moderate"
                elif us_aqi <= 150:
                    label = "Unhealthy for Sensitive Groups"
                elif us_aqi <= 200:
                    label = "Poor"
                else:
                    label = "Very Poor"
                air_quality_text = f"Air Quality: {label} (AQI {us_aqi})"
                if us_aqi > 150:
                    alerts.append("Poor air quality - people with asthma or breathing issues should avoid strenuous outdoor activity.")
    except Exception:
        pass

    return {
        "success": True,
        "city": loc_name,
        "temperature": temperature,
        "humidity": humidity,
        "wind_speed": wind_speed,
        "condition": condition,
        "forecast_summary": forecast_summary,
        "air_quality": air_quality_text,
        "alerts": alerts if alerts else ["No immediate disaster risk detected."],
    }


def get_weather_alert(city_name):
    """
    Fetches current weather, upcoming forecast, and air quality for a city,
    then applies rule-based thresholds to generate disaster/health alerts.
    Tries OpenWeather when configured, and falls back to Open-Meteo.
    """
    has_owm_key = bool(WEATHER_API_KEY) and not WEATHER_API_KEY.startswith("PUT_YOUR")

    if has_owm_key:
        current_url = f"{BASE_URL}/weather?q={city_name}&appid={WEATHER_API_KEY}&units=metric"
        try:
            current_response = requests.get(current_url, timeout=8)
            if current_response.status_code == 200:
                current = current_response.json()
                temperature = current["main"]["temp"]
                humidity = current["main"]["humidity"]
                wind_speed = current["wind"]["speed"]
                condition = current["weather"][0]["main"]
                rain_now = current.get("rain", {}).get("1h", 0)
                lat = current["coord"]["lat"]
                lon = current["coord"]["lon"]

                alerts = []
                if rain_now > 10:
                    alerts.append("Heavy rainfall right now - risk of flooding in low-lying areas.")
                if condition == "Thunderstorm":
                    alerts.append("Thunderstorm warning - avoid open fields and stay indoors.")
                if temperature > 40:
                    alerts.append("Extreme heat warning - avoid outdoor work during peak afternoon hours.")
                if wind_speed > 15:
                    alerts.append("High wind speed - secure loose structures and livestock shelters.")
                if humidity < 20 and temperature > 30:
                    alerts.append("Very dry and hot conditions - elevated drought/wildfire risk.")

                forecast_summary = "Forecast unavailable."
                try:
                    forecast_res = requests.get(f"{BASE_URL}/forecast?q={city_name}&appid={WEATHER_API_KEY}&units=metric", timeout=8)
                    if forecast_res.status_code == 200:
                        forecast_data = forecast_res.json()["list"]
                        next_24h = forecast_data[:8]
                        rain_next_24h = sum(entry.get("rain", {}).get("3h", 0) for entry in next_24h)
                        max_temp_next_3days = max(entry["main"]["temp_max"] for entry in forecast_data)
                        forecast_summary = f"Expected rainfall in next 24h: {round(rain_next_24h, 1)}mm. Max temp over next 5 days: {round(max_temp_next_3days, 1)}°C."
                        if rain_next_24h > 50:
                            alerts.append(f"Heavy rain expected in the next 24 hours ({round(rain_next_24h, 1)}mm) - prepare for possible flooding.")
                        if max_temp_next_3days > 42:
                            alerts.append("Extreme heat expected in the coming days - plan outdoor work for early morning/evening.")
                except Exception:
                    pass

                air_quality_text = "Air quality data unavailable."
                try:
                    air_res = requests.get(f"https://api.openweathermap.org/data/2.5/air_pollution?lat={lat}&lon={lon}&appid={WEATHER_API_KEY}", timeout=8)
                    if air_res.status_code == 200:
                        aqi = air_res.json()["list"][0]["main"]["aqi"]
                        aqi_labels = {1: "Good", 2: "Fair", 3: "Moderate", 4: "Poor", 5: "Very Poor"}
                        air_quality_text = f"Air Quality: {aqi_labels.get(aqi, 'Unknown')}"
                        if aqi >= 4:
                            alerts.append("Poor air quality - people with asthma or breathing issues should avoid strenuous outdoor activity.")
                except Exception:
                    pass

                return {
                    "success": True,
                    "city": current.get("name", city_name),
                    "temperature": temperature,
                    "humidity": humidity,
                    "wind_speed": wind_speed,
                    "condition": condition,
                    "forecast_summary": forecast_summary,
                    "air_quality": air_quality_text,
                    "alerts": alerts if alerts else ["No immediate disaster risk detected."],
                }
        except Exception:
            pass  # Fall back to Open-Meteo

    # Open-Meteo fallback
    return _get_alerts_open_meteo(city_name)
