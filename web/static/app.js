// Crop Shift frontend — field pin, soil inputs, priorities, What-If, C9 assistant
const $ = (id) => document.getElementById(id);
const API = "";

let lang = "en";
let map, marker;
let lastResult = null;
let marsMode = false;
let activePreset = null;

// Keys must match the backend Priority enum values
const PRIOS = [
  { key: "yield", en: "Income / yield", bn: "আয় / ফলন" },
  { key: "soil_health", en: "Soil health", bn: "মাটির স্বাস্থ্য" },
  { key: "water_conservation", en: "Save water", bn: "পানি বাঁচান" },
  { key: "risk_reduction", en: "Low risk", bn: "কম ঝুঁকি" },
  { key: "profitability", en: "Profit", bn: "লাভ" },
  { key: "climate_adaptation", en: "Climate-proof", bn: "জলবায়ু সহনশীল" },
];

const I18N = {
  en: {
    tagline: "Farm Future Simulator", s1: "Scan", s2: "Plan", s3: "Simulate", s4: "Result", s5: "Learn",
    liveData: "Fetched live from NASA POWER for your pin.",
    farmTitle: "Your field", farmHint: "Drop a pin on your field. NASA POWER data loads for that exact location.",
    soilTitle: "Soil and water", soilType: "Soil type", waterSrc: "Water source", soc: "Organic matter", history: "Crops grown recently",
    prioTitle: "Your priorities", prioHint: "Weight each factor. The ranking follows what matters to you.",
    whatif: "What if", whatifHint: "Shift the weather forward and see which rotation still holds.",
    pDrought: "Drought year", pHeat: "Heat", pFlood: "Heavy rain", pSalt: "Salinity", pReset: "Reset",
    temp: "Temperature", rain: "Rainfall", seasons: "Seasons", run: "Simulate my farm",
    loading: "Loading NASA weather data for your field…",
    rankTitle: "Rotation ranking", insights: "Insights", risks: "Risks", compare: "Compare rotations",
    emptyTitle: "Your field report is one click away", emptySub: "Drop a pin, set your priorities, then run the simulation. Turn on What-If to test future weather.",
    nasaTitle: "Live NASA data", c9sub: "Farm assistant",
    bestRotation: "Best rotation", rewind: "Back to baseline", stress: "Stress test +2°C",
  },
  bn: {
    tagline: "ফার্ম ফিউচার সিমুলেটর", s1: "স্ক্যান", s2: "পরিকল্পনা", s3: "সিমুলেট", s4: "ফলাফল", s5: "শিখুন",
    liveData: "আপনার পিনের অবস্থানের জন্য সরাসরি নাসা পাওয়ার থেকে আনা তথ্য।",
    farmTitle: "আপনার জমি", farmHint: "মানচিত্রে পিন দিন। ওই জায়গার জন্য নাসা পাওয়ারের তথ্য আনা হবে।",
    soilTitle: "মাটি ও পানি", soilType: "মাটির ধরন", waterSrc: "পানির উৎস", soc: "জৈব পদার্থ", history: "সম্প্রতি চাষ করা ফসল",
    prioTitle: "আপনার অগ্রাধিকার", prioHint: "প্রতিটি বিষয়ের ওজন ঠিক করুন। র‍্যাংকিং আপনার পছন্দ অনুসরণ করবে।",
    whatif: "যদি এমন হতো", whatifHint: "আবহাওয়া এগিয়ে নিয়ে দেখুন কোন রোটেশন এখনও টিকে থাকে।",
    pDrought: "খরার বছর", pHeat: "তাপ", pFlood: "ভারী বৃষ্টি", pSalt: "লবণাক্ততা", pReset: "রিসেট",
    temp: "তাপমাত্রা", rain: "বৃষ্টি", seasons: "মৌসুম", run: "আমার খামার সিমুলেট করুন",
    loading: "আপনার জমির জন্য নাসা আবহাওয়া তথ্য আনা হচ্ছে…",
    rankTitle: "রোটেশন র‍্যাংকিং", insights: "পরামর্শ", risks: "ঝুঁকি", compare: "তুলনা",
    emptyTitle: "এক ক্লিকেই আপনার মাঠের রিপোর্ট", emptySub: "পিন দিন, অগ্রাধিকার ঠিক করুন, তারপর সিমুলেট চালান। What-If চালু করে ভবিষ্যতের আবহাওয়া পরীক্ষা করুন।",
    nasaTitle: "লাইভ নাসা ডেটা", c9sub: "খামার সহকারী",
    bestRotation: "সেরা রোটেশন", rewind: "আগের অবস্থায়", stress: "+2°C চাপ পরীক্ষা",
  },
};

