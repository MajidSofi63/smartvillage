# gemini.py
# Calls Google's Gemini API for two things:
#   1. The floating chat assistant (ask_gemini)
#   2. Enhancing + translating telemedicine advice (get_telemedicine_advice)
#
# NOTE ON THE MODEL NAME: Google deprecates these fast. The model is read from
# GEMINI_MODEL in .env (default: gemini-3.6-flash). If it stops working, check
# https://ai.google.dev/gemini-api/docs/models for a current name and update
# .env - no code change is needed.

import threading
import requests
from config import GEMINI_API_KEY, GEMINI_ENABLED, GEMINI_MODEL

MODEL_NAME = GEMINI_MODEL
FALLBACK_MODELS = [MODEL_NAME, "gemini-flash-latest", "gemini-3.8-flash", "gemini-3.5-flash"]
GEMINI_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL_NAME}:generateContent"

LANGUAGE_NAMES = {"en": "English", "hi": "Hindi", "ur": "Urdu"}

# Initialize google-genai client if installed
_genai_client = None
try:
    import warnings
    warnings.filterwarnings("ignore", category=UserWarning, module="google.genai")
    from google import genai
    if GEMINI_API_KEY and not GEMINI_API_KEY.startswith("PUT_YOUR"):
        _genai_client = genai.Client(api_key=GEMINI_API_KEY)
except Exception:
    _genai_client = None


def is_configured():
    """True when Gemini is enabled and a real key has been supplied."""
    return (
        GEMINI_ENABLED
        and bool(GEMINI_API_KEY)
        and not GEMINI_API_KEY.startswith("PUT_YOUR")
    )

SYSTEM_CONTEXT = (
    "You are the assistant for the AI Smart Village Platform, a rural-services web app "
    "with six tabs: Crop Recommendation, Telemedicine, Government Schemes, Water Management, "
    "Disaster Alerts, and Employment. Answer the user's question briefly and, where useful, "
    "tell them which tab to use for the actual tool. Never give a medical diagnosis - always "
    "recommend seeing a doctor for health questions. Keep answers short and simple, rural "
    "users may have limited digital literacy."
)


def _call_gemini(prompt_text):
    """
    Sends one prompt to Gemini and returns the reply text,
    or None if the call failed for any reason.
    Tries google-genai SDK first, then REST API fallback.
    """
    if not is_configured():
        return None

    # Method 1: Google GenAI SDK (preferred & recommended by Google)
    global _genai_client
    if _genai_client is None:
        try:
            from google import genai
            _genai_client = genai.Client(api_key=GEMINI_API_KEY)
        except Exception:
            _genai_client = None

    if _genai_client is not None:
        for model in FALLBACK_MODELS:
            try:
                res = _genai_client.models.generate_content(model=model, contents=prompt_text)
                if res and res.text:
                    return res.text
            except Exception as exc:
                err_str = str(exc)
                if "503" in err_str or "UNAVAILABLE" in err_str or "404" in err_str:
                    continue  # try next fallback model
                print(f"Gemini SDK error ({model}): {err_str[:200]}")
                break

    # Method 2: REST fallback
    headers = {"Content-Type": "application/json", "x-goog-api-key": GEMINI_API_KEY}
    payload = {"contents": [{"parts": [{"text": prompt_text}]}]}

    try:
        response = requests.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL_NAME}:generateContent?key={GEMINI_API_KEY}",
            headers=headers,
            json=payload,
            timeout=10,
        )
        if response.status_code == 200:
            data = response.json()
            return data["candidates"][0]["content"]["parts"][0]["text"]
        else:
            print(f"Gemini REST API error {response.status_code}: {response.text[:200]}")
    except Exception as exc:
        print(f"Gemini request exception: {exc}")

    return None


def ask_gemini(user_message):
    """Used by the floating chat assistant."""
    reply = _call_gemini(SYSTEM_CONTEXT + "\n\nUser question: " + user_message)
    if reply is None:
        return ("Sorry, the assistant isn't available right now.")
    return reply


# Cache rewritten crop reasons so repeat requests for the same district/season
# do not pay for another Gemini call.
_crop_reason_cache = {}
_crop_reason_cache_lock = threading.Lock()


def get_crop_recommendation_reasons(facts, language_code):
    """
    Rewrite the computed crop-recommendation facts as 3-5 short bullet points
    in the user's language. Returns None when Gemini is unavailable or ignores
    the format, so the caller can keep the deterministic reasons.

    Gemini is only allowed to reword facts that were already computed; it must
    never add numbers or claims of its own.
    """
    language_name = LANGUAGE_NAMES.get(language_code, "English")
    cache_key = f"{language_code}:{facts}"

    if not is_configured():
        return None

    with _crop_reason_cache_lock:
        cached = _crop_reason_cache.get(cache_key)
    if cached is not None:
        return cached

    prompt = (
        "Rewrite the following computed crop-recommendation facts as 3-5 short, "
        f"plain-language bullet points in {language_name}. Do not add any facts, "
        "numbers, or claims that are not present. Do not mention profit or "
        "guarantees. Return only the bullet points, each starting with '- '.\n\n"
        + facts
    )

    reply = _call_gemini(prompt)
    if reply is None:
        return None

    # Keep only explicit bullet lines so a preamble is not shown as a reason.
    bullets = []
    for line in reply.splitlines():
        stripped = line.strip()
        if stripped.startswith(("-", "*", "•")):
            cleaned = stripped.lstrip("-*• ").replace("**", "").strip()
            if cleaned:
                bullets.append(cleaned)

    # If the model ignored the bullet format, drop a one-line preamble.
    if not bullets:
        lines = [
            line.strip().replace("**", "")
            for line in reply.splitlines()
            if line.strip()
        ]
        if len(lines) > 1 and lines[0].endswith(":"):
            lines = lines[1:]
        bullets = lines

    result = bullets[:5]
    if len(result) < 3:
        return None

    with _crop_reason_cache_lock:
        # Keep the cache small on a long-running server.
        if len(_crop_reason_cache) > 500:
            _crop_reason_cache.clear()
        _crop_reason_cache[cache_key] = result
    return result


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
