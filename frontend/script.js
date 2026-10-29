// script.js
// Handles: tab switching, language translation, connecting all forms to the
// backend, and the floating chat widget. API_URL is empty because this file is
// served BY the same FastAPI app it talks to (same origin).
const API_URL = "";

// ================= OFFLINE SUPPORT (Service Worker) =================
if ("serviceWorker" in navigator) {
  window.addEventListener("load", function () {
    navigator.serviceWorker.register("/sw.js").catch(function (error) {
      console.log("Service worker registration failed:", error);
    });
  });
}
window.addEventListener("offline", function () { setConnectionWarning(true); });
window.addEventListener("online", function () { setConnectionWarning(false); });


// ================= SAFE FETCH HELPER =================

async function safeFetch(url, options) {
  let response;
  try {
    response = await fetch(url, options);
  } catch (networkError) {
    return { ok: false, data: null, errorMessage: "Can't reach the backend. Is uvicorn running on port 8000?" };
  }

  let data;
  try {
    data = await response.json();
  } catch (parseError) {
    return { ok: false, data: null, errorMessage: "Backend sent an unreadable response." };
  }

  if (!response.ok) {
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

  // Re-render the last crop result so its labels follow the new language.
  if (lastCropRecommendation) renderCropRecommendation(lastCropRecommendation);
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
  btn.addEventListener("click", function () { showTab(btn.dataset.tab); });
});

document.querySelectorAll(".card").forEach(function (card) {
  card.addEventListener("click", function () { showTab(card.dataset.goto); });
});


// ================= SHARED HELPERS =================

function showResult(boxId, html, style) {
  const box = document.getElementById(boxId);
  box.innerHTML = html;
  box.className = "result-box visible " + style;
}

function setConnectionWarning(isDown, detail) {
  const banner = document.getElementById("connectionWarning");
  banner.classList.toggle("visible", isDown);
  banner.textContent = detail
    ? `Backend error: ${detail}`
    : "Can't reach the backend. Please check your connection and try again.";
}


// ================= PAGE LOAD =================

window.onload = async function () {
  applyLanguage(currentLang);
  restoreEmploymentSession();
  handlePasswordRecoveryLink(); // if they arrived from a reset email, show the "new password" form

  // Admin is deliberately not in the nav bar - only reachable by visiting /admin directly
  if (window.location.pathname === "/admin" || window.location.pathname === "/admin/" || window.location.pathname.endsWith("/admin")) {
    showTab("admin");
  }

  await loadCropSeasons();
  setupDistrictSearch();
  updateCropButtonState();
};


// ================= CROP RECOMMENDATION =================

let cropDistrictId = null;
let cropSearchTimer = null;
let lastCropRecommendation = null;

function translate(key, fallback) {
  const dict = translations[currentLang] || {};
  return dict[key] || fallback;
}