function t(key) { return (I18N[lang] && I18N[lang][key]) || I18N.en[key] || key; }

function applyLang() {
  document.querySelectorAll("[data-i18n]").forEach((el) => {
    const k = el.getAttribute("data-i18n");
    if (I18N[lang][k]) el.textContent = I18N[lang][k];
  });
  $("langToggle").textContent = lang === "en" ? "বাংলা" : "English";
  refreshIcons();
  renderPriorities();
  if (lastResult) c9Say(initialC9(lastResult), false);
}


let toastTimer;
function toast(message, sub, isError) {
  const el = $("toast");
  el.innerHTML = "";
  const title = document.createElement("strong");
  title.textContent = message;
  el.appendChild(title);
  if (sub) {
    const meta = document.createElement("span");
    meta.textContent = sub;
    el.appendChild(meta);
  }
  el.classList.toggle("is-error", !!isError);
  el.classList.add("is-visible");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => el.classList.remove("is-visible"), isError ? 7000 : 4000);
}


function paintRange(input) {
  const min = parseFloat(input.min || "0");
  const max = parseFloat(input.max || "100");
  const pct = ((parseFloat(input.value) - min) / (max - min)) * 100;
  input.style.setProperty("--p", pct.toFixed(2) + "%");
}

document.addEventListener("input", (e) => {
  const el = e.target;
  if (el.type !== "range") return;
  paintRange(el);
  if (["tempChange", "rainChange"].includes(el.id)) clearPreset();
});


function initMap() {
  const lat = parseFloat($("lat").value);
  const lon = parseFloat($("lon").value);
  map = L.map("map").setView([lat, lon], 7);
  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", { maxZoom: 18 }).addTo(map);
  marker = L.marker([lat, lon], { draggable: true }).addTo(map);
  marker.on("dragend", () => syncCoordinates());
  map.on("click", (e) => {
    marker.setLatLng(e.latlng);
    syncCoordinates();
  });
  syncCoordinates();
}

// Reflect the pin position back into the lat/lon inputs
function syncCoordinates() {
  const p = marker.getLatLng();
  $("lat").value = p.lat.toFixed(4);
  $("lon").value = p.lng.toFixed(4);
}


function renderPriorities() {
  const box = $("priorities");
  box.innerHTML = "";
  PRIOS.forEach((p) => {
    const row = document.createElement("div");
    row.className = "prow";
    const label = lang === "bn" ? p.bn : p.en;
    row.innerHTML =
      `<span class="prow__head">${label} <b class="prow__value" id="pv-${p.key}">20%</b></span>
       <input type="range" min="0" max="60" value="20" data-prio="${p.key}" aria-label="${label}">`;
    box.appendChild(row);
  });
  box.querySelectorAll("input").forEach((inp) => {
    paintRange(inp);
    inp.addEventListener("input", () => {
      $("pv-" + inp.dataset.prio).textContent = inp.value + "%";
    });
  });
}

function getPriorities() {
  const out = {};
  document.querySelectorAll("#priorities input").forEach((inp) => {
    out[inp.dataset.prio] = parseFloat(inp.value) / 100;
  });
  // The backend re-weights these, but they must sum to 1.0 to be meaningful
  const sum = Object.values(out).reduce((a, b) => a + b, 0) || 1;
  Object.keys(out).forEach((k) => (out[k] = +(out[k] / sum).toFixed(3)));
  return out;
}

