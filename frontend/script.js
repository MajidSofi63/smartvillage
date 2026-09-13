// script.js
// Handles: tab switching, language translation, connecting all forms to the
// backend, and the floating chat widget.
//
// API_URL is deliberately empty: this file is now served BY the same FastAPI app
// it talks to (see the StaticFiles mount at the bottom of backend/main.py), so
// every request is automatically same-origin - "" + "/options" just becomes
// "/options", which the browser resolves against whatever URL this page was
// loaded from. This works identically on localhost and on Render - nothing to
// edit before deploying, ever.
const API_URL = "";


// ================= SAFE FETCH HELPER =================
// Wraps fetch() so that network failures AND backend error responses (like
// FastAPI's 422 validation errors) both produce a clear message instead of
// the raw response shape leaking through as "undefined" in the UI.

async function safeFetch(url, options) {
  let response;
  try {
    response = await fetch(url, options);
  } catch (networkError) {
    // the server is unreachable (not running, wrong port, no internet, etc.)
    return { ok: false, data: null, errorMessage: "Can't reach the backend. Is uvicorn running on port 8000?" };
  }

  let data;
  try {
    data = await response.json();
  } catch (parseError) {
    return { ok: false, data: null, errorMessage: "Backend sent an unreadable response." };
  }

  if (!response.ok) {
    // FastAPI validation errors look like { "detail": [...] } - pull out something readable
    // FastAPI's HTTPException details are plain strings; validation errors are arrays -
    // only JSON.stringify the array case, so plain strings don't show stray quote marks
    const detail = data && data.detail
      ? (typeof data.detail === "string" ? data.detail : JSON.stringify(data.detail))
      : `Server error (${response.status})`;
    return { ok: false, data: null, errorMessage: detail };
  }

  return { ok: true, data: data, errorMessage: null };
}


// ================= LANGUAGE SWITCHING =================

let currentLang = localStorage.getItem("smartVillageLang") || "en";

function applyLanguage(lang) {
  currentLang = lang;
  localStorage.setItem("smartVillageLang", lang);
  const dict = translations[lang];

  document.getElementById("htmlRoot").setAttribute("dir", lang === "ur" ? "rtl" : "ltr");
  document.getElementById("htmlRoot").setAttribute("lang", lang);

  document.querySelectorAll("[data-i18n]").forEach(function (el) {
    const key = el.getAttribute("data-i18n");
    if (dict[key]) el.textContent = dict[key];
  });

  document.querySelectorAll("[data-i18n-placeholder]").forEach(function (el) {
    const key = el.getAttribute("data-i18n-placeholder");
    if (dict[key]) el.placeholder = dict[key];
  });

  document.getElementById("langSwitch").value = lang;
}

document.getElementById("langSwitch").addEventListener("change", function (event) {
  applyLanguage(event.target.value);
});


// ================= TAB SWITCHING =================

const tabButtons = document.querySelectorAll(".tab-btn");
const tabSections = document.querySelectorAll(".tab-section");

function showTab(tabName) {
  tabSections.forEach(function (section) {
    section.classList.toggle("active", section.id === tabName);
  });
  tabButtons.forEach(function (btn) {
    btn.classList.toggle("active", btn.dataset.tab === tabName);
  });
}

tabButtons.forEach(function (btn) {
  btn.addEventListener("click", function () {
    showTab(btn.dataset.tab);
  });
});

document.querySelectorAll(".card").forEach(function (card) {
  card.addEventListener("click", function () {
    showTab(card.dataset.goto);
  });
});


// ================= SHARED HELPERS =================

function showResult(boxId, html, style) {
  const box = document.getElementById(boxId);
  box.innerHTML = html;
  box.className = "result-box visible " + style; // style: success / warning / error / urgent
}

function setConnectionWarning(isDown) {
  const banner = document.getElementById("connectionWarning");
  banner.classList.toggle("visible", isDown);
  banner.textContent = "Can't reach the backend. Make sure the server is running: uvicorn main:app --reload";
}


// ================= PAGE LOAD =================

