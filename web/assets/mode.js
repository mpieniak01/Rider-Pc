import { initI18n, applyDom, t } from "/web/assets/i18n.js";

const urlLang = new URLSearchParams(location.search).get("lang");
const saved = localStorage.getItem("lang");
const browser = (navigator.language || "").slice(0, 2).toLowerCase();
const pick = (val) => (val && val.toLowerCase().startsWith("en")) ? "en" : (val && val.toLowerCase().startsWith("pl")) ? "pl" : null;
const lang = pick(urlLang) || pick(saved) || pick(browser) || "pl";
if (urlLang) {
  localStorage.setItem("lang", lang);
}

await initI18n(lang);
applyDom();
document.documentElement.setAttribute("lang", lang);
document.title = t("mode.page_title");

const qs = (sel) => document.querySelector(sel);

function formatHttpError(status, statusText, raw) {
  const txt = (raw || "").trim();
  if (!txt) return `HTTP ${status} :: ${statusText || "error"}`;
  const stripped = txt.replace(/<[^>]*>/g, " ").replace(/\s+/g, " ").trim();
  const preview = stripped || statusText || "error";
  return `HTTP ${status} :: ${preview.slice(0, 140)}`;
}

async function fetchJson(url, options = {}) {
  const r = await fetch(url, { cache: "no-store", ...options });
  const raw = await r.text();
  if (!r.ok) {
    throw new Error(formatHttpError(r.status, r.statusText, raw));
  }
  return raw ? JSON.parse(raw) : {};
}

async function sendJson(url, body, method = "POST") {
  const r = await fetch(url, {
    method,
    headers: { "Content-Type": "application/json" },
    body: body ? JSON.stringify(body) : undefined,
    cache: "no-store",
  });
  const raw = await r.text();
  if (!r.ok) {
    let message;
    try {
      const j = raw ? JSON.parse(raw) : {};
      message = j.error || j.stderr || j.stdout;
    } catch {
      /* ignore */
    }
    throw new Error(message || formatHttpError(r.status, r.statusText, raw));
  }
  return raw ? JSON.parse(raw) : {};
}

function pingHealth() {
  fetch("/healthz", { cache: "no-store" })
    .then((r) => r.json().catch(() => ({})))
    .then((j) => {
      const el = qs("#apiStatus");
      if (!el) return;
      const ok = !!j.ok;
      el.textContent = ok ? t("header.api_status_ok") : t("header.api_status_degraded");
      el.className = ok ? "ok" : "warn";
    })
    .catch(() => {
      const el = qs("#apiStatus");
      if (!el) return;
      el.textContent = t("header.api_status_down");
      el.className = "err";
    });
}

pingHealth();
setInterval(pingHealth, 1500);

const AI_MODE_ENDPOINT = "/api/system/ai-mode";
const PROVIDER_STATE_ENDPOINT = "/api/providers/state";
const PROVIDER_DOMAINS = ["vision", "voice", "text"];

function providerModeLabel(mode) {
  return mode === "pc" ? t("provider.mode_pc") : t("provider.mode_local");
}

function providerStatusLabel(status) {
  if (!status) return t("provider.status_unknown");
  const key = `provider.status_${status}`;
  const text = t(key);
  return typeof text === "string" && text !== key ? text : `${t("provider.status_unknown")} (${status})`;
}

function formatChangedTs(ts) {
  if (!ts || Number.isNaN(Number(ts))) {
    return t("provider.changed_unknown");
  }
  try {
    return new Date(Number(ts) * 1000).toLocaleTimeString();
  } catch {
    return t("provider.changed_unknown");
  }
}

function updateProviderPcBadge(health = {}) {
  const badge = qs("#providerPcStatus");
  if (!badge) return;
  let cls = "warn";
  let key = "provider.pc_status_unknown";
  if (health.reachable && health.status === "online") {
    cls = "ok";
    key = "provider.pc_status_online";
  } else if (health.status === "offline") {
    cls = "err";
    key = "provider.pc_status_offline";
  } else if (health.reason === "not_initialized") {
    key = "provider.pc_status_pending";
  }
  const latency = typeof health.latency_ms === "number" ? ` (${Math.round(health.latency_ms)} ms)` : "";
  badge.className = `c-pill ${cls}`;
  badge.textContent = `${t(key)}${latency}`;
}

function renderProviderDomain(domain, state = {}) {
  const row = document.querySelector(`.provider-row[data-provider="${domain}"]`);
  if (!row) return;
  const pill = row.querySelector("[data-provider-pill]");
  if (pill) {
    pill.textContent = providerModeLabel(state.mode);
    pill.className = `c-pill provider-pill ${state.mode === "pc" ? "warn" : "ok"}`;
  }
  const statusEl = row.querySelector("[data-provider-status]");
  if (statusEl) {
    const label = providerStatusLabel(state.status);
    const reason = state.reason ? ` (${state.reason})` : "";
    statusEl.textContent = `${label}${reason}`;
  }
  const changedEl = row.querySelector("[data-provider-changed]");
  if (changedEl) {
    changedEl.textContent = formatChangedTs(state.changed_ts);
  }
}

async function fetchAiModeStatus() {
  try {
    const data = await fetchJson(AI_MODE_ENDPOINT);
    const badge = qs("#aiModeCurrentBadge");
    const status = qs("#aiModeStatus");
    const ts = qs("#aiModeChangedTime");
    if (badge) {
      badge.classList.remove("warn", "ok");
      badge.classList.add(data.mode === "pc_offload" ? "warn" : "ok");
      badge.textContent = data.mode === "pc_offload" ? "PC Offload" : "Local";
    }
    if (status) {
      const label = data.error
        ? t("ai_mode.status_error", { error: data.error })
        : t("ai_mode.status_active", { mode: data.mode === "pc_offload" ? "PC Offload" : "Local" });
      status.textContent = label;
    }
    const changed = data.changed_ts ?? data.ts;
    if (ts && changed) {
      ts.textContent = new Date(changed * 1000).toLocaleTimeString();
    }
  } catch (err) {
    console.warn("AI mode fetch failed", err);
  }
}

async function setAiMode(mode) {
  try {
    await sendJson(AI_MODE_ENDPOINT, { mode }, "PUT");
    await fetchAiModeStatus();
  } catch (err) {
    console.error("AI mode update failed", err);
  }
}

qs("#btnAiModeLocal")?.addEventListener("click", () => setAiMode("local"));
qs("#btnAiModeOffload")?.addEventListener("click", () => setAiMode("pc_offload"));

async function fetchProviderState() {
  try {
    const data = await fetchJson(PROVIDER_STATE_ENDPOINT);
    const domains = data.domains || {};
    PROVIDER_DOMAINS.forEach((domain) => {
      renderProviderDomain(domain, domains[domain] || {});
    });
    updateProviderPcBadge(data.pc_health);
  } catch (err) {
    console.warn("Provider state fetch failed", err);
  }
}

async function setProviderMode(domain, target) {
  try {
    await sendJson(`/api/providers/${domain}`, { target }, "PATCH");
    await fetchProviderState();
  } catch (err) {
    console.error("Provider switch failed", err);
  }
}

document.querySelectorAll("[data-provider-action]").forEach((btn) => {
  btn.addEventListener("click", () => {
    const domain = btn.getAttribute("data-provider-domain");
    const target = btn.getAttribute("data-provider-action");
    if (!domain || !target) return;
    setProviderMode(domain, target);
  });
});

fetchAiModeStatus();
fetchProviderState();
setInterval(() => {
  fetchProviderState().catch(() => {});
}, 7000);
