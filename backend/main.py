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
# These read the "X-Auth-Token" header (a Supabase access token) on incoming
# requests and turn it into a verified user id. Any route that takes one of these
# as a parameter is automatically protected - FastAPI rejects the request before
# the route even runs if the token is missing, invalid, or the wrong account type.

def get_current_worker(x_auth_token: str = Header(...)):
    user = auth.get_user_from_token(x_auth_token)
    if user is None or user.get("user_metadata", {}).get("role") != "worker":
        raise HTTPException(status_code=401, detail="Please log in as a worker to do this.")
    return user["id"]


def get_current_employer(x_auth_token: str = Header(...)):
    user = auth.get_user_from_token(x_auth_token)
    if user is None or user.get("user_metadata", {}).get("role") != "employer":
        raise HTTPException(status_code=401, detail="Please log in as an employer to do this.")
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
    phone: str       # used as CONTACT info only, shown to employers - not for login
    location: str
    skills: str      # comma-separated, e.g. "farming, driving"
    password: str


class EmployerRegisterRequest(BaseModel):
    name: str
    email: str
    password: str


class LoginRequest(BaseModel):
    email: str
    password: str


class JobPostRequest(BaseModel):
    title: str
    skills: str  # comma-separated required skills
    location: str
    job_type: str
    contact: str


class ApplicationStatusRequest(BaseModel):
    status: str  # "Contacted" or "Hired"


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

    # the NUMBER above is final and trusted - Gemini only explains/advises around it
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


# --- Smart Water Management (real Open-Meteo data, per searched location) ---

@app.post("/water")
def water_status(request: WaterRequest):
    return water.get_water_status(request.city)


# --- Disaster Alerts ---

@app.post("/disaster")
def disaster_alert(request: WeatherRequest):
    return disaster.get_weather_alert(request.city)


# --- Employment: accounts (Supabase handles the actual login; we mirror each
#     account's profile fields locally right after, for applicant-list queries
#     AND for the admin panel to be able to see everyone) ---

@app.get("/employment/stats")
def employment_public_stats():
    # no login required - just aggregate counts, safe to show anyone
    return {"success": True, **employment.get_public_stats()}


@app.post("/auth/register-worker")
def register_worker(request: WorkerRegisterRequest):
    result = auth.sign_up(request.email, request.password, "worker",
                           {"name": request.name, "location": request.location, "skills": request.skills})
    if not result["success"]:
        return {"success": False, "message": result["message"]}

    employment.save_worker_profile(result["id"], request.name, request.email, request.phone, request.location, request.skills)
    return {"success": True, "token": result["token"], "name": request.name}


@app.post("/auth/login-worker")
def login_worker(request: LoginRequest):
    result = auth.log_in(request.email, request.password)
    if not result["success"]:
        return {"success": False, "message": result["message"]}
    if result["metadata"].get("role") != "worker":
        return {"success": False, "message": "This account isn't registered as a worker."}
    return {"success": True, "token": result["token"], "name": result["metadata"].get("name", "")}


@app.post("/auth/register-employer")
def register_employer(request: EmployerRegisterRequest):
    result = auth.sign_up(request.email, request.password, "employer", {"name": request.name})
    if not result["success"]:
        return {"success": False, "message": result["message"]}

    employment.save_employer_profile(result["id"], request.name, request.email)
    return {"success": True, "token": result["token"], "name": request.name}


@app.post("/auth/login-employer")
def login_employer(request: LoginRequest):
    result = auth.log_in(request.email, request.password)
    if not result["success"]:
        return {"success": False, "message": result["message"]}
    if result["metadata"].get("role") != "employer":
        return {"success": False, "message": "This account isn't registered as an employer."}
    return {"success": True, "token": result["token"], "name": result["metadata"].get("name", "")}


# --- Employment: jobs ---

@app.get("/jobs/for-me")
def get_jobs_for_worker(worker_id: str = Depends(get_current_worker)):
    # sorts jobs by how well they match THIS worker's saved skills
    worker_skills = employment.get_worker_skills(worker_id)
    return {"success": True, "jobs": employment.list_jobs(worker_skills=worker_skills)}


@app.get("/jobs/mine")
def get_my_jobs(employer_id: str = Depends(get_current_employer)):
    return {"success": True, "jobs": employment.list_employer_jobs(employer_id)}