window.onload = async function () {
  applyLanguage(currentLang);
  restoreEmploymentSession(); // jump straight to a dashboard if already logged in - independent of crop options

  const result = await safeFetch(`${API_URL}/options`);

  if (!result.ok) {
    setConnectionWarning(true);
    return;
  }
  setConnectionWarning(false);

  const areaList = document.getElementById("areaOptions");
  const cropList = document.getElementById("cropOptions");

  result.data.areas.forEach(function (areaName) {
    const option = document.createElement("option");
    option.value = areaName;
    areaList.appendChild(option);
  });

  result.data.crops.forEach(function (cropName) {
    const option = document.createElement("option");
    option.value = cropName;
    cropList.appendChild(option);
  });
};


// ================= CROP PREDICTION =================

document.getElementById("cropForm").addEventListener("submit", async function (event) {
  event.preventDefault();

  // Validate numbers BEFORE sending, so a blank/invalid field never turns into
  // a silent NaN -> null -> confusing "undefined" result.
  const rainfall = parseFloat(document.getElementById("rainfall").value);
  const pesticides = parseFloat(document.getElementById("pesticides").value);
  const temperature = parseFloat(document.getElementById("temperature").value);

  if (isNaN(rainfall) || isNaN(pesticides) || isNaN(temperature)) {
    showResult("cropResult", "Please fill in rainfall, pesticides, and temperature with valid numbers.", "error");
    return;
  }

  const requestData = {
    area: document.getElementById("area").value,
    crop: document.getElementById("cropType").value,
    rainfall: rainfall,
    pesticides: pesticides,
    temperature: temperature,
    language: currentLang, // Gemini writes the explanation directly in this language
  };

  const result = await safeFetch(`${API_URL}/predict-crop`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(requestData),
  });

  if (!result.ok) {
    showResult("cropResult", result.errorMessage, "error");
    return;
  }

  if (result.data.success) {
    showResult(
      "cropResult",
      `<h4>Predicted Yield</h4>${result.data.predicted_yield_hg_per_ha} hg/ha<p>${result.data.explanation}</p>`,
      "success"
    );
  } else {
    showResult("cropResult", result.data.message, "error");
  }
});


// ================= TELEMEDICINE =================

document.getElementById("telemedicineForm").addEventListener("submit", async function (event) {
  event.preventDefault();

  const requestData = {
    symptoms: document.getElementById("symptoms").value,
    language: currentLang, // backend asks Gemini to answer directly in this language
  };

  const result = await safeFetch(`${API_URL}/telemedicine`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(requestData),
  });

  if (!result.ok) {
    showResult("telemedicineResult", result.errorMessage, "error");
    return;
  }

  const data = result.data;
  const style = data.urgent ? "urgent" : (data.condition === "Unrecognised symptoms" ? "warning" : "success");

  // The safety disclaimer always comes from our own translation dictionary,
  // never from the AI - so it's guaranteed correct no matter what Gemini returns.
  const disclaimer = translations[currentLang].teleDisclaimer;

  showResult(
    "telemedicineResult",
    `<h4>${data.urgent ? "⚠️ " : ""}${data.condition}</h4><p>${data.advice}</p><p><em>${disclaimer}</em></p>`,
    style
  );
});


// ================= GOVERNMENT SCHEMES =================

document.getElementById("schemesForm").addEventListener("submit", async function (event) {
  event.preventDefault();

  const requestData = {
    age: parseInt(document.getElementById("age").value),
    annual_income: parseFloat(document.getElementById("income").value),
    owns_land: document.getElementById("land").value === "true",
    category: document.getElementById("category").value,
  };

  const result = await safeFetch(`${API_URL}/schemes`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(requestData),
  });

  if (!result.ok) {
    showResult("schemesResult", result.errorMessage, "error");
    return;
  }

  const schemesFound = result.data.eligible_schemes;
  if (schemesFound.length === 0) {
    showResult("schemesResult", "No matching schemes found for your profile.", "warning");
  } else {
    let listHtml = "<h4>Eligible Schemes</h4><ul>";
    schemesFound.forEach(function (scheme) {
      listHtml += `<li><strong>${scheme.name}</strong><br>${scheme.description}<br><em>${scheme.steps}</em></li>`;
    });
    listHtml += "</ul>";
    showResult("schemesResult", listHtml, "success");
  }
});


// ================= SMART WATER MANAGEMENT =================

