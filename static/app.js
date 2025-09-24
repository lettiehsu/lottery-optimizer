// -------- tiny helpers --------
const $ = (id) => document.getElementById(id);
const toast = (msg, kind="ok", ms=1800) => {
  const t = document.createElement("div");
  t.className = "toast";
  t.textContent = msg;
  document.body.appendChild(t);
  setTimeout(()=> t.remove(), ms);
};
const setBusy = (el, busy=true, label=null) => {
  if (!el) return;
  if (busy){ el.classList.add("busy"); el.disabled = true; if (label) el._old = el.textContent, el.textContent = label; }
  else { el.classList.remove("busy"); el.disabled = false; if (el._old) el.textContent = el._old; }
};
async function getJSON(url){ const r = await fetch(url); if(!r.ok){ let txt=await r.text(); throw new Error(txt||r.statusText);} return r.json(); }
async function postJSON(url, body){ const r = await fetch(url,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(body)}); const j = await r.json(); if(!r.ok || !j.ok) throw j; return j; }

// -------- upload --------
const csvFile = $("csvFile");
const overwrite = $("overwrite");
const btnImport = $("btnImport");
const importLog = $("importLog");

btnImport?.addEventListener("click", async ()=>{
  if (!csvFile.files?.length) return toast("Choose a CSV file", "warn");
  const fd = new FormData();
  fd.append("file", csvFile.files[0]);
  fd.append("overwrite", overwrite.checked ? "true" : "false");
  setBusy(btnImport, true, "Importing…");
  importLog.textContent = "";
  try {
    const r = await fetch("/store/import_csv", { method:"POST", body: fd });
    const j = await r.json();
    importLog.textContent = JSON.stringify(j, null, 2);
    if (!j.ok) throw j;
    toast(`Imported: +${j.added}, updated: ${j.updated}`, "ok");
  } catch(e){
    importLog.textContent = typeof e === "string" ? e : JSON.stringify(e, null, 2);
    toast("Import failed", "error", 2400);
  } finally {
    setBusy(btnImport, false);
  }
});

// -------- retrieve NJ rows --------
const mmDate=$("mmDate"), mmRetrieve=$("mmRetrieve"), mmPreview=$("mmPreview");
const pbDate=$("pbDate"), pbRetrieve=$("pbRetrieve"), pbPreview=$("pbPreview");
const ilJPDate=$("ilJPDate"), ilJPRetrieve=$("ilJPRetrieve"), ilJPPreview=$("ilJPPreview");
const ilM1Date=$("ilM1Date"), ilM1Retrieve=$("ilM1Retrieve"), ilM1Preview=$("ilM1Preview");
const ilM2Date=$("ilM2Date"), ilM2Retrieve=$("ilM2Retrieve"), ilM2Preview=$("ilM2Preview");

async function doRetrieve(btn, game, dateStr, previewEl, tier=""){
  if (!dateStr) return toast("Enter a date (MM/DD/YYYY).", "warn");
  const u = new URLSearchParams({game, date:dateStr});
  if (tier) u.set("tier", tier);
  setBusy(btn, true, "Retrieving…");
  try{
    const data = await getJSON(`/store/get_by_date?${u.toString()}`);
    if (!data.ok) throw data;
    previewEl.value = JSON.stringify(data.row);
    toast(`${game}${tier? " "+tier:""} retrieved.`, "ok");
  }catch(e){
    const msg = (e && e.detail) ? e.detail : (e && e.error) ? e.error : String(e);
    previewEl.value = typeof msg === "string" ? msg : JSON.stringify(msg, null, 2);
    toast("Retrieve failed — see details in the box.", "error", 2600);
  }finally{
    setBusy(btn, false);
  }
}

