# crop_recommendation.py
# Pure recommendation logic: turns historical rows plus model predictions into
# a ranked crop list. Keeping it separate from the FastAPI route makes the
# ranking easy to test with a CSV and no database.

import numpy as np


def make_district_key(state, district):
    """Build the location key used during training (state | district)."""
    # The separator must match the training script exactly.
    return f"{state} | {district}"


def build_recommendations(district, season, history_rows, model_service, live_weather):
    """
    Rank crops for one district and season.

    The headline number is the weighted ensemble yield. Ranking uses
    suitability = predicted yield / that crop's own historical median, so a
    naturally low-yield crop is not punished for being low-yield.
    """
    district_name = district["district"]
    state_name = district["state"]
    district_key = make_district_key(state_name, district_name)
    max_year = district.get("max_year")

    # Group yields, distinct years, and weather by crop/year in one pass.
    history_by_crop = {}
    years_by_crop = {}
    temp_by_year = {}
    rain_by_year = {}
    for row in history_rows:
        crop_name = row["crop"]
        year = int(row["year"])
        history_by_crop.setdefault(crop_name, []).append(float(row["yield_t_ha"]))
        years_by_crop.setdefault(crop_name, set()).add(year)
        temp_by_year.setdefault(year, []).append(float(row["temp_mean"]))
        rain_by_year.setdefault(year, []).append(float(row["rain_total"]))

    # Model-input weather comes from the 5 most recent years available.
    # Average within a year first so duplicated per-crop rows cannot weight a
    # year more heavily than it should.
    years_used = sorted(temp_by_year, reverse=True)[:5]
    model_temp = float(np.mean([np.mean(temp_by_year[year]) for year in years_used]))
    model_rain = float(np.mean([np.mean(rain_by_year[year]) for year in years_used]))

    if len(years_used) == 5:
        weather_note = (
            "Seasonal estimate: average of the 5 most recent years available "
            "for this district and season, not a forecast"
        )
    else:
        weather_note = (
            f"Seasonal estimate: average of {len(years_used)} available year(s) "
            "for this district and season, not a forecast"
        )

    # Candidate crops need at least 3 DISTINCT years of history.
    candidates = [
        {"crop": crop_name, "year_count": len(years_by_crop[crop_name])}
        for crop_name in sorted(history_by_crop)
        if len(years_by_crop[crop_name]) >= 3
    ]
    if not candidates:
        raise ValueError(
            "Not enough historical data for this district and season: at least "
            "3 years of records per crop are required."
        )

    # Predict every candidate crop in one batched call per model.
    batch_predictions = model_service.predict_many(
        district_key,
        season,
        [candidate["crop"] for candidate in candidates],
        model_temp,
        model_rain,
    )

    recommendations = []
    for candidate in candidates:
        crop_name = candidate["crop"]
        values = batch_predictions.get(crop_name)
        if values is None:
            continue

        hist_yields = history_by_crop.get(crop_name, [])
        if not hist_yields:
            continue

        hist_median = float(np.median(hist_yields))
        hist_p25 = float(np.percentile(hist_yields, 25))
        hist_p75 = float(np.percentile(hist_yields, 75))
        num_years = len(years_by_crop.get(crop_name, hist_yields))

        ensemble_pred = float(values.get("Ensemble", 0.0))
        suitability = (
            (ensemble_pred / hist_median * 100.0) if hist_median > 0 else 0.0
        )

        # Agreement is the coefficient of variation across the three models.
        model_values = [
            float(values.get("RandomForest", 0.0)),
            float(values.get("XGBoost", 0.0)),
            float(values.get("HistGradientBoosting", 0.0)),
        ]
        mean_value = float(np.mean(model_values))
        std_value = float(np.std(model_values))
        cv = (std_value / mean_value * 100.0) if mean_value > 0 else 999.0
        if cv < 10:
            agreement = "High"
        elif cv < 20:
            agreement = "Medium"
        else:
            agreement = "Low"

        reasons = [
            f"Recorded in {season} season in {district_name}, {state_name} "
            f"for {num_years} distinct years",
            f"Seasonal temperature estimate: {model_temp:.1f} C "
            f"(average of {len(years_used)} years)",
            f"Seasonal rainfall estimate: {model_rain:.1f} mm "
            f"(average of {len(years_used)} years)",
            f"Predicted yield {ensemble_pred:.2f} t/ha versus this crop's "
            f"historical median of {hist_median:.2f} t/ha",
            f"Model agreement: {agreement} "
            f"(coefficient of variation {cv:.1f}%)",
        ]

        recommendations.append(
            {
                "crop": crop_name,
                "expected_yield": round(ensemble_pred, 3),
                "suitability": round(float(suitability), 2),
                "models": {
                    "RandomForest": round(
                        float(values.get("RandomForest", 0.0)), 3
                    ),
                    "XGBoost": round(float(values.get("XGBoost", 0.0)), 3),
                    "HistGradientBoosting": round(
                        float(values.get("HistGradientBoosting", 0.0)), 3
                    ),
                    "Ensemble": round(ensemble_pred, 3),
                },
                "agreement": agreement,
                "historical_median": round(hist_median, 3),
                "historical_range": {
                    "p25": round(hist_p25, 3),
                    "p75": round(hist_p75, 3),
                },
                "years_of_evidence": num_years,
                "reasons": reasons,
            }
        )

    # Rank by suitability, highest first.
    recommendations.sort(key=lambda item: item["suitability"], reverse=True)
    top_five = recommendations[:5]

    limitations = [
        f"Historical data ends at {max_year}",
        "District-level averages, not field-level predictions",
        "No soil, irrigation, price, or satellite data is used",
        "Weather input is a seasonal estimate, not a forecast",
        "Suitability is based on history; it is not a profit estimate or a guarantee",
    ]
    if any(item["agreement"] == "Low" for item in top_five):
        limitations.append(
            "Low-confidence warning: models disagree on at least one top crop"
        )
    if any(item["years_of_evidence"] < 5 for item in top_five):
        limitations.append(
            "Low-confidence warning: fewer than 5 years of history "
            "for at least one top crop"
        )

    return {
        "district": {
            "id": district["id"],
            "name": district_name,
            "state": state_name,
        },
        "season": season,
        "weather_used": {
            "model_input": {
                "temperature": round(model_temp, 2),
                "rainfall": round(model_rain, 2),
                "years_used": years_used,
                "note": weather_note,
            },
            "live_conditions": live_weather.get("current"),
            "forecast_7day": live_weather.get("forecast", []),
        },
        "recommendations": top_five,
        "limitations": limitations,
    }