document.getElementById("waterForm").addEventListener("submit", async function (event) {
  event.preventDefault();

  const requestData = { city: document.getElementById("waterCity").value };

  const result = await safeFetch(`${API_URL}/water`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(requestData),
  });

  if (!result.ok) {
    showResult("waterResult", result.errorMessage, "error");
    return;
  }

  const data = result.data;
  if (!data.success) {
    showResult("waterResult", data.message, "error");
    return;
  }

  const style = (data.water_status === "Critical" || data.moisture_status === "Low") ? "warning" : "success";

  showResult(
    "waterResult",
    `<div class="result-row"><span>Location</span><span>${data.location_name}</span></div>
     <div class="result-row"><span>Soil Moisture</span><span>${data.soil_moisture_percent}% (${data.moisture_status})</span></div>
     <div class="result-row"><span>3-Day Water Balance</span><span>${data.water_balance_mm}mm (${data.water_status})</span></div>
     <p>${data.moisture_advice}</p>
     <p>${data.water_advice}</p>`,
    style
  );
});


// ================= DISASTER ALERTS =================

document.getElementById("disasterForm").addEventListener("submit", async function (event) {
  event.preventDefault();

  const requestData = { city: document.getElementById("city").value };

  const result = await safeFetch(`${API_URL}/disaster`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(requestData),
  });

  if (!result.ok) {
    showResult("disasterResult", result.errorMessage, "error");
    return;
  }

  const data = result.data;
  if (!data.success) {
    showResult("disasterResult", data.message, "error");
    return;
  }

  const hasRisk = data.alerts[0] !== "No immediate disaster risk detected.";
  let html = `<div class="result-row"><span>Condition</span><span>${data.condition}</span></div>
              <div class="result-row"><span>Temperature</span><span>${data.temperature}°C</span></div>
              <div class="result-row"><span>Wind Speed</span><span>${data.wind_speed} m/s</span></div>
              <div class="result-row"><span>Forecast</span><span>${data.forecast_summary}</span></div>
              <div class="result-row"><span>${data.air_quality}</span><span></span></div>
              <h4>Alerts</h4><ul>`;
  data.alerts.forEach(function (alert) {
    html += `<li>${alert}</li>`;
  });
  html += "</ul>";

  showResult("disasterResult", html, hasRisk ? "urgent" : "success");
});


// ================= EMPLOYMENT: VIEW SWITCHING =================
// Employment has several "views" (role choice, worker auth, employer auth, worker
// dashboard, employer dashboard) - only one is visible at a time.

const employmentViews = ["empRoleChoice", "workerAuthBox", "employerAuthBox", "workerDashboard", "employerDashboard"];

function showEmploymentView(viewId) {
  employmentViews.forEach(function (id) {
    document.getElementById(id).classList.toggle("active", id === viewId);
  });
}

document.getElementById("chooseWorkerBtn").addEventListener("click", function () {
  showEmploymentView("workerAuthBox");
});

document.getElementById("chooseEmployerBtn").addEventListener("click", function () {
  showEmploymentView("employerAuthBox");
});

document.querySelectorAll(".back-btn").forEach(function (btn) {
  btn.addEventListener("click", function () {
    showEmploymentView(btn.dataset.backto);
  });
});

// Login/Register sub-tabs inside each auth box
document.querySelectorAll(".auth-tab-btn").forEach(function (tabBtn) {
  tabBtn.addEventListener("click", function () {
    const box = tabBtn.closest(".auth-box");
    box.querySelectorAll(".auth-tab-btn").forEach(function (b) { b.classList.remove("active"); });
    box.querySelectorAll(".auth-form").forEach(function (f) { f.classList.remove("active"); });
    tabBtn.classList.add("active");
    document.getElementById(tabBtn.dataset.authtab).classList.add("active");
  });
});

// On page load: if a saved login token exists, jump straight to that dashboard
// instead of making the person log in again every visit.
function restoreEmploymentSession() {
  const workerToken = localStorage.getItem("workerToken");
  const employerToken = localStorage.getItem("employerToken");

  if (workerToken) {
    document.getElementById("workerDashName").textContent = localStorage.getItem("workerName") || "";
    showEmploymentView("workerDashboard");
    loadWorkerDashboard();
  } else if (employerToken) {
    document.getElementById("employerDashName").textContent = localStorage.getItem("employerName") || "";
    showEmploymentView("employerDashboard");
    loadEmployerDashboard();
  } else {
    showEmploymentView("empRoleChoice");
    loadPlatformStats();
  }
}