function escapeHtml(value) {
  return String(value)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

async function loadCropSeasons() {
  const result = await safeFetch(`${API_URL}/api/seasons`);
  if (!result.ok) {
    setConnectionWarning(true, result.errorMessage);
    return;
  }
  setConnectionWarning(false);

  const select = document.getElementById("seasonSelect");
  result.data.seasons.forEach(function (season) {
    const option = document.createElement("option");
    option.value = season;
    option.textContent = season;
    select.appendChild(option);
  });
}

function setupDistrictSearch() {
  const input = document.getElementById("districtSearch");
  const suggestions = document.getElementById("districtSuggestions");

  input.addEventListener("input", function () {
    const query = input.value.trim();

    // Typing invalidates the previous selection until a suggestion is clicked.
    cropDistrictId = null;
    document.getElementById("districtId").value = "";
    updateCropButtonState();

    suggestions.innerHTML = "";
    suggestions.style.display = "none";
    if (query.length < 2) return;

    clearTimeout(cropSearchTimer);
    cropSearchTimer = setTimeout(async function () {
      const result = await safeFetch(
        `${API_URL}/api/districts?q=${encodeURIComponent(query)}`
      );
      if (!result.ok) return;

      suggestions.innerHTML = "";
      if (!result.data.districts.length) {
        suggestions.style.display = "none";
        return;
      }

      result.data.districts.forEach(function (district) {
        const item = document.createElement("button");
        item.type = "button";
        item.className = "suggestion-item";
        item.textContent = `${district.district}, ${district.state}`;
        item.addEventListener("click", function () {
          input.value = `${district.district}, ${district.state}`;
          cropDistrictId = district.id;
          document.getElementById("districtId").value = String(district.id);
          suggestions.innerHTML = "";
          suggestions.style.display = "none";
          updateCropButtonState();
        });
        suggestions.appendChild(item);
      });
      suggestions.style.display = "block";
    }, 250);
  });

  // Hide suggestions when clicking outside the search box.
  document.addEventListener("click", function (event) {
    if (event.target !== input && !suggestions.contains(event.target)) {
      suggestions.style.display = "none";
    }
  });

  document.getElementById("seasonSelect").addEventListener("change", updateCropButtonState);
}

function updateCropButtonState() {
  const season = document.getElementById("seasonSelect").value;
  document.getElementById("recommendBtn").disabled = !(cropDistrictId && season);
}

document.getElementById("cropForm").addEventListener("submit", async function (event) {
  event.preventDefault();

  const season = document.getElementById("seasonSelect").value;
  if (!cropDistrictId) {
    showResult("cropResult", translate("cropPickDistrict", "Please pick a district from the suggestions."), "error");
    return;
  }
  if (!season) {
    showResult("cropResult", translate("cropPickSeason", "Please select a planting season."), "error");
    return;
  }

  const box = document.getElementById("cropResult");
  box.className = "result-box visible";
  box.innerHTML = `<p class="crop-loading">${translate("cropLoading", "Analysing crop suitability…")}</p>`;

  const result = await safeFetch(`${API_URL}/api/recommend`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      district_id: cropDistrictId,
      season: season,
      language: currentLang,
    }),
  });

  if (!result.ok) {
    showResult("cropResult", escapeHtml(result.errorMessage), "error");
    return;
  }

  lastCropRecommendation = result.data;
  document.getElementById("cropResult").className = "result-box visible success";
  renderCropRecommendation(result.data);
});

