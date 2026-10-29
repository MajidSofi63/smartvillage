# crop_model.py
# Loads the district-level crop recommendation models (Random Forest, XGBoost,
# and HistGradientBoosting) plus their weighted ensemble and label encoders.
#
# The artefacts in models/crop_recommendation/ were trained with scikit-learn
# 1.5.2 and xgboost 2.1.2 - see backend/requirements.txt. Loading them with a
# newer scikit-learn can fail for the HistGradientBoosting model, so keep those
# versions pinned.
#
# Nothing is trained here. Run backend/load_crop_data.py once to fill the
# districts / crop_stats tables, and run the original pipeline if you ever need
# to retrain the model files.

import json
from pathlib import Path

import joblib
import numpy as np

# All model artefacts live in one folder, next to this file.
MODELS_DIR = Path(__file__).resolve().parent / "models" / "crop_recommendation"


class CropModelService:
    """Load and use the trained yield models and their weighted ensemble."""

    def __init__(self, models_dir=MODELS_DIR):
        self.models_dir = Path(models_dir)
        self.models = {}
        self.encoders = {}
        self.weights = {}
        self.feature_info = {}
        self.metrics = {}
        self.error = None
        self._info_cache = None
        # Loading is guarded so a missing/broken artefact cannot stop the rest of
        # the platform from starting. is_ready() reports the state to the routes.
        try:
            self.load_models()
        except Exception as exc:
            self.error = str(exc)
            print(f"[WARNING] Crop recommendation models failed to load: {exc}")

    def load_models(self):
        """Load the three estimators, encoders, weights, and metadata."""
        self.models["RandomForest"] = joblib.load(
            self.models_dir / "randomforest_model.pkl"
        )
        self.models["XGBoost"] = joblib.load(
            self.models_dir / "xgboost_model.pkl"
        )
        self.models["HistGradientBoosting"] = joblib.load(
            self.models_dir / "histgradientboosting_model.pkl"
        )
        self.encoders["district"] = joblib.load(self.models_dir / "le_district.pkl")
        self.encoders["season"] = joblib.load(self.models_dir / "le_season.pkl")
        self.encoders["crop"] = joblib.load(self.models_dir / "le_crop.pkl")
        self.weights = joblib.load(self.models_dir / "ensemble_weights.pkl")

        with open(self.models_dir / "feature_info.json", "r", encoding="utf-8") as handle:
            self.feature_info = json.load(handle)
        with open(self.models_dir / "metrics.json", "r", encoding="utf-8") as handle:
            self.metrics = json.load(handle)

        # One-row inference must not spawn parallel worker processes.
        for model in self.models.values():
            if hasattr(model, "set_params") and "n_jobs" in model.get_params():
                model.set_params(n_jobs=1)

        # Cache the encoder class sets instead of rebuilding them per request.
        self.class_sets = {
            name: set(encoder.classes_) for name, encoder in self.encoders.items()
        }
        print("[OK] Crop recommendation models loaded")

    def is_ready(self):
        """True when every model and encoder loaded successfully."""
        return self.error is None and bool(self.models) and bool(self.encoders)

    def _encode(self, encoder_name, value):
        """Encode one category, returning None when the value is unseen."""
        encoder = self.encoders[encoder_name]
        if value not in self.class_sets[encoder_name]:
            return None
        return int(encoder.transform([value])[0])

    def predict_many(self, district_key, season, crops, temp_mean, rain_total):
        """
        Predict yield (t/ha) for several crops in ONE batched model call.

        Batching all candidate crops avoids the fixed per-call overhead that
        tree models pay, cutting a request from seconds to milliseconds.
        """
        if not self.is_ready():
            return {}

        district_enc = self._encode("district", district_key)
        season_enc = self._encode("season", season)
        if district_enc is None or season_enc is None:
            return {}

        valid_crops = []
        rows = []
        for crop in crops:
            crop_enc = self._encode("crop", crop)
            if crop_enc is None:
                continue
            valid_crops.append(crop)
            # Training feature order:
            # district_enc, season_enc, crop_enc, temp_mean, rain_total.
            rows.append(
                [
                    district_enc,
                    season_enc,
                    crop_enc,
                    float(temp_mean),
                    float(rain_total),
                ]
            )

        if not rows:
            return {}

        features = np.asarray(rows, dtype=float)
        per_model = {}
        for name, model in self.models.items():
            # Predict in log space, then convert back to t/ha.
            log_predictions = model.predict(features)
            per_model[name] = np.clip(np.expm1(log_predictions), 0.0, None)

        results = {}
        for index, crop in enumerate(valid_crops):
            values = {
                name: float(predictions[index])
                for name, predictions in per_model.items()
            }
            # Combine with the validation-derived weights.
            ensemble = sum(
                float(self.weights.get(name, 0.0)) * values[name]
                for name in self.models
            )
            values["Ensemble"] = float(max(ensemble, 0.0))
            results[crop] = values
        return results

    def get_model_info(self):
        """Return test metrics, weights, validation MAEs, and test years."""
        if self._info_cache is not None:
            return self._info_cache
        self._info_cache = {
            "metrics": self.metrics,
            "weights": self.weights,
            "val_maes": self.feature_info.get("val_maes", {}),
            "test_years": self.feature_info.get("test_years", []),
        }
        return self._info_cache


# One shared instance, loaded once when the server starts.
model_service = CropModelService()