function setStep(n) {
  document.querySelectorAll(".step").forEach((s) => {
    const i = +s.dataset.step;
    s.classList.toggle("is-active", i === n);
    s.classList.toggle("is-done", i < n);
  });
}


const PRESETS = {
  drought: { temp: 1.5, rain: -30 },
  heat: { temp: 2.0, rain: -10 },
  flood: { temp: 0.5, rain: 30 },
  salinity: { temp: 1.0, rain: -20 },
  reset: { temp: 0, rain: 0 },
};

function clearPreset() {
  activePreset = null;
  document.querySelectorAll("[data-preset]").forEach((b) => b.classList.remove("is-on"));
}

document.querySelectorAll("[data-preset]").forEach((btn) => {
  btn.addEventListener("click", () => {
    const p = PRESETS[btn.dataset.preset];
    $("tempChange").value = p.temp;
    $("rainChange").value = p.rain;
    $("scenarioOn").checked = !(p.temp === 0 && p.rain === 0);
    activePreset = btn.dataset.preset;
    document.querySelectorAll("[data-preset]").forEach((b) => b.classList.remove("is-on"));
    btn.classList.add("is-on");
    syncLabels();
  });
});

function syncLabels() {
  const t = +$("tempChange").value;
  $("tempVal").textContent = (t > 0 ? "+" : "") + t.toFixed(1) + "°C";
  const r = +$("rainChange").value;
  $("rainVal").textContent = (r > 0 ? "+" : "") + r + "%";
  $("phVal").textContent = (+$("soilPh").value).toFixed(1);
  $("socVal").textContent = (+$("soilSoc").value).toFixed(1) + "%";
}

["tempChange", "rainChange", "soilPh", "soilSoc"].forEach((id) => {
  $(id).addEventListener("input", syncLabels);
  paintRange($(id));
});


function c9Say(text, readAloud = true) {
  const box = $("chat");
  const div = document.createElement("div");
  div.className = "msg c9";
  div.innerHTML = text;
  box.appendChild(div);
  box.scrollTop = box.scrollHeight;
  if (readAloud) speak(text.replace(/<[^>]*>/g, ""));
}

function meSay(text) {
  const box = $("chat");
  const div = document.createElement("div");
  div.className = "msg me";
  div.textContent = text;
  box.appendChild(div);
  box.scrollTop = box.scrollHeight;
}

let voiceOn = false;
function speak(text) {
  try {
    if (!("speechSynthesis" in window)) return;
    if (!voiceOn && document.activeElement !== $("voiceBtn")) return;
    const u = new SpeechSynthesisUtterance(text.slice(0, 280));
    u.lang = lang === "bn" ? "bn-BD" : "en-US";
    speechSynthesis.cancel();
    speechSynthesis.speak(u);
  } catch (e) { /* ignore */ }
}

function refreshIcons() {
  if (window.lucide) lucide.createIcons();
}

$("voiceBtn").addEventListener("click", () => {
  voiceOn = !voiceOn;
  $("voiceBtn").classList.toggle("is-on", voiceOn);
  meSay(voiceOn ? "Voice on" : "Voice off");
});

function initialC9(res) {
  const b = res.best_rotation;
  const seq = b.crops.join(" → ");
  if (lang === "bn") {
    return `<b>সালাম! আমি C9।</b><br>আপনার জমির জন্য সেরা রোটেশন: <b>${seq}</b> — স্কোর ${b.overall_score.toFixed(0)}/100।<br>• ${b.details.soil_health.total_n_balance_kg_ha > 0 ? "ডাল ফসল মাটিতে নাইট্রোজেন যোগ করবে।" : "নাইট্রোজেনের জন্য সার লাগতে পারে।"}<br>What-If চালু করে +2°C / −20% বৃষ্টিতে পরীক্ষা করে দেখুন।`;
  }
  return `<b>Hi, I'm C9.</b><br>Best rotation for your field: <b>${seq}</b> — score ${b.overall_score.toFixed(0)}/100.<br>• ${b.details.soil_health.total_n_balance_kg_ha > 0 ? "Legumes add nitrogen to your soil." : "You may need extra nitrogen fertilizer."}<br>Flip the What-If toggle to stress-test at +2°C / −20% rain.`;
}