function renderCropRecommendation(data) {
  const box = document.getElementById("cropResult");
  if (!data || !data.recommendations || !data.recommendations.length) {
    box.className = "result-box visible warning";
    box.innerHTML = `<p>${translate("cropNoResults", "No crops could be recommended for this district and season.")}</p>`;
    return;
  }

  const top = data.recommendations[0];
  const others = data.recommendations.slice(1);
  const weather = data.weather_used || {};
  const modelInput = weather.model_input || {};
  const live = weather.live_conditions;
  const forecast = weather.forecast_7day || [];

  const agreementClass = (top.agreement || "").toLowerCase();
  const agreementText = translate(
    "agreement" + (top.agreement || "High"),
    top.agreement + " agreement"
  );

  const stat = function (labelKey, labelFallback, value, unit) {
    return `<div class="crop-stat">
      <span>${translate(labelKey, labelFallback)}</span>
      <strong>${escapeHtml(value)} <small>${escapeHtml(unit)}</small></strong>
    </div>`;
  };

  const otherHtml = others.length
    ? others.map(function (rec, index) {
        const cls = (rec.agreement || "").toLowerCase();
        const otherAgreement = translate(
          "agreement" + (rec.agreement || "High"),
          rec.agreement + " agreement"
        );
        return `<div class="crop-other-item">
          <div class="crop-other-head">
            <strong><span class="crop-rank">#${index + 2}</span> ${escapeHtml(rec.crop)}</strong>
            <span class="crop-suit-pill">${escapeHtml(rec.suitability)}%</span>
          </div>
          <div class="crop-other-stats">
            <span><b>${escapeHtml(rec.expected_yield)}</b> t/ha ${translate("cropExpectedShort", "expected")}</span>
            <span><b>${escapeHtml(rec.historical_median)}</b> t/ha ${translate("cropMedianShort", "median")}</span>
            <span><b>${escapeHtml(rec.years_of_evidence)}</b> ${translate("cropYearsShort", "years")}</span>
            <span class="crop-agreement ${cls}">${escapeHtml(otherAgreement)}</span>
          </div>
        </div>`;
      }).join("")
    : `<p class="crop-muted">${translate("cropNoOther", "No other strong matches.")}</p>`;

  const reasonsHtml = data.recommendations.map(function (rec, index) {
    const items = (rec.reasons || []).map(function (reason) {
      return `<li>${escapeHtml(reason)}</li>`;
    }).join("");
    return `<details class="crop-reason" ${index === 0 ? "open" : ""}>
      <summary><span class="crop-rank">#${index + 1}</span> ${escapeHtml(rec.crop)}</summary>
      <ul>${items}</ul>
    </details>`;
  }).join("");

  const limitationsHtml = (data.limitations || []).map(function (item) {
    return `<li>${escapeHtml(item)}</li>`;
  }).join("");

  const liveText = function (value, unit) {
    return (value === null || value === undefined)
      ? translate("cropUnavailable", "Unavailable")
      : `${value} ${unit}`;
  };

  const forecastHtml = forecast.length
    ? forecast.slice(0, 7).map(function (day) {
        const date = new Date(`${day.date}T00:00:00`);
        return `<div class="crop-forecast-day">
          <span>${date.toLocaleDateString("en-IN", { month: "short", day: "numeric" })}</span>
          <b>${day.temp_min}°–${day.temp_max}°C</b>
          <span>${day.precipitation} mm</span>
        </div>`;
      }).join("")
    : `<p class="crop-muted">${translate("cropForecastUnavailable", "Live forecast unavailable.")}</p>`;

  const modelInfo = data.model_info || {};
  const weights = modelInfo.weights || {};
  const metrics = modelInfo.metrics || {};
  const modelRows = [
    ["RandomForest", "Random Forest"],
    ["XGBoost", "XGBoost"],
    ["HistGradientBoosting", "HistGradientBoosting"],
  ].map(function (pair) {
    const name = pair[0];
    const jsonKey = name === "RandomForest" ? "RandomForest" : name;
    const metric = metrics[jsonKey] || {};
    const weight = weights[name] === undefined ? "--" : (weights[name] * 100).toFixed(1) + "%";
    const testMae = metric.MAE === undefined ? "--" : Number(metric.MAE).toFixed(3);
    return `<tr>
      <td>${pair[1]}</td>
      <td>${escapeHtml(top.models[name])} t/ha</td>
      <td>${weight}</td>
      <td>${testMae} t/ha</td>
    </tr>`;
  }).join("");

  box.innerHTML = `
    <div class="crop-results-head">
      <div>
        <span class="crop-eyebrow">${translate("cropResultsEyebrow", "Recommendations")}</span>
        <h4>${escapeHtml(data.district.name)}, ${escapeHtml(data.district.state)}</h4>
      </div>
      <span class="crop-season-badge">${escapeHtml(data.season)}</span>
    </div>

    <div class="crop-top-card">
      <div>
        <span class="crop-top-badge">${translate("cropTopPick", "Top pick")}</span>
        <div class="crop-top-name">${escapeHtml(top.crop)}</div>
        <p class="crop-top-sub">${translate("cropTopSub", "Highest predicted yield relative to this crop's own historical median.")}</p>
      </div>
      <div class="crop-suitability">
        <strong>${escapeHtml(top.suitability)}%</strong>
        <span>${translate("cropOfMedian", "of historical median")}</span>
      </div>
    </div>

    <div class="crop-stat-grid">
      ${stat("cropExpectedYield", "Expected yield", top.expected_yield, "t/ha")}
      ${stat("cropHistoricalMedian", "Historical median", top.historical_median, "t/ha")}
      ${stat("cropTypicalRange", "Typical range", `${top.historical_range.p25}–${top.historical_range.p75}`, "t/ha")}
      ${stat("cropYearsEvidence", "Years of evidence", top.years_of_evidence, translate("cropYearsShort", "years"))}
    </div>

    <div class="crop-pill-row">
      <span class="crop-agreement-pill ${agreementClass}">${escapeHtml(agreementText)}</span>
      <span class="crop-hint">${translate("cropRankHint", "Ranked by suitability, never by raw yield across crops.")}</span>
    </div>

    <h4 class="crop-subheading">${translate("cropOtherMatches", "Other strong matches")}</h4>
    <div class="crop-other-list">${otherHtml}</div>

    <h4 class="crop-subheading">${translate("cropWhy", "Why these crops")}</h4>
    <div class="crop-reasons">${reasonsHtml}</div>

    <h4 class="crop-subheading">${translate("cropWeatherUsed", "Weather used")}</h4>
    <div class="crop-weather-grid">
      <div class="crop-weather-item"><span>🌡️</span><b>${modelInput.temperature} °C</b><small>${translate("cropSeasonalTemp", "Seasonal average")}</small></div>
      <div class="crop-weather-item"><span>🌧️</span><b>${modelInput.rainfall} mm</b><small>${translate("cropSeasonalRain", "Seasonal total")}</small></div>
      <div class="crop-weather-item"><span>📅</span><b>${(modelInput.years_used || []).length}</b><small>${translate("cropYearsUsed", "Years used")}</small></div>
      <div class="crop-weather-item"><span>🌤️</span><b>${liveText(live && live.temperature, "°C")}</b><small>${translate("cropLiveTemp", "Live temperature")}</small></div>
    </div>
    <p class="crop-note">${escapeHtml(modelInput.note || "")}</p>
    <div class="crop-live-weather">
      <span>${translate("cropLiveConditions", "Live conditions")}:</span>
      ${translate("cropHumidity", "Humidity")} ${liveText(live && live.humidity, "%")} ·
      ${translate("cropPrecipitation", "Precipitation")} ${liveText(live && live.precipitation, "mm")} ·
      ${translate("cropWind", "Wind")} ${liveText(live && live.wind_speed, "km/h")}
    </div>
    <div class="crop-forecast">${forecastHtml}</div>

    <h4 class="crop-subheading">${translate("cropLimitations", "Read this before acting")}</h4>
    <ul class="crop-limitations">${limitationsHtml}</ul>

    <details class="crop-model-details">
      <summary>${translate("cropModelDetails", "Model details")}</summary>
      <table>
        <thead><tr>
          <th>${translate("cropModel", "Model")}</th>
          <th>${translate("cropPrediction", "Prediction")}</th>
          <th>${translate("cropWeight", "Weight")}</th>
          <th>${translate("cropTestMae", "Test MAE")}</th>
        </tr></thead>
        <tbody>${modelRows}
          <tr class="crop-ensemble-row">
            <td>${translate("cropEnsemble", "Ensemble")}</td>
            <td>${escapeHtml(top.models.Ensemble)} t/ha</td>
            <td>${translate("cropUsedForRanking", "Used for ranking")}</td>
            <td>${escapeHtml((metrics.Ensemble && Number(metrics.Ensemble.MAE).toFixed(3)) || "--")} t/ha</td>
          </tr>
        </tbody>
      </table>
      <p class="crop-note">${translate("cropModelNote", "Test metrics come from held-out years 2010–2011, the most recent in the dataset.")}</p>
    </details>
  `;
}


