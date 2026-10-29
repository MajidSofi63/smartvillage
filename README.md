# AI Smart Village Platform

A rural-services web app with six tabs: Crop Recommendation, Telemedicine,
Government Schemes, Water Management, Disaster Alerts, and Employment.

This repository was upgraded from a single-field crop-yield predictor to a
district-level crop recommendation system for India. The crop tab now ranks
crops for a district and planting season using three trained ML models and a
weighted ensemble.

## Crop recommendation: how it works

1. The user picks an Indian district and a planting season (Kharif, Rabi, etc.).
2. `POST /api/recommend` loads every historical `district + season + crop` row
   from PostgreSQL.
3. Three models (Random Forest, XGBoost, HistGradientBoosting) predict yield in
   one batched call. Their weighted ensemble (`ensemble_weights.pkl`) is the
   headline prediction.
4. Crops are ranked by **suitability**:
   `predicted ensemble yield / the crop's own historical median yield`.
   Ranking by raw yield across crops would always favour high-yield crops such
   as sugarcane, so each crop is compared with its own history instead.
5. Live weather and a 7-day forecast come from Open-Meteo and are shown for
   context only. The model uses the historical seasonal weather stored in the
   database, so a weather outage never blocks a recommendation.
6. If Gemini is configured, it rewords the **top crop's** reasons in the
   selected language. On any failure the deterministic reasons are kept.

### Data limitations (also shown in the UI)

- Historical data ends in 2011-12. Recommendations describe historical
  suitability, not a forecast.
- District-level averages, not field-level predictions.
- No soil, irrigation, price, or satellite data is used.
- Weather input is a seasonal estimate, not a forecast.
- Suitability is not a profit estimate or a guarantee.

## Setup

### 1. Install dependencies

The model artefacts were trained with specific library versions.
`histgradientboosting_model.pkl` cannot be unpickled by scikit-learn 1.9+, so
keep the pins in `backend/requirements.txt`:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r backend\requirements.txt
```

Pinned versions: `scikit-learn==1.5.2`, `xgboost==2.1.2`, `joblib==1.4.2`,
`numpy==2.1.3`, `pandas==2.2.3`.

### 2. Configure environment variables

```powershell
Copy-Item backend\.env.example backend\.env
```

Fill in `DATABASE_URL` (and any optional keys). See
`backend/.env.example` for the full list.

### 3. Load the crop data (one time)

This creates the `districts` and `crop_stats` tables and loads
`data/crop_data_with_weather.csv` (~17 MB, ~153k rows). It does **not** touch
`worker_profiles` or `usage_events`.

```powershell
python backend\load_crop_data.py
```

Use `--keep` to upsert instead of truncating the two crop tables, or
`--csv <path>` to load a different file.

### 4. Run the app

```powershell
cd backend
uvicorn main:app --reload
```

Open <http://127.0.0.1:8000>. The backend also serves the frontend from
`frontend/`. API docs: <http://127.0.0.1:8000/docs>.

The server starts even if the crop tables are empty or the models fail to load;
the crop tab returns a clear error until setup is complete.

## API

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/api/districts?q=` | Search districts by name or state (max 15) |
| `GET` | `/api/seasons` | Seasons present in the loaded data |
| `POST` | `/api/recommend` | Body: `{ "district_id": 1, "season": "Kharif", "language": "en" }` |

`POST /api/recommend` returns the top five crops with expected yield,
suitability, per-model predictions, model agreement, historical median and
range, years of evidence, reasons, the weather used, and data limitations.
Live weather is included when Open-Meteo is reachable.

## Project layout

```
backend/
  main.py                    FastAPI app and routes
  crop_model.py              Loads the 3 models + ensemble weights
  crop_recommendation.py     Pure ranking logic
  crop_db.py                 districts / crop_stats access
  crop_weather.py            Open-Meteo live weather (display only)
  load_crop_data.py          One-time CSV -> PostgreSQL loader
  gemini.py                  Chat, telemedicine, and crop reason rewriting
  models/crop_recommendation/  Trained artefacts (do not retrain in place)
data/crop_data_with_weather.csv  Source data for the DB loader
frontend/                    HTML, CSS, JS, translations, service worker
```

## Notes

- The old single-field crop model (`backend/train_model.py`, `crop_data.csv`,
  and the old `.pkl` files) is no longer used by the application.
- To retrain the district models, use the original training pipeline that
  produced `backend/models/crop_recommendation/`, then update the artefacts and
  rerun `load_crop_data.py` if the underlying data changed.