function c9Answer(q, res) {
  if (!res) return lang === "bn" ? "আগে সিমুলেট চালান, তারপর জিজ্ঞেস করুন।" : "Run a simulation first, then ask me.";
  const b = res.best_rotation;
  q = q.toLowerCase();
  if (q.includes("water") || q.includes("পানি")) {
    const w = b.details.water;
    return lang === "bn"
      ? `পানির চাহিদা বছরে ~${w.avg_annual_need_mm}mm। খরা সহনশীলতা ${w.avg_drought_tolerance}/5। বৃষ্টি কমলে ডাল + কভার ক্রপ বেছে নিন।`
      : `Annual need ~${w.avg_annual_need_mm}mm. Drought tolerance ${w.avg_drought_tolerance}/5. If rain drops, lean on legumes + cover crops.`;
  }
  if (q.includes("soil") || q.includes("মাটি")) {
    const s = b.details.soil_health;
    return lang === "bn"
      ? `মাটির স্কোর ${b.priority_scores.soil_health?.toFixed(0)}/100। নাইট্রোজেন ব্যালেন্স ${s.total_n_balance_kg_ha} kg/ha। ডাল ও কভার ক্রপ জৈব পদার্থ বাড়ায়।`
      : `Soil score ${b.priority_scores.soil_health?.toFixed(0)}/100. N balance ${s.total_n_balance_kg_ha} kg/ha. Legumes + cover crops build organic matter.`;
  }
  if (q.includes("mars") || q.includes("মঙ্গল")) {
    return lang === "bn"
      ? `মঙ্গলে বৃষ্টি নেই, তাপমাত্রা −60°C। ডোমের ভেতর শিম + ঢেঁড়স জাতীয় কম পানির ফসলই টিকবে।`
      : `Mars: no rain, −60°C outside. Inside a dome, low-water legumes + hardy cereals win. Try Mars Mode →`;
  }
  const seq = b.crops.join(" → ");
  const lead = plain(res.insights[0] || "");
  return lang === "bn"
    ? `সেরা রোটেশন: <b>${seq}</b> (${b.overall_score.toFixed(0)}/100)। ${lead}`
    : `Best rotation: <b>${seq}</b> (${b.overall_score.toFixed(0)}/100). ${lead}`;
}


let simulateInFlight = false;

