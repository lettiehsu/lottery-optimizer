/* small helpers */
const $ = (q) => document.querySelector(q);
const toast = (msg, kind="ok", ms=1600) => {
  const n = document.createElement("div");
  n.className = "toast " + kind;
  n.textContent = String(msg);
  document.body.appendChild(n);
  setTimeout(()=>n.classList.add("show"), 10);
  setTimeout(()=>{ n.classList.remove("show"); setTimeout(()=>n.remove(), 300); }, ms);
};
const buttonBusy = (btn, on, label) => {
  if (!btn) return;
  if (on) {
    btn.dataset.prev = btn.textContent;
    btn.classList.add("busy");
    btn.textContent = label || "Working…";
    btn.disabled = true;
  } else {
    btn.classList.remove("busy");
    btn.textContent = btn.dataset.prev || btn.textContent;
    btn.disabled = false;
  }
};
const getJSON = async (url) => (await fetch(url)).json();
const postJSON = async (url, data) => (await fetch(url, {method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify(data)})).json();

/* elements */
const csvFile = $("#csvFile");
const overwriteCsv = $("#overwriteCsv");
const btnCsv = $("#btnCsv");
const csvLog = $("#csvLog");

/* Phase 1 inputs */
const mmDate = $("#mmDate");
const pbDate = $("#pbDate");
const ilJPDate = $("#ilJPDate");
const ilM1Date = $("#ilM1Date");
const ilM2Date = $("#ilM2Date");

const mmPreview = $("#mmPreview");
const pbPreview = $("#pbPreview");
const ilJPPreview = $("#ilJPPreview");
const ilM1Preview = $("#ilM1Preview");
const ilM2Preview = $("#ilM2Preview");

const FEED_MM = $("#FEED_MM");
const FEED_PB = $("#FEED_PB");
const FEED_IL = $("#FEED_IL");

const mmHistDate = $("#mmHistDate");
const pbHistDate = $("#pbHistDate");
const ilJPHistDate = $("#ilJPHistDate");
const ilM1HistDate = $("#ilM1HistDate");
const ilM2HistDate = $("#ilM2HistDate");

const HIST_MM_BLOB = $("#HIST_MM_BLOB");
const HIST_PB_BLOB = $("#HIST_PB_BLOB");
const HIST_IL_JP_BLOB = $("#HIST_IL_JP_BLOB");
const HIST_IL_M1_BLOB = $("#HIST_IL_M1_BLOB");
const HIST_IL_M2_BLOB = $("#HIST_IL_M2_BLOB");

/* Results Phase 1 */
const runPhase1 = $("#runPhase1");
const phase1Path = $("#phase1Path");
const phase1Done = $("#phase1Done");
const mmBatch = $("#mmBatch");
const pbBatch = $("#pbBatch");
const ilBatch = $("#ilBatch");
const mmStats = $("#mmStats");
const pbStats = $("#pbStats");
const ilStats = $("#ilStats");
const mmRows = $("#mmRows");
const pbRows = $("#pbRows");
const ilRows = $("#ilRows");

/* Phase 2 */
const runPhase2 = $("#runPhase2");
const phase2Path = $("#phase2Path");
const copyBuy = $("#copyBuy");
const p2MMStats = $("#p2MMStats");
const p2PBStats = $("#p2PBStats");
const p2ILStats = $("#p2ILStats");
const p2MMRows = $("#p2MMRows");
const p2PBRows = $("#p2PBRows");
const p2ILRows = $("#p2ILRows");
const p2MMBuy = $("#p2MMBuy");
const p2PBBuy = $("#p2PBBuy");
const p2ILBuy = $("#p2ILBuy");

/* ---------------- CSV upload ---------------- */
btnCsv?.addEventListener("click", async ()=>{
  const f = csvFile.files?.[0];
  if (!f) return toast("Choose a CSV file first.", "warn");
  const fd = new FormData();
  fd.append("file", f);
  fd.append("overwrite", overwriteCsv.checked ? "true" : "false");
  buttonBusy(btnCsv, true, "Uploading…");
  try {
    const r = await fetch("/store/import_csv", {method:"POST", body:fd});
    const data = await r.json();
    csvLog.textContent = JSON.stringify(data, null, 2);
    if (!data.ok) throw new Error(data.detail || data.error || "Import failed");
    toast("CSV imported.", "ok");
  } catch (e) {
    csvLog.textContent = String(e);
    toast(String(e), "error", 2800);
  } finally {
    buttonBusy(btnCsv, false);
  }
});

