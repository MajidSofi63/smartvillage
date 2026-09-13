# crop_model.py
# This file loads the already-trained model (from train_model.py) and
# gives us one simple function, predict_yield(), that main.py can call.
# We don't train anything here - training already happened once in train_model.py.

import pickle  # used to load the saved model files
import pandas as pd  # used to build input data with the same column names the model was trained on

# Load the trained model and encoders from disk (only happens once, when the server starts)
with open("models/crop_model.pkl", "rb") as f:
    model = pickle.load(f)

with open("models/area_encoder.pkl", "rb") as f:
    area_encoder = pickle.load(f)

with open("models/crop_encoder.pkl", "rb") as f:
    crop_encoder = pickle.load(f)


def _match_known_value(user_value, known_classes):
    """
    Matches user input against the model's known area/crop names, ignoring
    case and extra spaces (e.g. "india " or "INDIA" both match "India").
    Returns the correctly-cased value the model expects, or None if no match.
    """
    cleaned = user_value.strip()
    for known in known_classes:
        if known.lower() == cleaned.lower():
            return known
    return None


def predict_yield(area, crop, rainfall, pesticides, temperature):
    """
    Takes in raw values (like "India", "Wheat", 1200.0, 50.0, 25.5)
    and returns the predicted crop yield in hg/ha.
    Year is deliberately not used - see the comment in train_model.py for why.
    """

    # Match the typed text to a known area/crop name regardless of case/spacing,
    # then convert it into the number the model understands
    matched_area = _match_known_value(area, area_encoder.classes_)
    matched_crop = _match_known_value(crop, crop_encoder.classes_)

    if matched_area is None or matched_crop is None:
        # This happens if the area/crop truly isn't in the training data
        return None

    area_num = area_encoder.transform([matched_area])[0]
    crop_num = crop_encoder.transform([matched_crop])[0]

    # Arrange the inputs in the SAME order and with the SAME column names the model was trained on
    # (using a DataFrame instead of a plain list avoids a scikit-learn feature-name warning)
    columns = ["Area_encoded", "Item_encoded", "average_rain_fall_mm_per_year", "pesticides_tonnes", "avg_temp"]
    input_data = pd.DataFrame([[area_num, crop_num, rainfall, pesticides, temperature]], columns=columns)

    # Ask the model to predict the yield
    predicted_yield = model.predict(input_data)[0]

    return round(predicted_yield, 2)


def get_available_areas():
    """Returns the list of countries/areas the model knows about (for the dropdown in the UI)."""
    return sorted(area_encoder.classes_.tolist())


def get_available_crops():
    """Returns the list of crops the model knows about (for the dropdown in the UI)."""
    return sorted(crop_encoder.classes_.tolist())
