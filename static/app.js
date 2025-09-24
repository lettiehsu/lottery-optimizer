// Small helpers
const $ = (id) => document.getElementById(id);
const sleep = (ms) => new Promise(r => setTimeout(r, ms));

function toast(msg, kind="ok", ms=1600) {
  const el = document.createElement("div");
  el.className = `toast ${kind}`;
  el.textContent = msg;
  document.body.appendChild(el);
  setTimeout(()=> el.classList.add("show"), 10);
  setTimeout(()=> { el.classList.remove("show"); setTimeout(()=>el.remove(), 200); }, ms);
}

async function getJSON(url){
  const r = await fetch(url);
  const t = await r.text();
  try { return JSON.parse(t); } catch { throw new Error(t || r.statusText); }
}

async function postForm(url, fd) {
  const r = await fetch(url, { method: "POST", body: fd });
  const t = await r.text();
  try { return JSON.parse(t); } catch { throw new Error(t || r.statusText); }
}

function setBusy(btn, busy=true, labelWhenBusy="Working…") {
  if (!btn) return;
  if (busy) {
    btn.dataset.label = btn.textContent;
    btn.disabled = true;
    btn.classList.add("busy");
    btn.textContent = labelWhenBusy;
  } else {
    btn.disabled = false;
    btn.classList.remove("busy");
    if (btn.dataset.label) btn.textContent = btn.dataset.label;
  }
}


// --- Upload CSV ---
const csvFile = $("csvFile");
const overwrite = $("overwrite");
const btnImport = $("btnImport");
const importLog = $("importLog");

btnImport?.addEventListener("click", async () => {
  try {
    if (!csvFile.files?.length) return toast("Choose a CSV file first.", "warn");
    const fd = new FormData();
    fd.append("file", csvFile.files[0]);
    setBusy(btnImport, true, "Uploading…");
    const data = await postForm(`/store/import_csv?overwrite=${overwrite.checked ? 1 : 0}`, fd);
    importLog.textContent = JSON.stringify(data, null, 2);
    if (data.ok) toast("Imported successfully.", "ok");
    else toast(data.detail || data.error || "Import failed", "error", 2600);
  } catch (e) {
    importLog.textContent = String(e);
    toast(String(e), "error", 2600);
  } finally {
    setBusy(btnImport, false);
  }
});


// --- Retrieve single row (2nd newest) ---
async function doRetrieve(btn, game, dateStr, previewEl, tier="") {
  if (!dateStr) return toast("Enter a date (MM/DD/YYYY).", "warn");
  const u = new URLSearchParams({game, date: dateStr});
  if (tier) u.set("tier", tier);
  setBusy(btn, true, "Retrieving…");
  try {
    const data = await getJSON(`/store/get_by_date?${u.toString()}`);
    if (!data.ok) throw new Error(data.detail || data.error || "Retrieve failed");
    previewEl.value = JSON.stringify(data.row);
    toast(`${game}${tier? " " + tier: ""} retrieved.`, "ok");
  } catch (e) {
    previewEl.value = "";
    toast(String(e), "error", 2600);
  } finally {
    setBusy(btn, false);
  }
}

$("mmRetrieve")?.addEventListener("click", ()=> doRetrieve($("mmRetrieve"), "MM", $("mmDate").value.trim(), $("mmPreview")));
$("pbRetrieve")?.addEventListener("click", ()=> doRetrieve($("pbRetrieve"), "PB", $("pbDate").value.trim(), $("pbPreview")));
$("ilJPRetrieve")?.addEventListener("click", ()=> doRetrieve($("ilJPRetrieve"), "IL", $("ilJPDate").value.trim(), $("ilJPPreview"), "JP"));
$("ilM1Retrieve")?.addEventListener("click", ()=> doRetrieve($("ilM1Retrieve"), "IL", $("ilM1Date").value.trim(), $("ilM1Preview"), "M1"));
$("ilM2Retrieve")?.addEventListener("click", ()=> doRetrieve($("ilM2Retrieve"), "IL", $("ilM2Date").value.trim(), $("ilM2Preview"), "M2"));


// --- Load 20 history rows ---
async function load20(btn, game, fromDate, outEl, tier="") {
  if (!fromDate) return toast("Type the 3rd newest date first.", "warn");
  const qs = new URLSearchParams({game, from: fromDate, limit: 20});
  if (tier) qs.set("tier", tier);
  setBusy(btn, true, "Loading…");
  try {
    const data = await getJSON(`/store/get_history?${qs.toString()}`);
    if (!data.ok) throw new Error(data.detail || data.error || "Load failed");
    outEl.value = (data.rows || []).join("\n");
    toast("Loaded 20.", "ok");
  } catch (e) {
    outEl.value = String(e);
    toast(String(e), "error", 2600);
  } finally {
    setBusy(btn, false);
  }
}

$("loadMM")?.addEventListener("click", ()=> load20($("loadMM"), "MM", $("histMMDate").value.trim(), $("histMM")));
$("loadPB")?.addEventListener("click", ()=> load20($("loadPB"), "PB", $("histPBDate").value.trim(), $("histPB")));
$("loadILJP")?.addEventListener("click", ()=> load20($("loadILJP"), "IL", $("histILJPDate").value.trim(), $("histILJP"), "JP"));
$("loadILM1")?.addEventListener("click", ()=> load20($("loadILM1"), "IL", $("histILM1Date").value.trim(), $("histILM1"), "M1"));
$("loadILM2")?.addEventListener("click", ()=> load20($("loadILM2"), "IL", $("histILM2Date").value.trim(), $("histILM2"), "M2"));


// --- Run Phase 1 (placeholder that just echoes what you loaded) ---
const runPhase1 = $("runPhase1");
const phase1Path = $("phase1Path");
const phase1Result = $("phase1Result");
const doneBadge = $("doneBadge");

runPhase1?.addEventListener("click", async ()=>{
  setBusy(runPhase1, true, "Running…");
  doneBadge.style.display = "none";
  try {
    // This demo just echos the blobs/preview text you already retrieved
    const out = {
      echo: {
        LATEST_MM: $("mmPreview").value || null,
        LATEST_PB: $("pbPreview").value || null,
        LATEST_IL_JP: $("ilJPPreview").value || null,
        LATEST_IL_M1: $("ilM1Preview").value || null,
        LATEST_IL_M2: $("ilM2Preview").value || null,
        HIST_MM_BLOB: $("histMM").value,
        HIST_PB_BLOB: $("histPB").value,
        HIST_IL_JP_BLOB: $("histILJP").value,
        HIST_IL_M1_BLOB: $("histILM1").value,
        HIST_IL_M2_BLOB: $("histILM2").value,
        phase: "phase1"
      },
      ok: true
    };
    const fname = `/tmp/lotto_1_${new Date().toISOString().slice(0,19).replace(/[:T]/g,'-')}.json`;
    phase1Path.value = fname;
    phase1Result.textContent = JSON.stringify(out, null, 2);
    doneBadge.style.display = "inline-block";
    toast("Phase 1 finished.", "ok");
  } catch (e) {
    phase1Result.textContent = String(e);
    toast(String(e), "error", 2600);
  } finally {
    setBusy(runPhase1, false);
  }
});
