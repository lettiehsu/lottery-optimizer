/* ===== UI helpers ===== */

function toast(msg, kind = "ok", ms = 1600) {
  const t = document.createElement("div");
  t.className = `toast ${kind}`;
  t.textContent = msg;
  document.body.appendChild(t);
  setTimeout(() => t.remove(), ms);
}

function busy(btn, on, label = "Working…") {
  if (!btn) return;
  if (on) {
    btn.dataset.old = btn.textContent || btn.value || "";
    if (btn.tagName === "BUTTON") btn.textContent = label;
    if (btn.tagName === "INPUT") btn.value = label;
    btn.disabled = true;
    btn.classList.add("is-busy");
  } else {
    if (btn.tagName === "BUTTON") btn.textContent = btn.dataset.old || "Done";
    if (btn.tagName === "INPUT") btn.value = btn.dataset.old || "Done";
    btn.disabled = false;
    btn.classList.remove("is-busy");
  }
}

async function getJSON(url) {
  const r = await fetch(url);
  return r.json();
}

async function postJSON(url, body) {
  const r = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body || {}),
  });
  return r.json();
}

/* ===== Upload CSV ===== */

const csvFile    = document.getElementById("csvFile");
const overwrite  = document.getElementById("overwrite");
const btnImport  = document.getElementById("btnImport");
const csvLog     = document.getElementById("csvLog");

btnImport?.addEventListener("click", async () => {
  if (!csvFile?.files?.[0]) {
    toast("Choose a CSV file.", "warn");
    return;
  }
  const fd = new FormData();
  fd.append("file", csvFile.files[0]);
  fd.append("overwrite", overwrite?.checked ? "true" : "false");

  busy(btnImport, true, "Uploading…");
  try {
    const r = await fetch("/store/import_csv", { method: "POST", body: fd });
    const data = await r.json();
    const msg = JSON.stringify(data, null, 2);
    if (csvLog) {
      csvLog.textContent = msg;
      csvLog.classList.toggle("ok", !!data.ok);
      csvLog.classList.toggle("err", !data.ok);
    }
    if (!data.ok) throw new Error(data.detail || data.error || "Import failed");
    toast("CSV imported.", "ok");
  } catch (e) {
    if (csvLog) {
      csvLog.textContent = String(e);
      csvLog.classList.add("err");
    }
    toast(String(e), "error", 2600);
  } finally {
    busy(btnImport, false);
  }
});

/* ===== Retrieve per-game (2nd newest) ===== */

async function retrieveOne(btn, game, dateStr, outEl, tier = "") {
  if (!dateStr) { toast("Enter a jackpot date.", "warn"); return; }
  const qs = new URLSearchParams({ game, date: dateStr });
  if (tier) qs.set("tier", tier);
  busy(btn, true, "Retrieving…");
  try {
    const data = await getJSON(`/store/get_by_date?${qs.toString()}`);
    if (!data?.ok) throw new Error(data?.detail || data?.error || "Retrieve failed");
    outEl.value = JSON.stringify(data.row); // [[mains..], bonus|null]
    toast(`${game}${tier ? " " + tier : ""} ready`, "ok");
  } catch (e) {
    outEl.value = "";
    toast(String(e), "error", 2500);
  } finally {
    busy(btn, false);
  }
}

const mmDate      = document.getElementById("mmDate");
const pbDate      = document.getElementById("pbDate");
const ilJPDate    = document.getElementById("ilJPDate");
const ilM1Date    = document.getElementById("ilM1Date");
const ilM2Date    = document.getElementById("ilM2Date");

const mmPreview   = document.getElementById("mmPreview");
const pbPreview   = document.getElementById("pbPreview");
const ilJPPreview = document.getElementById("ilJPPreview");
const ilM1Preview = document.getElementById("ilM1Preview");
const ilM2Preview = document.getElementById("ilM2Preview");

const mmRetrieve  = document.getElementById("mmRetrieve");
const pbRetrieve  = document.getElementById("pbRetrieve");
const ilJPRetrieve= document.getElementById("ilJPRetrieve");
const ilM1Retrieve= document.getElementById("ilM1Retrieve");
const ilM2Retrieve= document.getElementById("ilM2Retrieve");

mmRetrieve?.addEventListener("click", () => retrieveOne(mmRetrieve, "MM", mmDate.value.trim(), mmPreview));
pbRetrieve?.addEventListener("click", () => retrieveOne(pbRetrieve, "PB", pbDate.value.trim(), pbPreview));
ilJPRetrieve?.addEventListener("click", () => retrieveOne(ilJPRetrieve, "IL", ilJPDate.value.trim(), ilJPPreview, "JP"));
ilM1Retrieve?.addEventListener("click", () => retrieveOne(ilM1Retrieve, "IL", ilM1Date.value.trim(), ilM1Preview, "M1"));
ilM2Retrieve?.addEventListener("click", () => retrieveOne(ilM2Retrieve, "IL", ilM2Date.value.trim(), ilM2Preview, "M2"));