// Public counts shown on the role-choice screen - no login needed, just makes
// the platform feel active instead of an empty shell before anyone's logged in.
async function loadPlatformStats() {
  const result = await safeFetch(`${API_URL}/employment/stats`);
  const bar = document.getElementById("platformStatsBar");
  if (!result.ok) {
    bar.innerHTML = "";
    return;
  }
  const data = result.data;
  bar.innerHTML = `
    <div class="stat-box"><span class="stat-number">${data.worker_count}</span><span class="stat-label">Workers Registered</span></div>
    <div class="stat-box"><span class="stat-number">${data.employer_count}</span><span class="stat-label">Employers</span></div>
    <div class="stat-box"><span class="stat-number">${data.job_count}</span><span class="stat-label">Jobs Posted</span></div>`;
}


// ================= EMPLOYMENT: WORKER AUTH =================

document.getElementById("workerRegisterForm").addEventListener("submit", async function (event) {
  event.preventDefault();

  const requestData = {
    name: document.getElementById("workerRegName").value,
    email: document.getElementById("workerRegEmail").value,
    phone: document.getElementById("workerRegPhone").value,
    location: document.getElementById("workerRegLocation").value,
    skills: document.getElementById("workerRegSkills").value,
    password: document.getElementById("workerRegPassword").value,
  };

  const result = await safeFetch(`${API_URL}/auth/register-worker`, {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(requestData),
  });

  if (!result.ok || !result.data.success) {
    showResult("workerAuthResult", result.ok ? result.data.message : result.errorMessage, "error");
    return;
  }

  localStorage.setItem("workerToken", result.data.token);
  localStorage.setItem("workerName", result.data.name);
  document.getElementById("workerDashName").textContent = result.data.name;
  showEmploymentView("workerDashboard");
  loadWorkerDashboard();
});

document.getElementById("workerLoginForm").addEventListener("submit", async function (event) {
  event.preventDefault();

  const requestData = {
    email: document.getElementById("workerLoginEmail").value,
    password: document.getElementById("workerLoginPassword").value,
  };

  const result = await safeFetch(`${API_URL}/auth/login-worker`, {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(requestData),
  });

  if (!result.ok || !result.data.success) {
    showResult("workerAuthResult", result.ok ? result.data.message : result.errorMessage, "error");
    return;
  }

  localStorage.setItem("workerToken", result.data.token);
  localStorage.setItem("workerName", result.data.name);
  document.getElementById("workerDashName").textContent = result.data.name;
  showEmploymentView("workerDashboard");
  loadWorkerDashboard();
});

document.getElementById("workerLogoutBtn").addEventListener("click", function () {
  localStorage.removeItem("workerToken");
  localStorage.removeItem("workerName");
  showEmploymentView("empRoleChoice");
});


// ================= EMPLOYMENT: EMPLOYER AUTH =================

document.getElementById("employerRegisterForm").addEventListener("submit", async function (event) {
  event.preventDefault();

  const requestData = {
    name: document.getElementById("employerRegName").value,
    email: document.getElementById("employerRegEmail").value,
    password: document.getElementById("employerRegPassword").value,
  };

  const result = await safeFetch(`${API_URL}/auth/register-employer`, {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(requestData),
  });

  if (!result.ok || !result.data.success) {
    showResult("employerAuthResult", result.ok ? result.data.message : result.errorMessage, "error");
    return;
  }

  localStorage.setItem("employerToken", result.data.token);
  localStorage.setItem("employerName", result.data.name);
  document.getElementById("employerDashName").textContent = result.data.name;
  showEmploymentView("employerDashboard");
  loadEmployerDashboard();
});

document.getElementById("employerLoginForm").addEventListener("submit", async function (event) {
  event.preventDefault();

  const requestData = {
    email: document.getElementById("employerLoginEmail").value,
    password: document.getElementById("employerLoginPassword").value,
  };

  const result = await safeFetch(`${API_URL}/auth/login-employer`, {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(requestData),
  });

  if (!result.ok || !result.data.success) {
    showResult("employerAuthResult", result.ok ? result.data.message : result.errorMessage, "error");
    return;
  }

  localStorage.setItem("employerToken", result.data.token);
  localStorage.setItem("employerName", result.data.name);
  document.getElementById("employerDashName").textContent = result.data.name;
  showEmploymentView("employerDashboard");
  loadEmployerDashboard();
});