// ================= TELEMEDICINE =================

document.getElementById("telemedicineForm").addEventListener("submit", async function (event) {
  event.preventDefault();

  const requestData = {
    symptoms: document.getElementById("symptoms").value,
    language: currentLang,
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
  data.alerts.forEach(function (alert) { html += `<li>${alert}</li>`; });
  html += "</ul>";

  showResult("disasterResult", html, hasRisk ? "urgent" : "success");
});


// ================= EMPLOYMENT: VIEW SWITCHING =================

const employmentViews = ["publicFeedView", "workerAuthBox", "workerProfileBox"];

function showEmploymentView(viewId) {
  employmentViews.forEach(function (id) {
    document.getElementById(id).classList.toggle("active", id === viewId);
  });
}

document.getElementById("showWorkerAuthBtn").addEventListener("click", function () {
  showEmploymentView("workerAuthBox");
  showAuthForm("workerLoginForm"); // always open on the login form, even if they left from "forgot password"
});

document.querySelectorAll(".back-btn").forEach(function (btn) {
  btn.addEventListener("click", function () { showEmploymentView(btn.dataset.backto); });
});

document.querySelectorAll(".auth-tab-btn").forEach(function (tabBtn) {
  tabBtn.addEventListener("click", function () {
    const box = tabBtn.closest(".auth-box");
    box.querySelectorAll(".auth-tab-btn").forEach(function (b) { b.classList.remove("active"); });
    box.querySelectorAll(".auth-form").forEach(function (f) { f.classList.remove("active"); });
    tabBtn.classList.add("active");
    document.getElementById(tabBtn.dataset.authtab).classList.add("active");
  });
});

// ================= EMPLOYMENT: FORGOT / RESET PASSWORD =================
// Four forms live inside the auth box: login, register, forgot-password, reset-password.
// Login/register are reached through the two tabs; the other two are not, so the
// tabs are hidden while those are showing.

function showAuthForm(formId) {
  const box = document.getElementById("workerAuthBox");
  box.querySelectorAll(".auth-form").forEach(function (form) {
    form.classList.toggle("active", form.id === formId);
  });

  const isTabbedForm = formId === "workerLoginForm" || formId === "workerRegisterForm";
  box.querySelector(".auth-tabs").style.display = isTabbedForm ? "" : "none";
  box.querySelectorAll(".auth-tab-btn").forEach(function (tabBtn) {
    tabBtn.classList.toggle("active", tabBtn.dataset.authtab === formId);
  });
}

function clearAuthMessage() {
  const box = document.getElementById("workerAuthResult");
  box.innerHTML = "";
  box.className = "result-box";
}

// The short-lived token from the emailed link. Kept only in memory - never saved to
// localStorage, and removed from the address bar as soon as the page reads it.
let recoveryToken = null;

document.getElementById("forgotPasswordLink").addEventListener("click", function () {
  clearAuthMessage();
  showAuthForm("forgotPasswordForm");
});

// Any button marked data-showform="<formId>" just switches to that form
document.querySelectorAll("[data-showform]").forEach(function (btn) {
  btn.addEventListener("click", function () {
    clearAuthMessage();
    showAuthForm(btn.dataset.showform);
  });
});

document.getElementById("forgotPasswordForm").addEventListener("submit", async function (event) {
  event.preventDefault();

  const result = await safeFetch(`${API_URL}/auth/forgot-password`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      email: document.getElementById("forgotEmail").value,
      redirect_to: window.location.origin + "/", // the emailed link brings them back to this site
    }),
  });

  if (!result.ok || !result.data.success) {
    showResult("workerAuthResult", result.ok ? result.data.message : result.errorMessage, "error");
    return;
  }

  showResult("workerAuthResult", translations[currentLang].resetEmailSent, "success");
});

