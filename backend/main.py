# main.py
# This is the entry point of our backend server.
# Run it with: uvicorn main:app --reload
# Then open http://127.0.0.1:8000/docs to see and test the API directly in the browser.

from fastapi import FastAPI, Header, HTTPException, Depends  # web framework + auth helpers
from fastapi.middleware.cors import CORSMiddleware  # allows cross-origin calls (harmless to keep even when same-origin)
from fastapi.staticfiles import StaticFiles  # lets this same app serve the frontend files too
from fastapi.responses import FileResponse  # lets us hand back index.html directly for the hidden /admin route
from pydantic import BaseModel, EmailStr, field_validator  # request validation, including real email format checking
import os

# our own modules, one per platform feature
import crop_model
import crop_db
import crop_recommendation
import crop_weather
import telemedicine
import schemes
import water
import disaster
import employment
import gemini
import database
import auth
import analytics
from config import ADMIN_PASSWORD

from contextlib import asynccontextmanager


@asynccontextmanager
async def lifespan(app: FastAPI):
    # creates every table the first time the server ever runs - safe to call every time
    database.init_db()
    # crop recommendation tables live alongside the platform tables
    try:
        crop_db.init_crop_tables()
    except Exception as exc:
        print(f"[WARNING] Could not create crop tables: {exc}")
    yield


app = FastAPI(title="AI Smart Village Platform", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------- Auth dependencies ----------

def get_current_worker(x_auth_token: str = Header(...)):
    """
    Reads the "X-Auth-Token" header (a Supabase access token), verifies it, and
    returns the worker's id. Any route that takes this as a parameter is
    automatically protected - FastAPI rejects the request before the route body
    even runs if the token is missing, invalid, or belongs to a different role.
    """
    user = auth.get_user_from_token(x_auth_token)
    if user is None or user.get("user_metadata", {}).get("role") != "worker":
        raise HTTPException(status_code=401, detail="Please log in to do this.")
    return user["id"]


def require_admin(x_admin_password: str = Header(...)):
    """
    Simple shared-password check for admin routes - no account/token system needed
    since there's only ever one admin. The password itself is the credential on
    every request (sent over HTTPS, so it's not exposed in transit).
    """
    if x_admin_password != ADMIN_PASSWORD:
        raise HTTPException(status_code=401, detail="Incorrect admin password.")


# ---------- Request data shapes (what the frontend must send us) ----------

class RecommendCropRequest(BaseModel):
    district_id: int
    season: str
    language: str = "en"


class SymptomRequest(BaseModel):
    symptoms: str
    language: str = "en"


class SchemeRequest(BaseModel):
    age: int
    annual_income: float
    owns_land: bool
    category: str


class WaterRequest(BaseModel):
    city: str


class WeatherRequest(BaseModel):
    city: str


class WorkerRegisterRequest(BaseModel):
    name: str
    email: EmailStr  # validates real email format, not just any string
    phone: str       # shown publicly in the feed so people can call directly
    location: str
    skills: str      # comma-separated, e.g. "farming, driving"
    bio: str = ""    # short intro, like a social post caption
    password: str

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v):
        cleaned = v.replace(" ", "").replace("-", "")
        if not cleaned.replace("+", "", 1).isdigit() or len(cleaned) < 7:
            raise ValueError("Phone number looks invalid - please include enough digits.")
        return v

    @field_validator("password")
    @classmethod
    def validate_password(cls, v):
        if len(v) < 6:
            raise ValueError("Password must be at least 6 characters.")
        return v


class WorkerUpdateRequest(BaseModel):
    name: str
    phone: str
    location: str
    skills: str
    bio: str = ""


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class ForgotPasswordRequest(BaseModel):
    email: EmailStr
    redirect_to: str  # this site's own address - where the emailed link sends them back to


class ResetPasswordRequest(BaseModel):
    token: str        # the short-lived token Supabase put in the emailed link
    new_password: str

    @field_validator("new_password")
    @classmethod
    def validate_new_password(cls, v):
        if len(v) < 6:
            raise ValueError("Password must be at least 6 characters.")
        return v


class ChatRequest(BaseModel):
    message: str


# ---------- Routes ----------

# --- Crop Recommendation (district + season -> ranked crops from ML ensemble) ---