document.getElementById("employerLogoutBtn").addEventListener("click", function () {
  localStorage.removeItem("employerToken");
  localStorage.removeItem("employerName");
  showEmploymentView("empRoleChoice");
});


// ================= EMPLOYMENT: WORKER DASHBOARD =================

async function loadWorkerDashboard() {
  const token = localStorage.getItem("workerToken");

  // ---- Available jobs, sorted by skill match ----
  const jobsResult = await safeFetch(`${API_URL}/jobs/for-me`, { headers: { "X-Auth-Token": token } });
  const jobsList = document.getElementById("jobsList");
  jobsList.innerHTML = "";

  if (jobsResult.ok && jobsResult.data.jobs.length > 0) {
    jobsResult.data.jobs.forEach(function (job) {
      const card = document.createElement("div");
      card.className = "job-card";
      card.innerHTML = `
        <div class="job-card-header">
          <h4>${job.title}</h4>
          <button data-job-id="${job.id}" class="applyBtn">Apply</button>
        </div>
        <div class="job-card-meta">
          <span>📍 ${job.location}</span>
          <span>💼 ${job.type}</span>
          <span>🛠️ ${job.skills}</span>
        </div>`;
      jobsList.appendChild(card);
    });

    // wire up every "Apply" button just created
    jobsList.querySelectorAll(".applyBtn").forEach(function (btn) {
      btn.addEventListener("click", async function () {
        const applyResult = await safeFetch(`${API_URL}/jobs/${btn.dataset.jobId}/apply`, {
          method: "POST", headers: { "X-Auth-Token": token },
        });
        btn.textContent = applyResult.ok && applyResult.data.success ? "Applied ✓" : "Already Applied";
        btn.disabled = true;
        loadWorkerDashboard(); // refresh "My Applications" below to include the new one
      });
    });
  } else {
    jobsList.innerHTML = "<p>🔍 No jobs posted yet. Check back soon.</p>";
  }

  // ---- This worker's own application history ----
  const appsResult = await safeFetch(`${API_URL}/worker/applications`, { headers: { "X-Auth-Token": token } });
  const appsList = document.getElementById("myApplicationsList");
  appsList.innerHTML = "";

  if (appsResult.ok && appsResult.data.applications.length > 0) {
    appsResult.data.applications.forEach(function (app) {
      const card = document.createElement("div");
      card.className = "job-card";
      card.innerHTML = `
        <div class="job-card-header">
          <h4>${app.title}</h4>
          <span class="status-tag ${app.status}">${app.status}</span>
        </div>
        <div class="job-card-meta">
          <span>📍 ${app.location}</span>
          <span>💼 ${app.type}</span>
        </div>
        <button class="btn-danger withdrawBtn" data-app-id="${app.application_id}">Withdraw</button>`;
      appsList.appendChild(card);
    });

    // wire up every "Withdraw" button just created
    appsList.querySelectorAll(".withdrawBtn").forEach(function (btn) {
      btn.addEventListener("click", async function () {
        await safeFetch(`${API_URL}/worker/applications/${btn.dataset.appId}`, {
          method: "DELETE", headers: { "X-Auth-Token": token },
        });
        loadWorkerDashboard(); // refresh both lists - the job reappears as available to re-apply to
      });
    });
  } else {
    appsList.innerHTML = "<p>📋 You haven't applied to any jobs yet.</p>";
  }

  // ---- Stats summary ----
  const hiredCount = appsResult.ok ? appsResult.data.applications.filter(a => a.status === "Hired").length : 0;
  document.getElementById("workerStatsBar").innerHTML = `
    <div class="stat-box"><span class="stat-number">${jobsResult.ok ? jobsResult.data.jobs.length : "-"}</span><span class="stat-label">Jobs Available</span></div>
    <div class="stat-box"><span class="stat-number">${appsResult.ok ? appsResult.data.applications.length : "-"}</span><span class="stat-label">Applications Sent</span></div>
    <div class="stat-box"><span class="stat-number">${hiredCount}</span><span class="stat-label">Times Hired</span></div>`;
}


// ================= EMPLOYMENT: EMPLOYER DASHBOARD =================