document.getElementById("resetPasswordForm").addEventListener("submit", async function (event) {
  event.preventDefault();
  const text = translations[currentLang];

  const newPassword = document.getElementById("resetNewPassword").value;
  const confirmPassword = document.getElementById("resetConfirmPassword").value;

  if (newPassword.length < 6) {
    showResult("workerAuthResult", text.passwordTooShort, "error");
    return;
  }
  if (newPassword !== confirmPassword) {
    showResult("workerAuthResult", text.passwordsDontMatch, "error");
    return;
  }

  const result = await safeFetch(`${API_URL}/auth/reset-password`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ token: recoveryToken, new_password: newPassword }),
  });

  if (!result.ok || !result.data.success) {
    showResult("workerAuthResult", result.ok ? result.data.message : result.errorMessage, "error");
    return;
  }

  recoveryToken = null;
  event.target.reset();
  showAuthForm("workerLoginForm");
  showResult("workerAuthResult", text.passwordResetDone, "success");
});

// When someone clicks the link in their reset email, Supabase sends them back to this
// site with the token in the part of the address after "#". Returns true if that's
// what this page load is, so the normal start-up can step aside.
function handlePasswordRecoveryLink() {
  if (!window.location.hash || window.location.hash.length < 2) return false;
  const params = new URLSearchParams(window.location.hash.substring(1));

  // An expired or already-used link comes back as an error in the same place
  if (params.get("error") || params.get("error_description")) {
    history.replaceState(null, "", window.location.pathname);
    showTab("employment");
    showEmploymentView("workerAuthBox");
    showAuthForm("forgotPasswordForm");
    showResult("workerAuthResult", translations[currentLang].resetLinkExpired, "error");
    return true;
  }

  if (params.get("type") === "recovery" && params.get("access_token")) {
    recoveryToken = params.get("access_token");
    history.replaceState(null, "", window.location.pathname); // take the token out of the address bar
    showTab("employment");
    showEmploymentView("workerAuthBox");
    showAuthForm("resetPasswordForm");
    return true;
  }

  return false;
}