/* ===== History “Load 20” (3rd newest) ===== */

function formatHistoryLines(payload) {
  // Accepts either {blob:"..."} or {rows:[{date,mains,bonus},...]}
  if (!payload) return "";
  if (payload.blob && typeof payload.blob === "string") return payload.blob;

  if (Array.isArray(payload.rows)) {
    return payload.rows.map(r => {
      const d = (r.date || r.draw_date || "").trim();  // MM/DD/YYYY
      const [m, d2, y] = d.split("/");
      const mmddyy = (m && d2 && y) ? `${m.padStart(2,"0")}-${d2.padStart(2,"0")}-${y.slice(-2)}` : d;
      const mains = (r.mains || [r.n1, r.n2, r.n3, r.n4, r.n5]).filter(x => x !== undefined && x !== null);
      const bonus = (r.bonus ?? r.mb ?? r.pb ?? null);
      const ms = mains.map(n => String(n).padStart(2,"0")).join("-");
      return bonus == null ? `${mmddyy}  ${ms}` : `${mmddyy}  ${ms}  ${String(bonus).padStart(2,"0")}`;
    }).join("\n");
  }
  return String(payload);
}

async function load20(btn, game, dateStr, outEl, tier = "") {
  if (!dateStr) { toast("Pick the 3rd-newest date first.", "warn"); return; }
  const qs = new URLSearchParams({ game, from: dateStr, limit: "20" });
  if (tier) qs.set("tier", tier);
  busy(btn, true, "Loading…");
  try {
    const data = await getJSON(`/store/get_history?${qs.toString()}`);
    if (!data?.ok) throw new Error(data?.detail || data?.error || "Load failed");
    outEl.value = formatHistoryLines(data);
    toast(`${game}${tier?` ${tier}`:""} — loaded 20`, "ok");
  } catch (e) {
    outEl.value = "";
    toast(String(e), "error", 2600);
  } finally {
    busy(btn, false);
  }
}

const histMMDate  = document.getElementById("histMMDate");
const histPBDate  = document.getElementById("histPBDate");
const histILJPDate= document.getElementById("histILJPDate");
const histILM1Date= document.getElementById("histILM1Date");
const histILM2Date= document.getElementById("histILM2Date");

const histMMBlob  = document.getElementById("histMMBlob");
const histPBBlob  = document.getElementById("histPBBlob");
const histILJPBlob= document.getElementById("histILJPBlob");
const histILM1Blob= document.getElementById("histILM1Blob");
const histILM2Blob= document.getElementById("histILM2Blob");

document.getElementById("btnLoadMM")   ?.addEventListener("click", e => load20(e.currentTarget, "MM", histMMDate.value.trim(),   histMMBlob));
document.getElementById("btnLoadPB")   ?.addEventListener("click", e => load20(e.currentTarget, "PB", histPBDate.value.trim(),   histPBBlob));
document.getElementById("btnLoadIL_JP")?.addEventListener("click", e => load20(e.currentTarget, "IL", histILJPDate.value.trim(), histILJPBlob, "JP"));
document.getElementById("btnLoadIL_M1")?.addEventListener("click", e => load20(e.currentTarget, "IL", histILM1Date.value.trim(), histILM1Blob, "M1"));
document.getElementById("btnLoadIL_M2")?.addEventListener("click", e => load20(e.currentTarget, "IL", histILM2Date.value.trim(), histILM2Blob, "M2"));

/* ===== Run Phase 1 ===== */

const runPhase1   = document.getElementById("runPhase1");
const phase1Path  = document.getElementById("phase1Path");
const phase1Debug = document.getElementById("phase1Debug");

const mmBatch = document.getElementById("mmBatch");
const pbBatch = document.getElementById("pbBatch");
const ilBatch = document.getElementById("ilBatch");

const mmStats = document.getElementById("mmStats");
const pbStats = document.getElementById("pbStats");
const ilStats = document.getElementById("ilStats");

const mmRows  = document.getElementById("mmRows");
const pbRows  = document.getElementById("pbRows");
const ilRows  = document.getElementById("ilRows");

const mmCounts = document.getElementById("mmCounts");
const pbCounts = document.getElementById("pbCounts");
const ilCounts = document.getElementById("ilCounts");