document.getElementById("jobPostForm").addEventListener("submit", async function (event) {
  event.preventDefault();
  const token = localStorage.getItem("employerToken");

  const requestData = {
    title: document.getElementById("jobTitle").value,
    skills: document.getElementById("jobSkills").value,
    location: document.getElementById("jobLocation").value,
    job_type: document.getElementById("jobType").value,
    contact: document.getElementById("jobContact").value,
  };

  const result = await safeFetch(`${API_URL}/jobs`, {
    method: "POST", headers: { "Content-Type": "application/json", "X-Auth-Token": token },
    body: JSON.stringify(requestData),
  });

  if (!result.ok) {
    showResult("jobPostResult", result.errorMessage, "error");
    return;
  }

  showResult("jobPostResult", "✅ Job posted successfully.", "success");
  event.target.reset();
  loadEmployerDashboard();
});

async function loadEmployerDashboard() {
  const token = localStorage.getItem("employerToken");

  const jobsResult = await safeFetch(`${API_URL}/jobs/mine`, { headers: { "X-Auth-Token": token } });
  const myJobsList = document.getElementById("myJobsList");
  myJobsList.innerHTML = "";

  // stats bar, even when there are zero jobs yet
  const totalApplicants = jobsResult.ok ? jobsResult.data.jobs.reduce((sum, j) => sum + j.applicant_count, 0) : 0;
  document.getElementById("employerStatsBar").innerHTML = `
    <div class="stat-box"><span class="stat-number">${jobsResult.ok ? jobsResult.data.jobs.length : "-"}</span><span class="stat-label">Jobs Posted</span></div>
    <div class="stat-box"><span class="stat-number">${totalApplicants}</span><span class="stat-label">Total Applicants</span></div>`;

  if (!jobsResult.ok || jobsResult.data.jobs.length === 0) {
    myJobsList.innerHTML = "<p>📋 You haven't posted any jobs yet.</p>";
    return;
  }

  jobsResult.data.jobs.forEach(function (job) {
    const card = document.createElement("div");
    card.className = "job-card";
    card.innerHTML = `
      <div class="job-card-header">
        <h4>${job.title}</h4>
        <span>
          <button class="btn-secondary viewApplicantsBtn" data-job-id="${job.id}">👥 Applicants (${job.applicant_count})</button>
          <button class="btn-danger deleteJobBtn" data-job-id="${job.id}">Delete</button>
        </span>
      </div>
      <div class="job-card-meta">
        <span>📍 ${job.location}</span>
        <span>💼 ${job.type}</span>
        <span>🛠️ ${job.skills}</span>
      </div>
      <div class="applicant-list" id="applicants-${job.id}"></div>`;
    myJobsList.appendChild(card);
  });

  // wire up every "Delete" button just created
  myJobsList.querySelectorAll(".deleteJobBtn").forEach(function (btn) {
    btn.addEventListener("click", async function () {
      if (!confirm("Delete this job posting? This also removes all its applications.")) return;
      await safeFetch(`${API_URL}/jobs/${btn.dataset.jobId}`, {
        method: "DELETE", headers: { "X-Auth-Token": token },
      });
      loadEmployerDashboard();
    });
  });

  // wire up every "View Applicants" button just created
  myJobsList.querySelectorAll(".viewApplicantsBtn").forEach(function (btn) {
    btn.addEventListener("click", async function () {
      const box = document.getElementById(`applicants-${btn.dataset.jobId}`);
      const isOpening = !box.classList.contains("visible");
      box.classList.toggle("visible");
      if (!isOpening) return; // just closing it, no need to re-fetch

      const applicantsResult = await safeFetch(`${API_URL}/jobs/${btn.dataset.jobId}/applicants`, {
        headers: { "X-Auth-Token": token },
      });

      if (!applicantsResult.ok || applicantsResult.data.applicants.length === 0) {
        box.innerHTML = "<p>No applicants yet.</p>";
        return;
      }

      box.innerHTML = "";
      applicantsResult.data.applicants.forEach(function (applicant) {
        const row = document.createElement("div");
        row.className = "applicant-row";
        row.innerHTML = `
          <span><strong>${applicant.name}</strong> · ${applicant.location} · ${applicant.phone}</span>
          <select class="statusSelect" data-app-id="${applicant.application_id}">
            <option value="Applied" ${applicant.status === "Applied" ? "selected" : ""}>Applied</option>
            <option value="Contacted" ${applicant.status === "Contacted" ? "selected" : ""}>Contacted</option>
            <option value="Hired" ${applicant.status === "Hired" ? "selected" : ""}>Hired</option>
          </select>`;
        box.appendChild(row);
      });

      // wire up the status dropdown for this applicant list - one clean control
      // instead of two separate "Mark X" buttons
      box.querySelectorAll(".statusSelect").forEach(function (select) {
        select.addEventListener("change", async function () {
          await safeFetch(`${API_URL}/applications/${select.dataset.appId}/status`, {
            method: "PATCH", headers: { "Content-Type": "application/json", "X-Auth-Token": token },
            body: JSON.stringify({ status: select.value }),
          });
          loadEmployerDashboard(); // refreshes the "Applicants (N)" count and stats bar too
        });
      });
    });
  });
}


