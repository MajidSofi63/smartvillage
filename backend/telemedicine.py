# telemedicine.py
# Simple symptom-checker. This is NOT a medical diagnosis tool - it matches symptoms
# the user types against a local dataset of ~30 common conditions using keyword overlap.
# A real diagnosis always needs a doctor - this only helps someone decide how urgently
# they should seek care and what basic first-aid to do in the meantime.

import json  # to read the medical_data.json file

# Load the medical knowledge base once when the server starts
with open("../data/medical_data.json", "r") as f:
    medical_data = json.load(f)

# This disclaimer is attached to every single response, no matter what condition is found.
DISCLAIMER = ("This is NOT a medical diagnosis - it is only a general guide. "
              "Please consult a doctor or health worker to confirm and treat any condition.")


def find_condition(user_symptoms_text):
    """
    Takes free text like "chest pain and shortness of breath" and returns the
    best matching condition, its advice, whether it's urgent, and a safety disclaimer.
    """

    user_text_lower = user_symptoms_text.lower()  # normalise case once, reuse below

    best_match = None
    best_score = 0

    # Check each condition in our dataset and count how many symptoms overlap
    for entry in medical_data:
        score = 0
        for symptom in entry["symptoms"]:
            if symptom in user_text_lower:  # substring match, works for multi-word symptoms too
                score += 1

        if score > best_score:
            best_score = score
            best_match = entry

    # Nothing matched at all
    if best_match is None:
        return {
            "condition": "Unrecognised symptoms",
            "advice": "Could not match your symptoms confidently. Please describe them differently or consult a doctor directly.",
            "urgent": False,
            "disclaimer": DISCLAIMER,
        }

    return {
        "condition": best_match["condition"],
        "advice": best_match["advice"],
        "urgent": best_match["urgent"],
        "disclaimer": DISCLAIMER,
    }