$("runBtn").addEventListener("click", async () => {
  if (simulateInFlight) return;
  simulateInFlight = true;
  $("runBtn").disabled = true;
  setStep(3);
  $("empty").classList.add("hidden");
  $("results").classList.add("hidden");
  $("loading").classList.remove("hidden");

  const lat = parseFloat($("lat").value);
  const lon = parseFloat($("lon").value);
  if (!Number.isFinite(lat) || !Number.isFinite(lon) || Math.abs(lat) > 90 || Math.abs(lon) > 180) {
    $("loading").classList.add("hidden");
    $("empty").classList.remove("hidden");
    toast(lang === "bn" ? "স্থানাঙ্গ মান সঠিক নয়" : "Those coordinates are not valid",
      "Latitude −90 to 90 · longitude −180 to 180", true);
    simulateInFlight = false;
    $("runBtn").disabled = false;
    return;
  }

  const farm = {
    latitude: lat,
    longitude: lon,
    farm_name: $("farmName").value.trim() || "My Farm",
    soil_texture: $("soilTexture").value,
    soil_ph: parseFloat($("soilPh").value),
    soil_organic_carbon: parseFloat($("soilSoc").value),
    water_source: $("waterSource").value,
    crop_history: $("cropHistory").value.split(",").map((s) => s.trim()).filter(Boolean),
    priorities: getPriorities(),
  };

const useScenario = $("scenarioOn").checked;
  // The backend caps precipitation change at -50%; Mars Dome is pushed to that limit
  const MARS = { temperature_change_c: 2.5, precipitation_change_pct: -50 };
  let scenario = null;
  if (useScenario) {
    scenario = {
      temperature_change_c: parseFloat($("tempChange").value),
      precipitation_change_pct: parseFloat($("rainChange").value),
      scenario_name: "What-If",
    };
    if (marsMode) Object.assign(scenario, MARS);
  } else if (marsMode) {
    scenario = { ...MARS, scenario_name: "Mars Dome" };
  }

  try {
    const resp = await fetch(API + "/api/simulate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ farm, scenario, rotation_years: +$("years").value, max_recommendations: 5 }),
    });
    if (!resp.ok) {
      let msg = "Backend error " + resp.status;
      try {
        const err = await resp.json();
        if (err && err.detail) msg = typeof err.detail === "string" ? err.detail : JSON.stringify(err.detail);
      } catch (_) { /* non-JSON error body */ }
      throw new Error(msg);
    }
    const res = await resp.json();
    if (!res || !res.best_rotation) throw new Error("The backend returned no rotation for this field.");
    lastResult = res;
    render(res, scenario);
    const src = res.data_source || {};
    toast(
      `${res.recommendations.length} rotations scored`,
      `${src.provider || "NASA POWER"} · ${src.period || ""} · ${src.years_with_data ?? "?"} years`
    );
    setStep(4);
    c9Say(initialC9(res));
    setTimeout(() => setStep(5), 1500);
  } catch (e) {
    $("loading").classList.add("hidden");
    $("empty").classList.remove("hidden");
    toast(e.message, "Could not run the simulation", true);
  } finally {
    simulateInFlight = false;
    $("runBtn").disabled = false;
  }
});


// Backend markdown (**bold**) -> HTML
const md = (s) => s.replace(/\*\*(.+?)\*\*/g, "<b>$1</b>");
// The backend decorates its copy with emoji; the UI marks lists typographically instead
const plain = (s) => s.replace(/^[\p{Extended_Pictographic}\p{Emoji_Presentation}\uFE0F\u200D\s]+/u, "");
const n1 = (v) => (v == null ? "—" : v.toFixed(1));
const n0 = (v) => (v == null ? "—" : v.toFixed(0));