/* ---------------- retrieve 2nd newest (per game) ---------------- */
const doRetrieve = async (btn, game, dateStr, previewEl, tier="")=>{
  if (!dateStr) return toast("Enter a date (MM/DD/YYYY).", "warn");
  const params = new URLSearchParams({game, date: dateStr});
  if (tier) params.set("tier", tier);
  buttonBusy(btn, true, "Retrieving…");
  try {
    const data = await getJSON(`/store/get_by_date?${params.toString()}`);
    if (!data?.ok) throw new Error(data?.detail || data?.error || "Retrieve failed");
    previewEl.value = JSON.stringify(data.row);
    toast(`${game}${tier?` ${tier}`:""} retrieved.`, "ok");
  } catch (e) {
    previewEl.value = "";
    toast(String(e), "error", 2600);
  } finally {
    buttonBusy(btn, false);
  }
};

$("#mmRetrieve")?.addEventListener("click", ()=>doRetrieve($("#mmRetrieve"), "MM", mmDate.value.trim(), mmPreview));
$("#pbRetrieve")?.addEventListener("click", ()=>doRetrieve($("#pbRetrieve"), "PB", pbDate.value.trim(), pbPreview));
$("#ilJPRetrieve")?.addEventListener("click", ()=>doRetrieve($("#ilJPRetrieve"), "IL", ilJPDate.value.trim(), ilJPPreview, "JP"));
$("#ilM1Retrieve")?.addEventListener("click", ()=>doRetrieve($("#ilM1Retrieve"), "IL", ilM1Date.value.trim(), ilM1Preview, "M1"));
$("#ilM2Retrieve")?.addEventListener("click", ()=>doRetrieve($("#ilM2Retrieve"), "IL", ilM2Date.value.trim(), ilM2Preview, "M2"));

/* ---------------- history load 20 ---------------- */
const load20 = async (btn, game, dateStr, outEl, tier="")=>{
  if (!dateStr) return toast("Enter a date.", "warn");
  const qs = new URLSearchParams({game, date: dateStr});
  if (tier) qs.set("tier", tier);
  buttonBusy(btn, true, "Loading…");
  try {
    const data = await getJSON(`/store/get_history?game=${game}&from=${encodeURIComponent(dateStr)}&limit=20${tier?`&tier=${tier}`:""}`);
    if (!data?.ok) throw new Error(data.detail || data.error || "Load failed");
    // rows are most recent first
    outEl.value = (data.rows||[]).join("\n");
    toast("Loaded 20.", "ok");
  } catch (e) {
    outEl.value = "";
    toast(String(e), "error", 2600);
  } finally {
    buttonBusy(btn, false);
  }
};

$("#mmLoad20")?.addEventListener("click", ()=>load20($("#mmLoad20"), "MM", mmHistDate.value.trim(), HIST_MM_BLOB));
$("#pbLoad20")?.addEventListener("click", ()=>load20($("#pbLoad20"), "PB", pbHistDate.value.trim(), HIST_PB_BLOB));
$("#ilJPLoad20")?.addEventListener("click", ()=>load20($("#ilJPLoad20"), "IL", ilJPHistDate.value.trim(), HIST_IL_JP_BLOB, "JP"));
$("#ilM1Load20")?.addEventListener("click", ()=>load20($("#ilM1Load20"), "IL", ilM1HistDate.value.trim(), HIST_IL_M1_BLOB, "M1"));
$("#ilM2Load20")?.addEventListener("click", ()=>load20($("#ilM2Load20"), "IL", ilM2HistDate.value.trim(), HIST_IL_M2_BLOB, "M2"));