@app.get("/api/districts")
def get_crop_districts(q: str = ""):
    """Return up to 15 districts matching the search text."""
    try:
        districts = crop_db.search_districts(q.strip() if q else "")
        return {"districts": districts, "count": len(districts)}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Crop database error: {exc}")


@app.get("/api/seasons")
def get_crop_seasons():
    """Return the planting seasons present in the loaded crop data."""
    try:
        return {"seasons": crop_db.get_seasons()}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Crop database error: {exc}")


@app.post("/api/recommend")
def recommend_crops(request: RecommendCropRequest):
    """Recommend and rank crops for one Indian district and planting season."""
    # Refuse to guess before the trained artefacts have loaded.
    if not crop_model.model_service.is_ready():
        raise HTTPException(
            status_code=500,
            detail=(
                "Crop recommendation models are not loaded. Check "
                "backend/models/crop_recommendation/ and the pinned package versions."
            ),
        )

    # Load the district and the dataset's latest year.
    try:
        district = crop_db.get_district(request.district_id)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Crop database error: {exc}")

    if district is None:
        raise HTTPException(status_code=404, detail="District not found")

    # Every historical row for this district-season in one query.
    try:
        history_rows = crop_db.get_history(request.district_id, request.season)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Crop database error: {exc}")

    if not history_rows:
        raise HTTPException(
            status_code=404,
            detail="No historical crop data for this district and season",
        )

    # Live weather is display-only; a failure never blocks the recommendation.
    live_weather = crop_weather.weather_service.get_live_weather_and_forecast(
        district["lat"], district["lon"]
    )

    try:
        payload = crop_recommendation.build_recommendations(
            district,
            request.season,
            history_rows,
            crop_model.model_service,
            live_weather,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    # Optionally rewrite ONLY the top crop's reasons, once per request.
    top_recommendations = payload["recommendations"]
    if top_recommendations and gemini.is_configured():
        rewritten = gemini.get_crop_recommendation_reasons(
            "\n".join(top_recommendations[0]["reasons"]),
            request.language,
        )
        if rewritten:
            top_recommendations[0]["reasons"] = rewritten

    payload["model_info"] = crop_model.model_service.get_model_info()
    analytics.log_event("crop_prediction")
    return payload


# --- Health check (useful on Render) ---

@app.get("/health")
def health():
    """Report model and database readiness without exposing any secrets."""
    result = {
        "status": "ok",
        "models_ready": crop_model.model_service.is_ready(),
        "models_error": crop_model.model_service.error,
    }
    try:
        conn = database.get_connection()
        try:
            districts = conn.execute("SELECT COUNT(*) AS count FROM districts").fetchone()
            stats = conn.execute("SELECT COUNT(*) AS count FROM crop_stats").fetchone()
            result["database"] = "ok"
            result["districts"] = districts["count"]
            result["crop_stats"] = stats["count"]
        finally:
            conn.close()
    except Exception as exc:
        result["status"] = "degraded"
        result["database"] = "error"
        result["database_error"] = str(exc)[:300]
    return result


# --- Telemedicine ---

@app.post("/telemedicine")
def check_symptoms(request: SymptomRequest):
    local_result = telemedicine.find_condition(request.symptoms)
    enhanced_advice = gemini.get_telemedicine_advice(
        symptoms=request.symptoms, local_condition=local_result["condition"],
        local_advice=local_result["advice"], urgent=local_result["urgent"],
        language_code=request.language,
    )
    analytics.log_event("telemedicine_query")
    return {
        "success": True,
        "condition": local_result["condition"],
        "advice": enhanced_advice,
        "urgent": local_result["urgent"],
    }


# --- Government Schemes ---

@app.post("/schemes")
def get_schemes(request: SchemeRequest):
    result = schemes.find_eligible_schemes(request.age, request.annual_income, request.owns_land, request.category)
    analytics.log_event("scheme_check")
    return {"success": True, "eligible_schemes": result}


# --- Smart Water Management ---

@app.post("/water")
def water_status(request: WaterRequest):
    result = water.get_water_status(request.city)
    analytics.log_event("water_check")
    return result


# --- Disaster Alerts ---

@app.post("/disaster")
def disaster_alert(request: WeatherRequest):
    result = disaster.get_weather_alert(request.city)
    analytics.log_event("disaster_check")
    return result


# --- Employment: public feed (no login needed to browse) ---

@app.get("/workers")
def get_public_feed():
    return {"success": True, "workers": employment.list_public_feed()}


@app.get("/employment/stats")
def employment_public_stats():
    return {"success": True, **employment.get_public_stats()}


# --- Employment: worker accounts ---

@app.post("/auth/register-worker")
def register_worker(request: WorkerRegisterRequest):
    result = auth.sign_up(request.email, request.password, "worker",
                           {"name": request.name, "location": request.location, "skills": request.skills})
    if not result["success"]:
        return {"success": False, "message": result["message"]}

    employment.save_worker_profile(result["id"], request.name, request.email, request.phone,
                                    request.location, request.skills, request.bio)
    return {"success": True, "token": result["token"], "name": request.name}


@app.post("/auth/login-worker")
def login_worker(request: LoginRequest):
    result = auth.log_in(request.email, request.password)
    if not result["success"]:
        return {"success": False, "message": result["message"]}
    if result["metadata"].get("role") != "worker":
        return {"success": False, "message": "This account isn't registered as a worker."}
    return {"success": True, "token": result["token"], "name": result["metadata"].get("name", "")}


# --- Employment: forgotten password ---

@app.post("/auth/forgot-password")
def forgot_password(request: ForgotPasswordRequest):
    result = auth.request_password_reset(request.email, request.redirect_to)
    if not result["success"]:
        return {"success": False, "message": result["message"]}
    # Same wording whether or not that email has an account, so this can't be used
    # to find out who is registered.
    return {"success": True, "message": "If that email is registered, a reset link is on its way."}


@app.post("/auth/reset-password")
def reset_password(request: ResetPasswordRequest):
    result = auth.update_password(request.token, request.new_password)
    if not result["success"]:
        return {"success": False, "message": result["message"]}
    return {"success": True, "message": "Password updated."}


@app.get("/worker/profile")
def get_my_profile(worker_id: str = Depends(get_current_worker)):
    profile = employment.get_worker_profile(worker_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="Profile not found.")
    return {"success": True, "profile": profile}


@app.put("/worker/profile")
def update_my_profile(request: WorkerUpdateRequest, worker_id: str = Depends(get_current_worker)):
    employment.update_worker_profile(worker_id, request.name, request.phone, request.location, request.skills, request.bio)
    return {"success": True, "message": "Profile updated."}


@app.delete("/worker/profile")
def delete_my_profile(worker_id: str = Depends(get_current_worker)):
    employment.delete_worker_profile(worker_id)
    return {"success": True, "message": "Profile removed from the feed."}


# --- Admin panel: full visibility into every registered worker + platform activity ---
# Deliberately NOT in the main nav bar - only reachable by going directly to
# /admin, so casual visitors never see it exists. script.js checks the URL path
# on load and shows the admin view only when it matches.

@app.get("/admin")
@app.get("/admin/")
def serve_admin_page():
    # hands back the same index.html the rest of the site uses - script.js then
    # notices the URL is /admin and switches straight to the admin view
    return FileResponse(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "frontend", "index.html"))


@app.get("/admin/verify")
def admin_verify(_: None = Depends(require_admin)):
    return {"success": True}


@app.get("/admin/workers")
def admin_list_workers(_: None = Depends(require_admin)):
    return {"success": True, "workers": employment.list_all_workers()}


@app.delete("/admin/workers/{worker_id}")
def admin_remove_worker(worker_id: str, _: None = Depends(require_admin)):
    employment.delete_worker_profile(worker_id)
    return {"success": True, "message": "Worker profile removed."}


@app.get("/admin/activity")
def admin_get_activity(_: None = Depends(require_admin)):
    # real platform usage counts - the piece that was missing before: previously
    # the admin panel could only show WHO registered, never whether the platform
    # was actually being used
    return {"success": True, "activity": analytics.get_usage_counts()}


# --- Conversational Assistant (Gemini) ---

@app.post("/chat")
def chat_with_assistant(request: ChatRequest):
    reply = gemini.ask_gemini(request.message)
    analytics.log_event("chat_message")
    return {"success": True, "reply": reply}


# ---------- Serve the frontend ----------
# This MUST be the last thing registered - it's mounted at "/" and would otherwise
# swallow every API route above it if it came first.

FRONTEND_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "frontend")
app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