function render(res, scenario) {
  $("loading").classList.add("hidden");
  $("results").classList.remove("hidden");

  const b = res.best_rotation;
  const seq = b.crops.join(" → ");
  const ds = res.data_source || {};

  $("bestBanner").innerHTML = `
    <div class="verdict__top">
      <div>
        <p class="verdict__label">${t("bestRotation")}</p>
        <p class="verdict__crops">${seq}</p>
        <p class="verdict__meta">${res.farm_name} · ${res.location.latitude.toFixed(2)}, ${res.location.longitude.toFixed(2)}
          ${scenario ? ` · What-If ${scenario.temperature_change_c > 0 ? "+" : ""}${scenario.temperature_change_c}°C, ${scenario.precipitation_change_pct}% rain` : ""}
          ${ds.provider ? ` · ${ds.provider} ${ds.period} (${ds.years_with_data} years)` : ""}</p>
      </div>
      <p class="verdict__score">${b.overall_score.toFixed(0)}<small> / 100</small></p>
    </div>
    <div class="verdict__actions">
      <button class="btn btn--ghost" type="button" id="rewindBtn">${t("rewind")}</button>
      <button class="btn btn--ghost" type="button" id="stressBtn">${t("stress")}</button>
    </div>`;

  $("rewindBtn").addEventListener("click", () => {
    $("scenarioOn").checked = false;
    $("tempChange").value = 0;
    $("rainChange").value = 0;
    clearPreset();
    syncLabels();
    $("runBtn").click();
  });
  $("stressBtn").addEventListener("click", () => {
    $("scenarioOn").checked = true;
    $("tempChange").value = 2;
    $("rainChange").value = -20;
    clearPreset();
    syncLabels();
    $("runBtn").click();
  });

  // Ranked rotations
  const box = $("rotationCards");
  box.innerHTML = res.recommendations.map((r, i) => {
    const bars = [
      ["Yield", r.priority_scores.yield], ["Soil", r.priority_scores.soil_health],
      ["Water", r.priority_scores.water_conservation], ["Low risk", r.priority_scores.risk_reduction],
      ["Profit", r.priority_scores.profitability], ["Climate-proof", r.priority_scores.climate_adaptation],
    ].filter(([, v]) => typeof v === "number").map(([k, v]) => `
      <div class="bar"><span>${k}</span>
        <span class="bar__track"><span class="bar__fill" style="width:${Math.max(0, Math.min(100, v))}%"></span></span>
        <span class="bar__value">${v.toFixed(0)}</span></div>`).join("");
    const nitrogen = r.details.soil_health.total_n_balance_kg_ha;
    const water = r.details.water.avg_annual_need_mm;
    const profit = r.details.economic.avg_annual_profit_usd_ha;
    return `<article class="rcard${i === 0 ? " is-top" : ""}">
      <span class="rcard__rank">${String(i + 1).padStart(2, "0")}</span>
      <div>
        <p class="rcard__crops">${r.crops.join(" → ")}</p>
        <p class="rcard__meta">N ${nitrogen != null ? (nitrogen > 0 ? "+" : "") + nitrogen.toFixed(0) : "—"} kg/ha · ${water != null ? water.toFixed(0) + "mm water/yr" : "water —"} · ${profit != null ? "$" + profit.toFixed(0) + "/ha" : "profit —"}</p>
      </div>
      <span class="rcard__score">${r.overall_score.toFixed(0)}</span>
      <div class="bars">${bars}</div>
    </article>`;
  }).join("");

  if (marsMode && !$("marsCard").classList.contains("hidden")) {
    $("marsOut").innerHTML = `Best under dome stress: <b>${b.crops.join(" → ")}</b> (${b.overall_score.toFixed(0)}/100).`;
  }

  $("insights").innerHTML = res.insights.map((s) => `<li>${md(plain(s))}</li>`).join("");
  $("warnings").innerHTML = res.warnings.map((s) => `<li>${md(plain(s))}</li>`).join("");

  const keys = ["yield", "soil_health", "water_conservation", "risk_reduction", "profitability", "climate_adaptation"];
  const names = ["Yield", "Soil", "Water", "Risk", "Profit", "Climate"];
  $("compareTable").innerHTML =
    "<thead><tr><th>Rotation</th><th>Overall</th>" + names.map((c) => `<th>${c}</th>`).join("") + "</tr></thead><tbody>" +
    res.recommendations.map((r, i) =>
      `<tr><td${i === 0 ? ' class="is-lead"' : ""}>${r.crops.join(" → ")}</td><td>${r.overall_score.toFixed(0)}</td>` +
      keys.map((k) => `<td>${r.priority_scores[k] == null ? "—" : Math.round(r.priority_scores[k])}</td>`).join("") +
      `</tr>`
    ).join("") + "</tbody>";

  // Climate strip
  const bc = res.baseline_climate;
  const sc = res.scenario_climate;
  const stats = [
    ["Avg temp", n1(bc.mean_temp) + "°C"],
    ["Rainfall", n0(bc.total_precipitation) + "mm"],
    ["Heat days", bc.heat_stress_days ?? "—"],
    ["Growing degree days", bc.growing_degree_days ?? "—"],
  ];
  if (sc) stats.push(["What-If", n1(sc.mean_temp) + "°C · " + n0(sc.total_precipitation) + "mm"]);

  $("climateStrip").innerHTML = stats.map(([k, v]) =>
    `<div class="stat"><span class="stat__label">${k}</span><span class="stat__value">${v}</span></div>`
  ).join("");
  $("climateStrip").classList.remove("hidden");

  // Live source readout
  const rows = [
    ["Provider", ds.provider || "NASA POWER"],
    ["Period", ds.period || "—"],
    ["Avg temp / rain", `${n1(bc.mean_temp)}°C · ${n0(bc.total_precipitation)}mm`],
    ["Hottest / coldest", `${n1(bc.max_temp)}°C · ${n1(bc.min_temp)}°C`],
    ["Mean humidity", n0(bc.mean_humidity) + "%"],
    ["Growing / heat / frost days", `${bc.growing_degree_days ?? "—"} · ${bc.heat_stress_days ?? "—"} · ${bc.frost_days ?? "—"}`],
    ["Reference ET (Hargreaves)", n0(bc.total_pet) + "mm/yr"],
    ["Aridity index", n1(bc.aridity_index)],
  ];
  if (sc) {
    const dt = (sc.mean_temp ?? 0) - (bc.mean_temp ?? 0);
    rows.push(["What-If applied", `${dt > 0 ? "+" : ""}${n1(dt)}°C · ${sc.precipitation_change_pct}% rain`]);
  } else {
    rows.push(["Scenario", "baseline"]);
  }
  $("nasaLive").innerHTML = rows.map(([k, v]) =>
    `<div class="readout__row"><dt class="readout__key">${k}</dt><dd class="readout__val"><b>${v}</b></dd></div>`
  ).join("");
}


