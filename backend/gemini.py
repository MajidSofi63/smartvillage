# gemini.py
# Calls Google's Gemini API for two things:
#   1. The floating chat assistant (ask_gemini)
#   2. Enhancing + translating telemedicine advice (get_telemedicine_advice)
#
# NOTE ON THE MODEL NAME: Google deprecates these fast. gemini-2.0-flash and
# then gemini-2.5-flash both stopped working for new users within months of
# each other. Currently using gemini-3.6-flash per Google's own error message
# recommendation. If this breaks again, check https://ai.google.dev/gemini-api/docs/models
# for the current model name and swap it into MODEL_NAME below - nothing else needs to change.

import requests
from config import GEMINI_API_KEY

MODEL_NAME = "gemini-3.6-flash"
GEMINI_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL_NAME}:generateContent"

LANGUAGE_NAMES = {"en": "English", "hi": "Hindi", "ur": "Urdu"}

SYSTEM_CONTEXT = (
    "You are the assistant for the AI Smart Village Platform, a rural-services web app "
    "with six tabs: Crop Prediction, Telemedicine, Government Schemes, Water Management, "
    "Disaster Alerts, and Employment. Answer the user's question briefly and, where useful, "
    "tell them which tab to use for the actual tool. Never give a medical diagnosis - always "
    "recommend seeing a doctor for health questions. Keep answers short and simple, rural "
    "users may have limited digital literacy."
)


def _call_gemini(prompt_text):
    """
    Low-level helper: sends one prompt to Gemini and returns the reply text,
    or None if the call failed for any reason (bad key, model down, etc.).
    """
    headers = {"Content-Type": "application/json", "x-goog-api-key": GEMINI_API_KEY}
    payload = {"contents": [{"parts": [{"text": prompt_text}]}]}

    try:
        response = requests.post(GEMINI_URL, headers=headers, json=payload, timeout=15)
    except requests.exceptions.RequestException:
        return None  # network problem (no internet, DNS failure, etc.)

    if response.status_code != 200:
        # Printing this helps you see the REAL reason in the terminal running uvicorn
        # (e.g. 400 = bad request, 403 = bad API key, 404 = model name wrong)
        print(f"Gemini API error {response.status_code}: {response.text[:300]}")
        return None

    data = response.json()
    try:
        return data["candidates"][0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError):
        return None


def ask_gemini(user_message):
    """Used by the floating chat assistant."""
    reply = _call_gemini(SYSTEM_CONTEXT + "\n\nUser question: " + user_message)
    if reply is None:
        return ("Sorry, the assistant isn't available right now. Check the terminal running "
                "uvicorn for the exact error, and confirm your Gemini API key in config.py.")
    return reply


def get_crop_explanation(area, crop, rainfall, pesticides, temperature, predicted_yield, language_code):
    """
    Explains a crop yield prediction in plain language: whether it's high/low,
    what's likely driving it, and how to improve it - written in the user's language.
    The NUMBER always comes from the trained ML model, never from Gemini - this only
    interprets and advises around a number that has already been computed.
    """
    language_name = LANGUAGE_NAMES.get(language_code, "English")

    prompt = (
        f"A machine learning model predicted a crop yield of {predicted_yield} hg/ha for {crop} "
        f"in {area}, given: average rainfall {rainfall}mm/year, pesticide use {pesticides} tonnes, "
        f"average temperature {temperature}°C. Explain to a farmer, in {language_name}, in under 100 words: "
        f"(1) whether this yield seems high, average, or low for this crop, (2) which input factor "
        f"(rainfall, pesticide use, or temperature) most likely helped or hurt it, and (3) two concrete, "
        f"practical suggestions to improve next season's yield. Keep language simple, no jargon."
    )

    reply = _call_gemini(prompt)
    if reply is None:
        return "AI explanation unavailable right now - showing the raw prediction only."
    return reply


def get_telemedicine_advice(symptoms, local_condition, local_advice, urgent, language_code):
    """
    Takes the LOCAL keyword-matched result (which we trust for the urgent/not-urgent
    safety flag) and asks Gemini to turn it into a clearer, more complete explanation,
    written in the user's chosen language. If Gemini is unavailable, we fall back to
    the local English advice so the feature still works offline.
    """
    language_name = LANGUAGE_NAMES.get(language_code, "English")

    prompt = (
        f"A rural telemedicine app matched these symptoms: \"{symptoms}\" "
        f"to the likely condition \"{local_condition}\" with this basic advice: \"{local_advice}\". "
        f"Urgency level: {'URGENT - needs immediate medical care' if urgent else 'not urgent'}. "
        f"Rewrite this as a clear, simple, well-explained response for a rural user with limited "
        f"medical knowledge, in {language_name}. Include: what the condition likely is, what to do "
        f"right now, and a clear reminder to see a real doctor - this is not a diagnosis. "
        f"Keep it under 120 words. Do not use complex medical jargon."
    )

    reply = _call_gemini(prompt)
    if reply is None:
        # Fall back to the plain local advice (English) with a note explaining why
        return local_advice + " (AI enhancement unavailable right now - showing basic offline guidance.)"
    return reply