@app.post("/jobs")
def create_job(request: JobPostRequest, employer_id: str = Depends(get_current_employer)):
    employment.post_job(employer_id, request.title, request.skills, request.location, request.job_type, request.contact)
    return {"success": True, "message": "Job posted."}


@app.delete("/jobs/{job_id}")
def remove_job(job_id: int, employer_id: str = Depends(get_current_employer)):
    deleted = employment.delete_job(employer_id, job_id)
    if not deleted:
        raise HTTPException(status_code=403, detail="This job doesn't belong to you.")
    return {"success": True, "message": "Job removed."}


@app.post("/jobs/{job_id}/apply")
def apply_to_job(job_id: int, worker_id: str = Depends(get_current_worker)):
    applied = employment.apply_to_job(worker_id, job_id)
    if not applied:
        return {"success": False, "message": "You've already applied to this job."}
    return {"success": True, "message": "Application submitted!"}


@app.get("/jobs/{job_id}/applicants")
def get_applicants(job_id: int, employer_id: str = Depends(get_current_employer)):
    applicants = employment.list_applicants(employer_id, job_id)
    if applicants is None:
        raise HTTPException(status_code=403, detail="This job doesn't belong to you.")
    return {"success": True, "applicants": applicants}


@app.patch("/applications/{application_id}/status")
def set_application_status(application_id: int, request: ApplicationStatusRequest, employer_id: str = Depends(get_current_employer)):
    updated = employment.update_application_status(employer_id, application_id, request.status)
    if not updated:
        raise HTTPException(status_code=403, detail="This application doesn't belong to one of your job postings.")
    return {"success": True}


@app.get("/worker/applications")
def get_my_applications(worker_id: str = Depends(get_current_worker)):
    return {"success": True, "applications": employment.list_worker_applications(worker_id)}


@app.delete("/worker/applications/{application_id}")
def withdraw_application(application_id: int, worker_id: str = Depends(get_current_worker)):
    withdrawn = employment.withdraw_application(worker_id, application_id)
    if not withdrawn:
        raise HTTPException(status_code=403, detail="This application doesn't belong to you.")
    return {"success": True, "message": "Application withdrawn."}


# --- Admin panel ---
# Every route below requires the admin password (Depends(require_admin)) - the
# dependency raises 401 before the route body even runs if the password is wrong.

@app.get("/admin/verify")
def admin_verify(_: None = Depends(require_admin)):
    # the frontend calls this just to check the password before showing the dashboard
    return {"success": True}


@app.get("/admin/workers")
def admin_list_workers(_: None = Depends(require_admin)):
    return {"success": True, "workers": employment.list_all_workers()}


@app.get("/admin/employers")
def admin_list_employers(_: None = Depends(require_admin)):
    return {"success": True, "employers": employment.list_all_employers()}


@app.get("/admin/jobs")
def admin_list_jobs(_: None = Depends(require_admin)):
    return {"success": True, "jobs": employment.list_all_jobs()}


@app.get("/admin/applications")
def admin_list_applications(_: None = Depends(require_admin)):
    return {"success": True, "applications": employment.list_all_applications()}


@app.delete("/admin/workers/{worker_id}")
def admin_remove_worker(worker_id: str, _: None = Depends(require_admin)):
    employment.admin_delete_worker(worker_id)
    return {"success": True, "message": "Worker profile removed."}


@app.delete("/admin/employers/{employer_id}")
def admin_remove_employer(employer_id: str, _: None = Depends(require_admin)):
    employment.admin_delete_employer(employer_id)
    return {"success": True, "message": "Employer profile removed."}


@app.delete("/admin/jobs/{job_id}")
def admin_remove_job(job_id: int, _: None = Depends(require_admin)):
    employment.admin_delete_job(job_id)
    return {"success": True, "message": "Job removed."}


# --- Conversational Assistant (Gemini) ---

@app.post("/chat")
def chat_with_assistant(request: ChatRequest):
    reply = gemini.ask_gemini(request.message)
    return {"success": True, "reply": reply}


# ---------- Serve the frontend ----------
# This MUST be the last thing registered - it's mounted at "/" and would otherwise
# swallow every API route above it if it came first. With it here, FastAPI checks
# all the specific routes (/options, /predict-crop, etc.) first, and only falls
# through to serving a frontend file if nothing else matched.

FRONTEND_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "frontend")
app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
