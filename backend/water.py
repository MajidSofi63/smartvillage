# water.py
# Real, location-based water/soil data using Open-Meteo (completely free, no API key,
# no signup required - https://open-meteo.com). Replaces the earlier random simulation.
#
# HONESTY NOTE: there is no public, free API that reports actual reservoir levels for
# arbitrary villages - that data usually sits with local irrigation departments, not
# in a global dataset. So for "reservoir status" we compute a real water-balance proxy
# instead (rainfall minus evapotranspiration over the last few days) rather than faking
# a sensor reading. Soil moisture, on the other hand, IS real satellite/model data.

import requests

GEOCODE_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"


def _geocode(city_name):
    """Turns a city/village name into latitude/longitude using Open-Meteo's free geocoder."""
    try:
        response = requests.get(GEOCODE_URL, params={"name": city_name, "count": 1}, timeout=10)
    except requests.exceptions.RequestException:
        return None  # no internet / DNS failure / timeout

    if response.status_code != 200:
        return None

    results = response.json().get("results")
    if not results:
        return None  # place name not found

    place = results[0]
    return {"lat": place["latitude"], "lon": place["longitude"], "name": place["name"]}


def get_water_status(city_name):
    """
    Looks up the given city/village and returns real soil moisture plus a rainfall-vs-
    evaporation water balance, with irrigation/conservation advice based on both.
    """
    location = _geocode(city_name)
    if location is None:
        return {"success": False, "message": "Could not find that location. Try a nearby larger town."}

    params = {
        "latitude": location["lat"],
        "longitude": location["lon"],
        "hourly": "soil_moisture_0_to_7cm,soil_moisture_7_to_28cm",
        "daily": "precipitation_sum,et0_fao_evapotranspiration",
        "past_days": 3,
        "forecast_days": 1,
        "timezone": "auto",
    }

    try:
        response = requests.get(FORECAST_URL, params=params, timeout=10)
    except requests.exceptions.RequestException:
        return {"success": False, "message": "Could not reach the weather service. Check your internet connection."}

    if response.status_code != 200:
        return {"success": False, "message": "Weather service error - please try again."}

    data = response.json()

    # ---- Soil moisture: average today's hourly readings from the two topsoil layers ----
    shallow = data["hourly"]["soil_moisture_0_to_7cm"][-24:]   # last 24 hourly readings = today
    root_zone = data["hourly"]["soil_moisture_7_to_28cm"][-24:]
    all_readings = shallow + root_zone
    avg_moisture_m3 = sum(all_readings) / len(all_readings)  # m³/m³, roughly 0.05 (dry) to 0.5 (saturated)
    soil_moisture_percent = round(min(100, (avg_moisture_m3 / 0.5) * 100), 1)  # rough % of saturation

    # ---- Water balance: rainfall minus evapotranspiration over the last 3 days ----
    rainfall_3d = sum(data["daily"]["precipitation_sum"][:3])
    evap_3d = sum(data["daily"]["et0_fao_evapotranspiration"][:3])
    water_balance_mm = round(rainfall_3d - evap_3d, 1)  # positive = net water gain, negative = net loss

    # ---- Same threshold logic as before, now driven by real numbers instead of random() ----
    if soil_moisture_percent < 30:
        moisture_status = "Low"
        moisture_advice = "Soil is dry. Irrigation is recommended within the next 24 hours."
    elif soil_moisture_percent < 60:
        moisture_status = "Moderate"
        moisture_advice = "Soil moisture is adequate for now. Re-check in 2-3 days."
    else:
        moisture_status = "Good"
        moisture_advice = "Soil moisture is sufficient. No irrigation needed."

    if water_balance_mm < -10:
        water_status = "Critical"
        water_advice = "Evaporation has significantly outpaced rainfall this week. Conserve water and prioritise essential use."
    elif water_balance_mm < 0:
        water_status = "Low"
        water_advice = "Slight net water loss this week. Use water efficiently."
    else:
        water_status = "Healthy"
        water_advice = "Rainfall has kept pace with or exceeded evaporation this week."

    return {
        "success": True,
        "location_name": location["name"],
        "soil_moisture_percent": soil_moisture_percent,
        "moisture_status": moisture_status,
        "moisture_advice": moisture_advice,
        "water_balance_mm": water_balance_mm,
        "water_status": water_status,
        "water_advice": water_advice,
    }
