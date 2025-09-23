// static/app.js

// -------------------- helpers --------------------
const $ = sel => document.querySelector(sel);
const j = (id) => document.getElementById(id);

const HISTORY_URL = "/store/get_history";
const BYDATE_URL  = "/store/get_by_date";
const RUN_URL     = "/core/run";
const IMPORT_URL  = "/store/import_csv";

function toast(msg, type="ok", ms=1800) {
  const t = document.createElement("div");
  t.className = "toast";
  t.style.background = type==="error" ? "#b91c1c" : (type==="warn" ? "#92400e" : "#111");
  t.textContent = msg;
  document.body.appendChild(t);
  setTimeout(()=>t.remove(), ms);
}

function buttonBusy(btn, on, labelWhile) {
  if (!btn) return;
  if (on) {
    btn.dataset._text = btn.textContent;
    btn.textContent = labelWhile || "Working…";
    btn.setAttribute("disabled","disabled");
  } else {
    if (btn.dataset._text) btn.textContent = btn.dataset._text;
    btn.removeAttribute("disabled");
  }
}

async function getJSON(url) {
  const r = await fetch(url, {cache:"no-store"});
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return await r.json();
}
async function postJSON(url, body) {
  const r = await fetch(url, {method:"POST", headers:{ "Content-Type":"application/json" }, body: JSON.stringify(body)});
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return await r.json();
}

// Render helpers
function renderList(ol, arr) {
  ol.innerHTML = "";
  (arr||[]).forEach(s=>{
    const li = document.createElement("li");
    li.textContent = s;
    ol.appendChild(li);
  });
}
function renderCounts(el, counts) {
  if (!counts) { el.textContent=""; return; }
  const labels = Object.keys(counts);
  el.textContent = labels.map(k=>`${k}:${counts[k]}`).join("  ");
}
function renderStatChips(el, counts) {
  el.innerHTML = "";
  if (!counts) return;
  for (const k of Object.keys(counts)) {
    const span = document.createElement("span");
    span.className = "chip";
    span.textContent = `${k}: ${counts[k]}`;
    el.appendChild(span);
  }
}

// -------------------- IMPORT CSV --------------------
const importBtn = j("importBtn");
const csvFile   = j("csvFile");
const overwrite = j("overwrite");
const importLog = j("importLog");

importBtn?.addEventListener("click", async () => {
  const f = csvFile.files?.[0];
  if (!f) return toast("Choose a CSV file.", "warn");
  const fd = new FormData();
  fd.append("file", f);
  fd.append("overwrite", overwrite.checked ? "true" : "false");
  buttonBusy(importBtn, true, "Uploading…");
  try {
    const r = await fetch(IMPORT_URL, { method:"POST", body: fd });
    const data = await r.json();
    importLog.textContent = JSON.stringify(data, null, 2);
    if (!data.ok) toast("Import error", "error");
    else toast("Import complete", "ok");
  } catch (e) {
    importLog.textContent = String(e);
    toast(String(e), "error");
  } finally {
    buttonBusy(importBtn, false);
  }
});

// -------------------- RETRIEVE per date --------------------
async function doRetrieve(btn, game, dateStr, previewEl, tier="") {
  if (!dateStr) return toast("Enter a date (MM/DD/YYYY).", "warn");
  const params = new URLSearchParams({ game, date: dateStr });
  if (tier) params.set("tier", tier);
  buttonBusy(btn, true, "Retrieving…");
  try {
    const data = await getJSON(`${BYDATE_URL}?${params.toString()}`);
    if (!data?.ok) throw new Error(data?.detail || data?.error || "Retrieve failed");
    // returns row = [[mains..], bonus] (IL bonus=null)
    previewEl.value = JSON.stringify(data.row);
    toast(`${game}${tier? " "+tier:""} retrieved`, "ok");
  } catch (e) {
    previewEl.value = "";
    toast(String(e), "error", 3000);
  } finally {
    buttonBusy(btn, false);
  }
}

