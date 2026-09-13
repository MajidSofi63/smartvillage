# disaster.py
# Uses THREE free OpenWeather endpoints together for a fuller picture:
#   1. Current Weather      - what's happening right now
#   2. 5 Day / 3 Hour Forecast - lets us warn about heavy rain coming in the next 1-3 days
#   3. Air Pollution API    - air quality, useful for respiratory health warnings
# All three are on OpenWeather's free tier (no credit card needed), unlike "One Call 3.0"
# which now requires billing details even for its free quota.
#
# NOTE: If you'd rather not deal with OpenWeather's signup at all, Open-Meteo
# (https://open-meteo.com) is a genuinely free alternative that needs NO API key -
# just say the word and I'll swap this module to use it instead.

import requests
from config import WEATHER_API_KEY

BASE_URL = "https://api.openweathermap.org/data/2.5"


def get_weather_alert(city_name):
    """
    Fetches current weather, upcoming forecast, and air quality for a city,
    then applies rule-based thresholds to generate disaster/health alerts.
    """

    # ---- 1. Current weather (also gives us lat/lon for the air quality call) ----
    current_url = f"{BASE_URL}/weather?q={city_name}&appid={WEATHER_API_KEY}&units=metric"
    try:
        current_response = requests.get(current_url, timeout=10)
    except requests.exceptions.RequestException:
        return {"success": False, "message": "Could not reach the weather service. Check your internet connection."}

    if current_response.status_code != 200:
        return {"success": False, "message": "Could not fetch weather. Check the city name or API key in config.py."}

    current = current_response.json()

    temperature = current["main"]["temp"]
    humidity = current["main"]["humidity"]
    wind_speed = current["wind"]["speed"]  # metres/second
    condition = current["weather"][0]["main"]  # e.g. "Rain", "Clear", "Thunderstorm"
    rain_now = current.get("rain", {}).get("1h", 0)  # mm in the last hour
    lat = current["coord"]["lat"]
    lon = current["coord"]["lon"]

    alerts = []

    # ---- Current-condition rules ----
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

    # ---- 2. 5-day / 3-hour forecast (gives lead time, matching your synopsis's 3-5 day target) ----
    forecast_url = f"{BASE_URL}/forecast?q={city_name}&appid={WEATHER_API_KEY}&units=metric"
    try:
        forecast_response = requests.get(forecast_url, timeout=10)
    except requests.exceptions.RequestException:
        forecast_response = None

    forecast_summary = "Forecast unavailable."
    if forecast_response is not None and forecast_response.status_code == 200:
        forecast_data = forecast_response.json()["list"]

        # each entry is a 3-hour slot; the next 8 entries cover the next 24 hours
        next_24h = forecast_data[:8]
        rain_next_24h = sum(entry.get("rain", {}).get("3h", 0) for entry in next_24h)
        max_temp_next_3days = max(entry["main"]["temp_max"] for entry in forecast_data)

        forecast_summary = f"Expected rainfall in next 24h: {round(rain_next_24h, 1)}mm. Max temp over next 5 days: {round(max_temp_next_3days, 1)}°C."

        if rain_next_24h > 50:
            alerts.append(f"Heavy rain expected in the next 24 hours ({round(rain_next_24h, 1)}mm) - prepare for possible flooding.")
        if max_temp_next_3days > 42:
            alerts.append("Extreme heat expected in the coming days - plan outdoor work for early morning/evening.")

    # ---- 3. Air quality (uses lat/lon from the current-weather call) ----
    air_url = f"https://api.openweathermap.org/data/2.5/air_pollution?lat={lat}&lon={lon}&appid={WEATHER_API_KEY}"
    try:
        air_response = requests.get(air_url, timeout=10)
    except requests.exceptions.RequestException:
        air_response = None

    air_quality_text = "Air quality data unavailable."
    if air_response is not None and air_response.status_code == 200:
        aqi = air_response.json()["list"][0]["main"]["aqi"]  # scale 1 (good) to 5 (very poor)
        aqi_labels = {1: "Good", 2: "Fair", 3: "Moderate", 4: "Poor", 5: "Very Poor"}
        air_quality_text = f"Air Quality: {aqi_labels.get(aqi, 'Unknown')}"

        if aqi >= 4:
            alerts.append("Poor air quality - people with asthma or breathing issues should avoid strenuous outdoor activity.")

    return {
        "success": True,
        "city": city_name,
        "temperature": temperature,
        "humidity": humidity,
        "wind_speed": wind_speed,
        "condition": condition,
        "forecast_summary": forecast_summary,
        "air_quality": air_quality_text,
        "alerts": alerts if alerts else ["No immediate disaster risk detected."],
    }