/* ---------------- Run Phase 1 ---------------- */
runPhase1?.addEventListener("click", async ()=>{
  phase1Done.style.display = "none";
  mmBatch.innerHTML = pbBatch.innerHTML = ilBatch.innerHTML = "";
  mmStats.textContent = pbStats.textContent = ilStats.textContent = "";
  mmRows.textContent = pbRows.textContent = ilRows.textContent = "";
  const payload = {
    phase: "phase1",
    FEED_MM: FEED_MM.value, FEED_PB: FEED_PB.value, FEED_IL: FEED_IL.value,
    HIST_MM_BLOB: HIST_MM_BLOB.value, HIST_PB_BLOB: HIST_PB_BLOB.value,
    HIST_IL_JP_BLOB: HIST_IL_JP_BLOB.value, HIST_IL_M1_BLOB: HIST_IL_M1_BLOB.value, HIST_IL_M2_BLOB: HIST_IL_M2_BLOB.value,
    LATEST_MM: mmPreview.value, LATEST_PB: pbPreview.value, LATEST_IL_JP: ilJPPreview.value
  };
  buttonBusy(runPhase1, true, "Running…");
  try {
    const res = await postJSON("/run_json", payload);
    if (!res?.ok) throw new Error(res.detail || res.error || "Phase 1 failed");
    phase1Path.value = res.saved_path || "";
    // show batches
    (res.echo?.BATCH_MM||[]).forEach(s=>{ const li=document.createElement("li"); li.textContent=s; mmBatch.appendChild(li);});
    (res.echo?.BATCH_PB||[]).forEach(s=>{ const li=document.createElement("li"); li.textContent=s; pbBatch.appendChild(li);});
    (res.echo?.BATCH_IL||[]).forEach(s=>{ const li=document.createElement("li"); li.textContent=s; ilBatch.appendChild(li);});
    phase1Done.style.display = "inline-block";
    toast("Phase 1 complete.", "ok");
  } catch (e) {
    toast(String(e), "error", 3000);
  } finally {
    buttonBusy(runPhase1, false);
  }
});

/* ---------------- Run Phase 2 ---------------- */
runPhase2?.addEventListener("click", async ()=>{
  p2MMStats.textContent = p2PBStats.textContent = p2ILStats.textContent = "";
  p2MMRows.textContent = p2PBRows.textContent = p2ILRows.textContent = "";
  p2MMBuy.textContent = p2PBBuy.textContent = p2ILBuy.textContent = "";
  const payload = {
    phase: "phase2",
    FEED_MM: FEED_MM.value, FEED_PB: FEED_PB.value, FEED_IL: FEED_IL.value,
    HIST_MM_BLOB: HIST_MM_BLOB.value, HIST_PB_BLOB: HIST_PB_BLOB.value,
    HIST_IL_JP_BLOB: HIST_IL_JP_BLOB.value, HIST_IL_M1_BLOB: HIST_IL_M1_BLOB.value, HIST_IL_M2_BLOB: HIST_IL_M2_BLOB.value,
    LATEST_MM: mmPreview.value, LATEST_PB: pbPreview.value, LATEST_IL_JP: ilJPPreview.value
  };
  buttonBusy(runPhase2, true, "Simulating 100…");
  try {
    const res = await postJSON("/run_json", payload);
    if (!res?.ok) throw new Error(res.detail || res.error || "Phase 2 failed");
    phase2Path.value = res.saved_path || "";

    const S = (o)=>JSON.stringify(o, null, 2);
    p2MMStats.textContent = S(res.stats?.MM || {});
    p2PBStats.textContent = S(res.stats?.PB || {});
    p2ILStats.textContent = S(res.stats?.IL || {});
    p2MMRows.textContent  = S(res.positions?.MM || {});
    p2PBRows.textContent  = S(res.positions?.PB || {});
    p2ILRows.textContent  = S(res.positions?.IL || {});
    p2MMBuy.textContent   = (res.buy_list?.MM || []).join("\n");
    p2PBBuy.textContent   = (res.buy_list?.PB || []).join("\n");
    p2ILBuy.textContent   = (res.buy_list?.IL || []).join("\n");
    toast("Phase 2 complete.", "ok");
  } catch (e) {
    toast(String(e), "error", 3200);
  } finally {
    buttonBusy(runPhase2, false);
  }
});

/* Copy buy list (all 3 together) */
copyBuy?.addEventListener("click", ()=>{
  const blob = [
    "Mega Millions (10):", p2MMBuy.textContent.trim(), "",
    "Powerball (10):", p2PBBuy.textContent.trim(), "",
    "IL Lotto (15):", p2ILBuy.textContent.trim()
  ].join("\n");
  navigator.clipboard.writeText(blob).then(()=>toast("Copied buy list.", "ok")).catch(e=>toast(String(e), "error"));
});