function restoreEmploymentSession() {
  const workerToken = localStorage.getItem("workerToken");

  if (workerToken) {
    document.getElementById("workerDashName").textContent = localStorage.getItem("workerName") || "";
    showEmploymentView("workerProfileBox");
    loadMyProfile();
  } else {
    showEmploymentView("publicFeedView");
  }
  loadPublicFeed();
}


// ================= EMPLOYMENT: PUBLIC FEED =================

async function loadPublicFeed() {
  const result = await safeFetch(`${API_URL}/workers`);
  const feedList = document.getElementById("workerFeedList");

  if (!result.ok || result.data.workers.length === 0) {
    feedList.innerHTML = "<p>📋 No one has registered yet. Be the first!</p>";
    return;
  }

  feedList.innerHTML = "";
  result.data.workers.forEach(function (worker) {
    const initial = worker.name.trim().charAt(0).toUpperCase();
    const skillTags = worker.skills.split(",").map(function (s) {
      return `<span class="skill-tag">${s.trim()}</span>`;
    }).join("");

    const post = document.createElement("div");
    post.className = "worker-post";
    post.innerHTML = `
      <div class="worker-post-header">
        <div class="worker-avatar">${initial}</div>
        <div>
          <div class="worker-post-name">${worker.name}</div>
          <div class="worker-post-location">📍 ${worker.location}</div>
        </div>
      </div>
      ${worker.bio ? `<div class="worker-post-bio">${worker.bio}</div>` : ""}
      <div class="worker-post-skills">${skillTags}</div>
      <a class="call-btn" href="tel:${worker.phone}">📞 Call ${worker.phone}</a>`;
    feedList.appendChild(post);
  });
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
    bio: document.getElementById("workerRegBio").value,
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
  showEmploymentView("workerProfileBox");
  loadMyProfile();
  loadPublicFeed();
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
  showEmploymentView("workerProfileBox");
  loadMyProfile();
});

document.getElementById("workerLogoutBtn").addEventListener("click", function () {
  localStorage.removeItem("workerToken");
  localStorage.removeItem("workerName");
  showEmploymentView("publicFeedView");
});


// ================= EMPLOYMENT: MY PROFILE (edit / delete) =================