mmRetrieve?.addEventListener("click", ()=> doRetrieve(mmRetrieve,"MM",mmDate.value.trim(),mmPreview));
pbRetrieve?.addEventListener("click", ()=> doRetrieve(pbRetrieve,"PB",pbDate.value.trim(),pbPreview));
ilJPRetrieve?.addEventListener("click", ()=> doRetrieve(ilJPRetrieve,"IL",ilJPDate.value.trim(),ilJPPreview,"JP"));
ilM1Retrieve?.addEventListener("click", ()=> doRetrieve(ilM1Retrieve,"IL",ilM1Date.value.trim(),ilM1Preview,"M1"));
ilM2Retrieve?.addEventListener("click", ()=> doRetrieve(ilM2Retrieve,"IL",ilM2Date.value.trim(),ilM2Preview,"M2"));

// -------- history (Load 20) --------
const mmHistDate=$("mmHistDate"), mmLoad20=$("mmLoad20"), HIST_MM_BLOB=$("HIST_MM_BLOB");
const pbHistDate=$("pbHistDate"), pbLoad20=$("pbLoad20"), HIST_PB_BLOB=$("HIST_PB_BLOB");
const ilJPHistDate=$("ilJPHistDate"), ilJPLoad20=$("ilJPLoad20"), HIST_IL_JP_BLOB=$("HIST_IL_JP_BLOB");
const ilM1HistDate=$("ilM1HistDate"), ilM1Load20=$("ilM1Load20"), HIST_IL_M1_BLOB=$("HIST_IL_M1_BLOB");
const ilM2HistDate=$("ilM2HistDate"), ilM2Load20=$("ilM2Load20"), HIST_IL_M2_BLOB=$("HIST_IL_M2_BLOB");

async function load20(btn, game, dateStr, outEl, tier=""){
  if (!dateStr) return toast("Enter a date (MM/DD/YYYY).", "warn");
  const u = new URLSearchParams({game, from:dateStr, limit:"20"});
  if (tier) u.set("tier", tier);
  setBusy(btn, true, "Loading…");
  try{
    const data = await getJSON(`/store/get_history?${u.toString()}`);
    if (!data.ok) throw data;
    outEl.value = (data.rows||[]).join("\n");
    toast("Loaded 20", "ok");
  }catch(e){
    const msg = (e && e.detail) ? e.detail : (e && e.error) ? e.error : String(e);
    outEl.value = typeof msg === "string" ? msg : JSON.stringify(msg, null, 2);
    toast("Load failed", "error", 2400);
  }finally{
    setBusy(btn, false);
  }
}

mmLoad20?.addEventListener("click", ()=> load20(mmLoad20,"MM",mmHistDate.value.trim(),HIST_MM_BLOB));
pbLoad20?.addEventListener("click", ()=> load20(pbLoad20,"PB",pbHistDate.value.trim(),HIST_PB_BLOB));
ilJPLoad20?.addEventListener("click", ()=> load20(ilJPLoad20,"IL",ilJPHistDate.value.trim(),HIST_IL_JP_BLOB,"JP"));
ilM1Load20?.addEventListener("click", ()=> load20(ilM1Load20,"IL",ilM1HistDate.value.trim(),HIST_IL_M1_BLOB,"M1"));
ilM2Load20?.addEventListener("click", ()=> load20(ilM2Load20,"IL",ilM2HistDate.value.trim(),HIST_IL_M2_BLOB,"M2"));

// -------- run phase 1 --------
const runPhase1 = $("runPhase1");
const phase1Path = $("phase1Path");

const mmBatch=$("mmBatch"), pbBatch=$("pbBatch"), ilBatch=$("ilBatch");
const mmStats=$("mmStats"), pbStats=$("pbStats"), ilStats=$("ilStats");
const mmRows=$("mmRows"), pbRows=$("pbRows"), ilRows=$("ilRows");
const mmCounts=$("mmCounts"), pbCounts=$("pbCounts"), ilCounts=$("ilCounts");

function renderBatch(listEl, rows){
  listEl.innerHTML = "";
  rows.forEach((s)=> {
    const li = document.createElement("li"); li.textContent = s; listEl.appendChild(li);
  });
}