j("mmRetrieve")?.addEventListener("click", ()=>doRetrieve(j("mmRetrieve"), "MM", j("mmDate").value.trim(), j("mmPreview")));
j("pbRetrieve")?.addEventListener("click", ()=>doRetrieve(j("pbRetrieve"), "PB", j("pbDate").value.trim(), j("pbPreview")));
j("ilJPRetrieve")?.addEventListener("click", ()=>doRetrieve(j("ilJPRetrieve"), "IL", j("ilJPDate").value.trim(), j("ilJPPreview"), "JP"));
j("ilM1Retrieve")?.addEventListener("click", ()=>doRetrieve(j("ilM1Retrieve"), "IL", j("ilM1Date").value.trim(), j("ilM1Preview"), "M1"));
j("ilM2Retrieve")?.addEventListener("click", ()=>doRetrieve(j("ilM2Retrieve"), "IL", j("ilM2Date").value.trim(), j("ilM2Preview"), "M2"));

// -------------------- HISTORY (Load 20) --------------------
async function load20(btn, game, dateStr, outEl, tier="") {
  if (!dateStr) return toast("Enter start date.", "warn");
  const qs = new URLSearchParams({ game, date: dateStr });
  if (tier) qs.set("tier", tier);
  buttonBusy(btn, true, "Loading…");
  try {
    const data = await getJSON(`${HISTORY_URL}?${qs.toString()}`);
    if (!data?.ok) throw new Error(data?.detail || data?.error || "Load failed");
    outEl.value = data.text || data.blob || ""; // backend may return .text
    toast("Loaded 20", "ok");
  } catch (e) {
    outEl.value = "";
    toast(String(e), "error", 3000);
  } finally {
    buttonBusy(btn, false);
  }
}

// Phase-1 history buttons
j("mmLoad20")?.addEventListener("click", ()=>load20(j("mmLoad20"), "MM", j("mmHistDate").value.trim(), j("HIST_MM_BLOB")));
j("pbLoad20")?.addEventListener("click", ()=>load20(j("pbLoad20"), "PB", j("pbHistDate").value.trim(), j("HIST_PB_BLOB")));
j("ilJPLoad20")?.addEventListener("click", ()=>load20(j("ilJPLoad20"), "IL", j("ilJPHistDate").value.trim(), j("HIST_IL_JP_BLOB"), "JP"));
j("ilM1Load20")?.addEventListener("click", ()=>load20(j("ilM1Load20"), "IL", j("ilM1HistDate").value.trim(), j("HIST_IL_M1_BLOB"), "M1"));
j("ilM2Load20")?.addEventListener("click", ()=>load20(j("ilM2Load20"), "IL", j("ilM2HistDate").value.trim(), j("HIST_IL_M2_BLOB"), "M2"));

// Phase-2 history buttons (2nd-newest start)
j("p2_mmLoad20")?.addEventListener("click", ()=>load20(j("p2_mmLoad20"), "MM", j("p2_mmHistDate").value.trim(), j("P2_HIST_MM_BLOB")));
j("p2_pbLoad20")?.addEventListener("click", ()=>load20(j("p2_pbLoad20"), "PB", j("p2_pbHistDate").value.trim(), j("P2_HIST_PB_BLOB")));
j("p2_ilJPLoad20")?.addEventListener("click", ()=>load20(j("p2_ilJPLoad20"), "IL", j("p2_ilJPHistDate").value.trim(), j("P2_HIST_IL_JP_BLOB"), "JP"));
j("p2_ilM1Load20")?.addEventListener("click", ()=>load20(j("p2_ilM1Load20"), "IL", j("p2_ilM1HistDate").value.trim(), j("P2_HIST_IL_M1_BLOB"), "M1"));
j("p2_ilM2Load20")?.addEventListener("click", ()=>load20(j("p2_ilM2Load20"), "IL", j("p2_ilM2HistDate").value.trim(), j("P2_HIST_IL_M2_BLOB"), "M2"));