async function loadMyProfile() {
  const token = localStorage.getItem("workerToken");
  const result = await safeFetch(`${API_URL}/worker/profile`, { headers: { "X-Auth-Token": token } });

  if (!result.ok) return;

  const profile = result.data.profile;
  document.getElementById("workerEditName").value = profile.name;
  document.getElementById("workerEditPhone").value = profile.phone;
  document.getElementById("workerEditLocation").value = profile.location;
  document.getElementById("workerEditSkills").value = profile.skills;
  document.getElementById("workerEditBio").value = profile.bio;
}

document.getElementById("workerEditForm").addEventListener("submit", async function (event) {
  event.preventDefault();
  const token = localStorage.getItem("workerToken");

  const requestData = {
    name: document.getElementById("workerEditName").value,
    phone: document.getElementById("workerEditPhone").value,
    location: document.getElementById("workerEditLocation").value,
    skills: document.getElementById("workerEditSkills").value,
    bio: document.getElementById("workerEditBio").value,
  };

  const result = await safeFetch(`${API_URL}/worker/profile`, {
    method: "PUT", headers: { "Content-Type": "application/json", "X-Auth-Token": token },
    body: JSON.stringify(requestData),
  });

  if (!result.ok) {
    showResult("workerEditResult", result.errorMessage, "error");
    return;
  }

  localStorage.setItem("workerName", requestData.name);
  document.getElementById("workerDashName").textContent = requestData.name;
  showResult("workerEditResult", "✅ Profile updated - the feed now shows your changes.", "success");
  loadPublicFeed();
});

document.getElementById("deleteProfileBtn").addEventListener("click", async function () {
  if (!confirm("Delete your profile? It will be removed from the public feed.")) return;

  const token = localStorage.getItem("workerToken");
  await safeFetch(`${API_URL}/worker/profile`, { method: "DELETE", headers: { "X-Auth-Token": token } });

  localStorage.removeItem("workerToken");
  localStorage.removeItem("workerName");
  showEmploymentView("publicFeedView");
  loadPublicFeed();
});


// ================= ADMIN PANEL =================

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

  const result = await safeFetch(`${API_URL}/admin/workers`, { headers });

  document.getElementById("adminStatsBar").innerHTML =
    `<div class="stat-box"><span class="stat-number">${result.ok ? result.data.workers.length : "-"}</span><span class="stat-label">Registered Workers</span></div>`;

  const workersList = document.getElementById("adminWorkersList");
  workersList.innerHTML = "";

  if (result.ok && result.data.workers.length > 0) {
    result.data.workers.forEach(function (worker) {
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
        if (!confirm("Remove this worker's profile from the platform?")) return;
        await safeFetch(`${API_URL}/admin/workers/${btn.dataset.id}`, { method: "DELETE", headers });
        loadAdminDashboard();
      });
    });
  } else {
    workersList.innerHTML = "<p>No workers registered yet.</p>";
  }

  const activityResult = await safeFetch(`${API_URL}/admin/activity`, { headers });
  const activityLabels = {
    crop_prediction: "Crop Recommendations", telemedicine_query: "Telemedicine Queries",
    scheme_check: "Scheme Checks", water_check: "Water Checks",
    disaster_check: "Disaster Checks", chat_message: "Chat Messages",
  };
  const activityBar = document.getElementById("adminActivityBar");
  if (activityResult.ok) {
    const activity = activityResult.data.activity;
    activityBar.innerHTML = Object.keys(activityLabels).map(function (key) {
      return `<div class="stat-box"><span class="stat-number">${activity[key] || 0}</span><span class="stat-label">${activityLabels[key]}</span></div>`;
    }).join("");
  } else {
    activityBar.innerHTML = "";
  }
}


// ================= FLOATING ASSISTANT WIDGET =================

const chatBubble = document.getElementById("chatBubble");
const chatPanel = document.getElementById("chatPanel");

chatBubble.addEventListener("click", function () { chatPanel.classList.toggle("open"); });
document.getElementById("chatCloseBtn").addEventListener("click", function () { chatPanel.classList.remove("open"); });

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