// ✅ FIXED: accept the whole hits object and use .counts / .rows correctly
function renderMMorPB(statsEl, rowsEl, hitsObj){
  const c = hitsObj.counts || {"3":0,"4":0,"5":0,"3+B":0,"4+B":0,"5+B":0};
  const r = hitsObj.rows || {"3":[], "4":[], "5":[], "3+B":[], "4+B":[], "5+B":[]};
  const line = `3=${c["3"]}  3+B=${c["3+B"]}  |  4=${c["4"]}  4+B=${c["4+B"]}  |  5=${c["5"]}  5+B=${c["5+B"]}`;
  statsEl.textContent = line;
  rowsEl.textContent = JSON.stringify(r, null, 2);
}

function renderIL(statsEl, rowsEl, counts){
  const line = `3=${counts["3"]}  |  4=${counts["4"]}  |  5=${counts["5"]}  |  6=${counts["6"]}`;
  statsEl.textContent = line;
  rowsEl.textContent = JSON.stringify(counts.rows || {}, null, 2);
}

runPhase1?.addEventListener("click", async ()=>{
  // Normalize LATEST fields: allow raw JSON or already-stringified
  const norm = (v)=> {
    const t = (v||"").trim();
    try { JSON.parse(t); return t; } catch { return t; }
  };

  const payload = {
    LATEST_MM: norm(mmPreview.value),
    LATEST_PB: norm(pbPreview.value),
    LATEST_IL_JP: norm(ilJPPreview.value),
    LATEST_IL_M1: norm(ilM1Preview.value),
    LATEST_IL_M2: norm(ilM2Preview.value),
    HIST_MM_BLOB: $("HIST_MM_BLOB").value,
    HIST_PB_BLOB: $("HIST_PB_BLOB").value,
    HIST_IL_JP_BLOB: $("HIST_IL_JP_BLOB").value,
    HIST_IL_M1_BLOB: $("HIST_IL_M1_BLOB").value,
    HIST_IL_M2_BLOB: $("HIST_IL_M2_BLOB").value
  };

  for (const k of ["LATEST_MM","LATEST_PB","LATEST_IL_JP","LATEST_IL_M1","LATEST_IL_M2"]) {
    if (!payload[k]) return toast(`Missing ${k}`, "warn");
  }

  setBusy(runPhase1, true, "Running…");
  try{
    const res = await postJSON("/run_json", payload);
    phase1Path.value = res.saved_path || "";

    // MM
    renderBatch(mmBatch, res.echo.BATCH_MM || []);
    renderMMorPB(mmStats, mmRows, res.echo.HITS_MM || {counts:{},rows:{}});
    mmCounts.textContent = (res.echo.HITS_MM?.exact_rows?.length ? `Exact 5 hits: ${res.echo.HITS_MM.exact_rows.join(", ")}` : "");

    // PB
    renderBatch(pbBatch, res.echo.BATCH_PB || []);
    renderMMorPB(pbStats, pbRows, res.echo.HITS_PB || {counts:{},rows:{}});
    pbCounts.textContent = (res.echo.HITS_PB?.exact_rows?.length ? `Exact 5 hits: ${res.echo.HITS_PB.exact_rows.join(", ")}` : "");

    // IL (aggregate)
    renderBatch(ilBatch, res.echo.BATCH_IL || []);
    const agg = { "3":0,"4":0,"5":0,"6":0, rows:{} };
    for (const key of ["HITS_IL_JP","HITS_IL_M1","HITS_IL_M2"]) {
      const h = res.echo[key] || {counts:{},rows:{}};
      agg["3"] += (h.counts?.["3"]||0); agg["4"] += (h.counts?.["4"]||0);
      agg["5"] += (h.counts?.["5"]||0); agg["6"] += (h.counts?.["6"]||0);
      agg.rows[key] = h.rows || {};
    }
    renderIL(ilStats, ilRows, agg);

    toast("Phase 1 complete", "ok");
  }catch(e){
    const msg = typeof e === "string" ? e : (e.detail || e.error || "Phase 1 failed");
    toast(msg, "error", 3000);
  }finally{
    setBusy(runPhase1, false);
  }
});