// -------------------- RUN PHASE 1 --------------------
const runPhase1 = j("runPhase1");
runPhase1?.addEventListener("click", async () => {
  const payload = {
    FEED_MM: j("FEED_MM").value, FEED_PB: j("FEED_PB").value, FEED_IL: j("FEED_IL").value,
    HIST_MM_BLOB: j("HIST_MM_BLOB").value, HIST_PB_BLOB: j("HIST_PB_BLOB").value,
    HIST_IL_JP_BLOB: j("HIST_IL_JP_BLOB").value, HIST_IL_M1_BLOB: j("HIST_IL_M1_BLOB").value, HIST_IL_M2_BLOB: j("HIST_IL_M2_BLOB").value,
    LATEST_MM: j("mmPreview").value, LATEST_PB: j("pbPreview").value,
    LATEST_IL_JP: j("ilJPPreview").value, LATEST_IL_M1: j("ilM1Preview").value, LATEST_IL_M2: j("ilM2Preview").value,
    phase: "phase1"
  };
  buttonBusy(runPhase1, true, "Running…");
  j("phase1Done").style.display = "none";
  try {
    const data = await postJSON(RUN_URL, payload);
    if (!data?.ok) throw new Error(data?.detail || data?.error || "Phase 1 failed");

    const E = data.echo || {};
    // batches
    renderList(j("mmBatch"), E.BATCH_MM || []);
    renderList(j("pbBatch"), E.BATCH_PB || []);
    renderList(j("ilBatch"), E.BATCH_IL || []);
    // counts
    renderCounts(j("mmCounts"), (E.HITS_MM||{}).counts);
    renderCounts(j("pbCounts"), (E.HITS_PB||{}).counts);
    const jp = (E.HITS_IL_JP||{}).counts || {};
    const m1 = (E.HITS_IL_M1||{}).counts || {};
    const m2 = (E.HITS_IL_M2||{}).counts || {};
    j("ilCounts").textContent = `JP ${JSON.stringify(jp)}  M1 ${JSON.stringify(m1)}  M2 ${JSON.stringify(m2)}`;
    // stat chips + row indices
    renderStatChips(j("mmStats"), (E.HITS_MM||{}).counts);
    renderStatChips(j("pbStats"), (E.HITS_PB||{}).counts);
    const rfmt = (rows) => JSON.stringify(rows, null, 2);
    j("mmRows").textContent = rfmt((E.HITS_MM||{}).rows||{});
    j("pbRows").textContent = rfmt((E.HITS_PB||{}).rows||{});
    j("ilRows").textContent = JSON.stringify({
      JP:(E.HITS_IL_JP||{}).rows||{}, M1:(E.HITS_IL_M1||{}).rows||{}, M2:(E.HITS_IL_M2||{}).rows||{}
    }, null, 2);

    if (data.saved_path) j("phase1Path").value = data.saved_path;
    j("phase1Done").style.display = "inline";
    toast("Phase 1 complete", "ok");
  } catch (e) {
    toast(String(e), "error", 3500);
  } finally {
    buttonBusy(runPhase1, false);
  }
});

// -------------------- RUN PHASE 2 --------------------
const runPhase2 = j("runPhase2");
runPhase2?.addEventListener("click", async () => {
  const payload = {
    phase: "phase2",
    // same FEED_* inputs
    FEED_MM: j("FEED_MM").value, FEED_PB: j("FEED_PB").value, FEED_IL: j("FEED_IL").value,
    // phase-2 histories (no JP in latest)
    HIST_MM_BLOB: j("P2_HIST_MM_BLOB").value,
    HIST_PB_BLOB: j("P2_HIST_PB_BLOB").value,
    HIST_IL_JP_BLOB: j("P2_HIST_IL_JP_BLOB").value,
    HIST_IL_M1_BLOB: j("P2_HIST_IL_M1_BLOB").value,
    HIST_IL_M2_BLOB: j("P2_HIST_IL_M2_BLOB").value,
    // optional: the draw dates (for your own reference or backend logging)
    PREDICT_MM_DATE: j("p2_mmDraw").value.trim(),
    PREDICT_PB_DATE: j("p2_pbDraw").value.trim(),
    PREDICT_IL_DATE: j("p2_ilDraw").value.trim()
  };
  buttonBusy(runPhase2, true, "Sampling…");
  try {
    const data = await postJSON(RUN_URL, payload);
    if (!data?.ok) throw new Error(data?.detail || data?.error || "Phase 2 failed");
    const E = data.echo || {};
    renderList(j("p2_mmBatch"), E.BATCH_MM || []);
    renderList(j("p2_pbBatch"), E.BATCH_PB || []);
    renderList(j("p2_ilBatch"), E.BATCH_IL || []);
    // show diversity/meta
    const metaTxt = (m)=> m? `unique:${m.diversity?.unique_mains}  pairs:${m.used_pairs}  triples:${m.used_triples}` : "";
    j("p2_mmMeta").textContent = metaTxt(E.META_MM);
    j("p2_pbMeta").textContent = metaTxt(E.META_PB);
    j("p2_ilMeta").textContent = metaTxt(E.META_IL);
    toast("Phase 2 ready", "ok");
  } catch (e) {
    toast(String(e), "error", 3500);
  } finally {
    buttonBusy(runPhase2, false);
  }
});
