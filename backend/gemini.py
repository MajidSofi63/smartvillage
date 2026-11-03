# gemini.py
# Calls Google's Gemini API for two things:
#   1. The floating chat assistant (ask_gemini)
#   2. Enhancing telemedicine advice (get_telemedicine_advice)
#
# NOTE ON THE MODEL NAME: Google deprecates these fast. The model is read from
# GEMINI_MODEL in .env (default: gemini-3.6-flash). If it stops working, check
# https://ai.google.dev/gemini-api/docs/models for a current name and update
# .env - no code change is needed.
import threading
import time
import requests
from config import GEMINI_API_KEY, GEMINI_ENABLED, GEMINI_MODEL

MODEL_NAME = GEMINI_MODEL
FALLBACK_MODELS = [MODEL_NAME, "gemini-3.5-flash-lite", "gemini-3.6-flash", "gemini-3.5-flash"]
GEMINI_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL_NAME}:generateContent"

# Initialize google-genai client if installed
def _make_genai_client():
    """Create the SDK client with a hard timeout and no retries.

    Without this a bad key or an unreachable model can block a recommendation
    request for minutes, because the SDK retries internally by default.
    """
    from google import genai
    from google.genai import types

    return genai.Client(
        api_key=GEMINI_API_KEY,
        http_options=types.HttpOptions(
            timeout=10000,
            retry_options=types.HttpRetryOptions(attempts=1),
        ),
    )


_genai_client = None
try:
    import warnings
    warnings.filterwarnings("ignore", category=UserWarning, module="google.genai")
    if GEMINI_API_KEY and not GEMINI_API_KEY.startswith("PUT_YOUR"):
        _genai_client = _make_genai_client()
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
    "with five tabs: Crop Recommendation, Telemedicine, Government Schemes, "
    "Disaster Alerts, and Employment. Answer the user's question briefly and, where useful, "
    "tell them which tab to use for the actual tool. Never give a medical diagnosis - always "
    "recommend seeing a doctor for health questions. Keep answers short and simple, rural "
    "users may have limited digital literacy."
)


def _call_gemini(prompt_text, models=None, rest_fallback=True):
    """
    Sends one prompt to Gemini and returns the reply text,
    or None if the call failed for any reason.
    Tries google-genai SDK first, then REST API fallback.
    `models` optionally limits which model names are tried, and
    `rest_fallback=False` skips the extra REST attempt.
    """
    if not is_configured():
        return None

    # Method 1: Google GenAI SDK (preferred & recommended by Google)
    global _genai_client
    if _genai_client is None:
        try:
            _genai_client = _make_genai_client()
        except Exception:
            _genai_client = None

    if _genai_client is not None:
        for model in (models or FALLBACK_MODELS):
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
    if not rest_fallback:
        return None

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


# Cache crop summaries so repeat requests for the same district/season do not
# pay for another Gemini call.
_crop_summary_cache = {}
_crop_summary_cache_lock = threading.Lock()

# After a failed call, skip Gemini for a short while so every request does not
# pay the timeout again. Reset automatically once the window passes.
_crop_summary_failure_until = 0.0


def get_crop_recommendation_summary(district, state, season, recommendations):
    """
    Turn the computed crop ranking into a short, plain-language explanation of
    why the top crops suit this district and season.

    Returns None when Gemini is unavailable, so the caller can fall back to the
    deterministic reasons already built by crop_recommendation.py. Gemini may
    only reword facts that were computed - it must never add numbers or claims
    of its own.
    """
    if not recommendations:
        return None

    facts = [f"District: {district}, {state}", f"Season: {season}"]
    for index, rec in enumerate(recommendations[:5], start=1):
        facts.append(
            f"{index}. {rec['crop']}: suitability {rec['suitability']}% of its "
            f"historical median, expected yield {rec['expected_yield']} t/ha, "
            f"historical median {rec['historical_median']} t/ha"
        )
    facts_text = "\n".join(facts)
    cache_key = facts_text

    if not is_configured():
        return None

    global _crop_summary_failure_until

    with _crop_summary_cache_lock:
        cached = _crop_summary_cache.get(cache_key)
    if cached is not None:
        return cached

    if time.monotonic() < _crop_summary_failure_until:
        return None

    prompt = (
        "Write a short, plain-language explanation for a rural farmer of why "
        "the following crops are the best and most suitable choices. Use 2-3 "
        "sentences, mention the top crop first, and explain that suitability "
        "compares the predicted yield with each crop's own history. Do not add "
        "any facts, numbers, or claims that are not present. Do not mention "
        "profit or guarantees. Return only the explanation, no heading.\n\n"
        + facts_text
    )

    # Hard wall-clock cap: a slow or misconfigured Gemini must never delay the
    # crop recommendation itself. The daemon thread is abandoned on timeout and
    # the caller falls back to the deterministic reasons.
    reply_holder = {}
    def _fetch():
        reply_holder["reply"] = _call_gemini(
            prompt, models=[MODEL_NAME], rest_fallback=False
        )

    worker = threading.Thread(target=_fetch, daemon=True)
    worker.start()
    worker.join(timeout=5)

    reply = reply_holder.get("reply")
    if reply is None:
        _crop_summary_failure_until = time.monotonic() + 60
        return None

    summary = " ".join(
        line.strip().replace("**", "") for line in reply.splitlines() if line.strip()
    )
    if len(summary) < 20:
        return None

    with _crop_summary_cache_lock:
        # Keep the cache small on a long-running server.
        if len(_crop_summary_cache) > 500:
            _crop_summary_cache.clear()
        _crop_summary_cache[cache_key] = summary
    return summary


def get_telemedicine_advice(symptoms, local_condition, local_advice, urgent):
    """
    Takes the LOCAL keyword-matched result (which we trust for the urgent/not-urgent
    safety flag) and asks Gemini to turn it into a clearer, more complete explanation
    in English. If Gemini is unavailable, we fall back to the local English advice so
    the feature still works offline.
    """
    prompt = (
        f"A rural telemedicine app matched these symptoms: \"{symptoms}\" "
        f"to the likely condition \"{local_condition}\" with this basic advice: \"{local_advice}\". "
        f"Urgency level: {'URGENT - needs immediate medical care' if urgent else 'not urgent'}. "
        f"Rewrite this as a clear, simple, well-explained response for a rural user with limited "
        f"medical knowledge, in English. Include: what the condition likely is, what to do "
        f"right now, and a clear reminder to see a real doctor - this is not a diagnosis. "
        f"Keep it under 120 words. Do not use complex medical jargon."
    )

    reply = _call_gemini(prompt)
    if reply is None:
        # Fall back to the plain local advice (English) with a note explaining why
        return local_advice + " (AI enhancement unavailable right now - showing basic offline guidance.)"
    return reply