function renderBatch(listEl, batchLines) {
  if (!listEl) return;
  listEl.innerHTML = "";
  (batchLines || []).forEach((line, i) => {
    const li = document.createElement("li");
    li.textContent = `${String(i+1).padStart(2," ")}. ${line}`;
    listEl.appendChild(li);
  });
}
function renderCounts(spanEl, countsObj) {
  if (!spanEl) return;
  if (!countsObj) { spanEl.textContent = ""; return; }
  // MM / PB counts: 3,3+B,4,4+B,5,5+B
  // IL counts: JP_3,JP_4,JP_5,JP_6 etc (we’ll just join)
  const parts = [];
  for (const [k,v] of Object.entries(countsObj)) parts.push(`${k}:${v}`);
  spanEl.textContent = parts.join("  ");
}
function renderRows(preEl, rowsObj) {
  if (!preEl) return;
  const out = [];
  for (const [k, arr] of Object.entries(rowsObj || {})) {
    out.push(`${k}: ${Array.isArray(arr) && arr.length ? arr.join(", ") : "—"}`);
  }
  preEl.textContent = out.join("\n");
}

runPhase1?.addEventListener("click", async () => {
  const payload = {
    phase: "phase1",
    LATEST_MM: mmPreview?.value || "",
    LATEST_PB: pbPreview?.value || "",
    LATEST_IL_JP: ilJPPreview?.value || "",
    LATEST_IL_M1: ilM1Preview?.value || "",
    LATEST_IL_M2: ilM2Preview?.value || "",
    HIST_MM_BLOB: histMMBlob?.value || "",
    HIST_PB_BLOB: histPBBlob?.value || "",
    HIST_IL_JP_BLOB: histILJPBlob?.value || "",
    HIST_IL_M1_BLOB: histILM1Blob?.value || "",
    HIST_IL_M2_BLOB: histILM2Blob?.value || "",
    FEED_MM: document.getElementById("feedMM")?.value || "",
    FEED_PB: document.getElementById("feedPB")?.value || "",
    FEED_IL: document.getElementById("feedIL")?.value || "",
  };

  busy(runPhase1, true, "Running…");
  try {
    const data = await postJSON("/run_json", payload);
    if (!data.ok) throw new Error(data.detail || data.error || "Phase 1 failed");

    // save path
    if (phase1Path && data.saved_path) {
      phase1Path.value = data.saved_path;
    }

    // Optional debug JSON
    if (phase1Debug) {
      phase1Debug.textContent = JSON.stringify(data, null, 2);
    }

    // render MM/PB/IL
    const e = data.echo || {};
    renderBatch(mmBatch, e.BATCH_MM);
    renderBatch(pbBatch, e.BATCH_PB);
    renderBatch(ilBatch, e.BATCH_IL);

    renderCounts(mmCounts, e.HITS_MM?.counts);
    renderCounts(pbCounts, e.HITS_PB?.counts);
    renderCounts(ilCounts, e.HITS_IL_JP?.counts || e.HITS_IL_M1?.counts || e.HITS_IL_M2?.counts);

    renderRows(mmRows, e.HITS_MM?.rows);
    renderRows(pbRows, e.HITS_PB?.rows);

    // For IL we combine the three tiers in one block if present
    const ilOut = [];
    if (e.HITS_IL_JP) ilOut.push("JP", JSON.stringify(e.HITS_IL_JP.rows));
    if (e.HITS_IL_M1) ilOut.push("\nM1", JSON.stringify(e.HITS_IL_M1.rows));
    if (e.HITS_IL_M2) ilOut.push("\nM2", JSON.stringify(e.HITS_IL_M2.rows));
    if (ilRows) ilRows.textContent = ilOut.join(" ");

    toast("Phase 1 complete.", "ok");
  } catch (e) {
    if (phase1Debug) phase1Debug.textContent = String(e);
    toast(String(e), "error", 2800);
  } finally {
    busy(runPhase1, false);
  }
});

/* ===== visual toasts style hook (in case CSS didn’t include) ===== */
(() => {
  if (document.getElementById("toast-style")) return;
  const s = document.createElement("style");
  s.id = "toast-style";
  s.textContent = `
  .toast{position:fixed;right:16px;bottom:16px;background:#111;color:#fff;padding:10px 12px;border-radius:10px;opacity:.95;z-index:9999;box-shadow:0 8px 24px rgba(0,0,0,.2);font:500 14px system-ui}
  .toast.ok{background:#0e7a0d}
  .toast.warn{background:#a66b00}
  .toast.error{background:#b32020}
  .is-busy{opacity:.7}
  `;
  document.head.appendChild(s);
})();