$("sendChat").addEventListener("click", () => {
  const q = $("chatText").value.trim();
  if (!q) return;
  meSay(q);
  $("chatText").value = "";
  c9Say(c9Answer(q, lastResult));
});
$("chatText").addEventListener("keydown", (e) => { if (e.key === "Enter") $("sendChat").click(); });
document.querySelectorAll("[data-q]").forEach((btn) => {
  btn.addEventListener("click", () => {
    const q = btn.dataset.q === "best" ? "best rotation?" : btn.dataset.q === "water" ? "save water?" : "soil health?";
    meSay(btn.textContent.trim());
    c9Say(c9Answer(q, lastResult));
  });
});


$("langToggle").addEventListener("click", () => {
  lang = lang === "en" ? "bn" : "en";
  document.documentElement.lang = lang;
  applyLang();
});

$("marsToggle").addEventListener("click", () => {
  marsMode = !marsMode;
  $("marsToggle").classList.toggle("on", marsMode);
  $("marsCard").classList.toggle("hidden", !marsMode);
  c9Say(marsMode
    ? (lang === "bn" ? "<b>মার্স মোড চালু!</b> ডোমের ভেতর চাষ — বৃষ্টি শূন্য, বাইরে −60°C। Mars Dome বোতাম চাপুন।"
                      : "<b>Mars Mode on.</b> Dome farming — zero rain, −60°C outside. Hit the Mars Dome button.")
    : (lang === "bn" ? "পৃথিবীতে ফিরে এলাম।" : "Back on Earth."));
});

$("marsSim").addEventListener("click", () => {
  marsMode = true;
  $("marsToggle").classList.add("on");
  $("marsCard").classList.remove("hidden");
  $("scenarioOn").checked = true;
  $("runBtn").click();
});


initMap();

["lat", "lon"].forEach((id) =>
  $(id).addEventListener("change", () => {
    const la = parseFloat($("lat").value);
    const lo = parseFloat($("lon").value);
    if (Number.isFinite(la) && Number.isFinite(lo) && Math.abs(la) <= 90 && Math.abs(lo) <= 180) {
      marker.setLatLng([la, lo]);
      map.setView([la, lo], map.getZoom());
    }
  })
);

renderPriorities();
syncLabels();
applyLang();
c9Say(lang === "bn"
  ? "<b>সালাম! আমি C9।</b> মানচিত্রে পিন দিন, অগ্রাধিকার ঠিক করুন, তারপর <b>সিমুলেট</b> চাপুন। মাইক বাটনে চাপলে ফলাফল পড়ে শুনাব।"
  : "<b>Hi, I'm C9.</b> Drop a pin, set your priorities, then press <b>Simulate my farm</b>. Tap the mic and I'll read the results aloud.");