// ================= FLOATING ASSISTANT WIDGET =================

const chatBubble = document.getElementById("chatBubble");
const chatPanel = document.getElementById("chatPanel");

chatBubble.addEventListener("click", function () {
  chatPanel.classList.toggle("open");
});

document.getElementById("chatCloseBtn").addEventListener("click", function () {
  chatPanel.classList.remove("open");
});

document.getElementById("chatForm").addEventListener("submit", async function (event) {
  event.preventDefault();

  const input = document.getElementById("chatInput");
  const message = input.value;
  const chatWindow = document.getElementById("chatWindow");

  chatWindow.innerHTML += `<div class="chat-message user">${message}</div>`;
  input.value = "";
  chatWindow.scrollTop = chatWindow.scrollHeight;

  const result = await safeFetch(`${API_URL}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message: message }),
  });

  const replyText = result.ok ? result.data.reply : result.errorMessage;
  chatWindow.innerHTML += `<div class="chat-message assistant">${replyText}</div>`;
  chatWindow.scrollTop = chatWindow.scrollHeight;
});


// ================= ADMIN PANEL =================
// The admin password is kept only in this variable (never localStorage) - closing
// the tab or refreshing requires logging in again, which is the right trade-off
// for something this sensitive.

let adminPassword = null;

document.getElementById("adminLoginForm").addEventListener("submit", async function (event) {
  event.preventDefault();
  const enteredPassword = document.getElementById("adminPasswordInput").value;

  const result = await safeFetch(`${API_URL}/admin/verify`, {
    headers: { "X-Admin-Password": enteredPassword },
  });

  if (!result.ok) {
    showResult("adminAuthResult", "Incorrect password.", "error");
    return;
  }

  adminPassword = enteredPassword;
  document.getElementById("adminLoginForm").classList.remove("active");
  document.getElementById("adminDashboard").classList.add("active");
  loadAdminDashboard();
});

document.getElementById("adminLogoutBtn").addEventListener("click", function () {
  adminPassword = null;
  document.getElementById("adminDashboard").classList.remove("active");
  document.getElementById("adminLoginForm").classList.add("active");
  document.getElementById("adminPasswordInput").value = "";
});

async function loadAdminDashboard() {
  const headers = { "X-Admin-Password": adminPassword };

  // fetch all four datasets at once rather than one after another
  const [workersResult, employersResult, jobsResult, applicationsResult] = await Promise.all([
    safeFetch(`${API_URL}/admin/workers`, { headers }),
    safeFetch(`${API_URL}/admin/employers`, { headers }),
    safeFetch(`${API_URL}/admin/jobs`, { headers }),
    safeFetch(`${API_URL}/admin/applications`, { headers }),
  ]);

  // ---- Summary stats bar ----
  document.getElementById("adminStatsBar").innerHTML = `
    <div class="stat-box"><span class="stat-number">${workersResult.ok ? workersResult.data.workers.length : "-"}</span><span class="stat-label">Workers</span></div>
    <div class="stat-box"><span class="stat-number">${employersResult.ok ? employersResult.data.employers.length : "-"}</span><span class="stat-label">Employers</span></div>
    <div class="stat-box"><span class="stat-number">${jobsResult.ok ? jobsResult.data.jobs.length : "-"}</span><span class="stat-label">Jobs Posted</span></div>
    <div class="stat-box"><span class="stat-number">${applicationsResult.ok ? applicationsResult.data.applications.length : "-"}</span><span class="stat-label">Applications</span></div>`;

  // ---- Workers ----
  const workersList = document.getElementById("adminWorkersList");
  workersList.innerHTML = "";
  if (workersResult.ok && workersResult.data.workers.length > 0) {
    workersResult.data.workers.forEach(function (worker) {
      const row = document.createElement("div");
      row.className = "admin-row";
      row.innerHTML = `
        <div class="admin-row-details">
          <strong>${worker.name}</strong>
          <span>${worker.email} · ${worker.phone} · ${worker.location}</span>
          <span>Skills: ${worker.skills}</span>
        </div>
        <button class="btn-danger deleteWorkerBtn" data-id="${worker.id}">Delete</button>`;
      workersList.appendChild(row);
    });
    workersList.querySelectorAll(".deleteWorkerBtn").forEach(function (btn) {
      btn.addEventListener("click", async function () {
        if (!confirm("Remove this worker's profile/listing?")) return;
        await safeFetch(`${API_URL}/admin/workers/${btn.dataset.id}`, { method: "DELETE", headers });
        loadAdminDashboard();
      });
    });
  } else {
    workersList.innerHTML = "<p>No workers registered yet.</p>";
  }

  // ---- Employers ----
  const employersList = document.getElementById("adminEmployersList");
  employersList.innerHTML = "";
  if (employersResult.ok && employersResult.data.employers.length > 0) {
    employersResult.data.employers.forEach(function (employer) {
      const row = document.createElement("div");
      row.className = "admin-row";
      row.innerHTML = `
        <div class="admin-row-details">
          <strong>${employer.name}</strong>
          <span>${employer.email}</span>
        </div>
        <button class="btn-danger deleteEmployerBtn" data-id="${employer.id}">Delete</button>`;
      employersList.appendChild(row);
    });
    employersList.querySelectorAll(".deleteEmployerBtn").forEach(function (btn) {
      btn.addEventListener("click", async function () {
        if (!confirm("Remove this employer's profile/listing?")) return;
        await safeFetch(`${API_URL}/admin/employers/${btn.dataset.id}`, { method: "DELETE", headers });
        loadAdminDashboard();
      });
    });
  } else {
    employersList.innerHTML = "<p>No employers registered yet.</p>";
  }

  // ---- Jobs ----
  const jobsList = document.getElementById("adminJobsList");
  jobsList.innerHTML = "";
  if (jobsResult.ok && jobsResult.data.jobs.length > 0) {
    jobsResult.data.jobs.forEach(function (job) {
      const row = document.createElement("div");
      row.className = "admin-row";
      row.innerHTML = `
        <div class="admin-row-details">
          <strong>${job.title}</strong>
          <span>Posted by ${job.employer_name} (${job.employer_email}) · ${job.location} · ${job.type}</span>
          <span>${job.applicant_count} applicant(s)</span>
        </div>
        <button class="btn-danger deleteAdminJobBtn" data-id="${job.id}">Delete</button>`;
      jobsList.appendChild(row);
    });
    jobsList.querySelectorAll(".deleteAdminJobBtn").forEach(function (btn) {
      btn.addEventListener("click", async function () {
        if (!confirm("Delete this job posting?")) return;
        await safeFetch(`${API_URL}/admin/jobs/${btn.dataset.id}`, { method: "DELETE", headers });
        loadAdminDashboard();
      });
    });
  } else {
    jobsList.innerHTML = "<p>No jobs posted yet.</p>";
  }

  // ---- Applications ----
  const applicationsList = document.getElementById("adminApplicationsList");
  applicationsList.innerHTML = "";
  if (applicationsResult.ok && applicationsResult.data.applications.length > 0) {
    applicationsResult.data.applications.forEach(function (application) {
      const row = document.createElement("div");
      row.className = "admin-row";
      row.innerHTML = `
        <div class="admin-row-details">
          <strong>${application.worker_name}</strong> applied to <strong>${application.job_title}</strong>
          <span>${application.worker_phone} · <span class="status-tag ${application.status}">${application.status}</span></span>
        </div>`;
      applicationsList.appendChild(row);
    });
  } else {
    applicationsList.innerHTML = "<p>No applications yet.</p>";
  }
}
