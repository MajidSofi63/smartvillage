# main.py
# This is the entry point of our backend server.
# Run it with: uvicorn main:app --reload
# Then open http://127.0.0.1:8000/docs to see and test the API directly in the browser.

from fastapi import FastAPI, Header, HTTPException, Depends  # web framework + auth helpers
from fastapi.middleware.cors import CORSMiddleware  # allows cross-origin calls (harmless to keep even when same-origin)
from fastapi.staticfiles import StaticFiles  # lets this same app serve the frontend files too
from pydantic import BaseModel  # used to define what data the API expects to receive
import os

# our own modules, one per platform feature
import crop_model
import telemedicine
import schemes
import water
import disaster
import employment
import gemini
import database
import auth
from config import ADMIN_PASSWORD

app = FastAPI(title="AI Smart Village Platform")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup():
    # creates every table the first time the server ever runs - safe to call every time
    database.init_db()


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

class CropRequest(BaseModel):
    area: str
    crop: str
    rainfall: float
    pesticides: float
    temperature: float
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
    email: str       # used to log in
    phone: str       # shown publicly in the feed so people can call directly
    location: str
    skills: str      # comma-separated, e.g. "farming, driving"
    bio: str = ""    # short intro, like a social post caption
    password: str


class WorkerUpdateRequest(BaseModel):
    name: str
    phone: str
    location: str
    skills: str
    bio: str = ""


class LoginRequest(BaseModel):
    email: str
    password: str


class ChatRequest(BaseModel):
    message: str


# ---------- Routes ----------

# --- Crop Prediction (number from the ML model, explanation from Gemini) ---

@app.get("/options")
def get_options():
    return {
        "areas": crop_model.get_available_areas(),
        "crops": crop_model.get_available_crops(),
    }


@app.post("/predict-crop")
def predict_crop(request: CropRequest):
    predicted = crop_model.predict_yield(
        area=request.area,
        crop=request.crop,
        rainfall=request.rainfall,
        pesticides=request.pesticides,
        temperature=request.temperature,
    )
    if predicted is None:
        return {"success": False, "message": "Area or crop not recognised by the model."}

    explanation = gemini.get_crop_explanation(
        area=request.area, crop=request.crop, rainfall=request.rainfall,
        pesticides=request.pesticides, temperature=request.temperature,
        predicted_yield=predicted, language_code=request.language,
    )

    return {"success": True, "predicted_yield_hg_per_ha": predicted, "explanation": explanation}


# --- Telemedicine ---

@app.post("/telemedicine")
def check_symptoms(request: SymptomRequest):
    local_result = telemedicine.find_condition(request.symptoms)
    enhanced_advice = gemini.get_telemedicine_advice(
        symptoms=request.symptoms, local_condition=local_result["condition"],
        local_advice=local_result["advice"], urgent=local_result["urgent"],
        language_code=request.language,
    )
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
    return {"success": True, "eligible_schemes": result}


# --- Smart Water Management ---

@app.post("/water")
def water_status(request: WaterRequest):
    return water.get_water_status(request.city)


# --- Disaster Alerts ---

@app.post("/disaster")
def disaster_alert(request: WeatherRequest):
    return disaster.get_weather_alert(request.city)


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


# --- Admin panel: full visibility into every registered worker ---

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


# --- Conversational Assistant (Gemini) ---

@app.post("/chat")
def chat_with_assistant(request: ChatRequest):
    reply = gemini.ask_gemini(request.message)
    return {"success": True, "reply": reply}


# ---------- Serve the frontend ----------
# This MUST be the last thing registered - it's mounted at "/" and would otherwise
# swallow every API route above it if it came first.

FRONTEND_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "frontend")
app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")