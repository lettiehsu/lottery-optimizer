/* ======== helpers ======== */
const $ = (id) => document.getElementById(id);

function toast(msg, kind="ok", ms=1800){
  const t = document.createElement("div");
  t.className = `toast ${kind}`;
  t.textContent = msg;
  document.body.appendChild(t);
  setTimeout(()=>t.remove(), ms);
}

async function getJSON(url){
  const r = await fetch(url);
  if(!r.ok) throw new Error(`${r.status} ${r.statusText}`);
  return r.json();
}
async function postJSON(url, body){
  const r = await fetch(url, {
    method:"POST",
    headers:{ "Content-Type":"application/json" },
    body: JSON.stringify(body)
  });
  if(!r.ok) throw new Error(`${r.status} ${r.statusText}`);
  return r.json();
}
function buttonBusy(btn, on, label){
  if(!btn) return;
  if(on){ btn.setAttribute("disabled",""); btn.dataset.prev = btn.textContent; if(label) btn.textContent = label; }
  else { btn.removeAttribute("disabled"); if(btn.dataset.prev) btn.textContent = btn.dataset.prev; }
}

/* ======== DOM refs ======== */
const overwrite = $("overwrite");
const csvFile = $("csvFile");
const btnImport = $("btnImport");
const importLog = $("importLog");

const mmDate = $("mmDate"), pbDate = $("pbDate");
const ilJPDate = $("ilJPDate"), ilM1Date = $("ilM1Date"), ilM2Date = $("ilM2Date");
const mmPreview = $("mmPreview"), pbPreview = $("pbPreview");
const ilJPPreview = $("ilJPPreview"), ilM1Preview = $("ilM1Preview"), ilM2Preview = $("ilM2Preview");

const feedMM = $("feedMM"), feedPB = $("feedPB"), feedIL = $("feedIL");

const mmHistDate = $("mmHistDate"), pbHistDate = $("pbHistDate");
const ilJPHistDate = $("ilJPHistDate"), ilM1HistDate = $("ilM1HistDate"), ilM2HistDate = $("ilM2HistDate");
const mmHist = $("mmHist"), pbHist = $("pbHist");
const ilJPHist = $("ilJPHist"), ilM1Hist = $("ilM1Hist"), ilM2Hist = $("ilM2Hist");

const mmRetrieve = $("mmRetrieve"), pbRetrieve = $("pbRetrieve");
const ilJPRetrieve = $("ilJPRetrieve"), ilM1Retrieve = $("ilM1Retrieve"), ilM2Retrieve = $("ilM2Retrieve");
const mmLoad20 = $("mmLoad20"), pbLoad20 = $("pbLoad20");
const ilJPLoad20 = $("ilJPLoad20"), ilM1Load20 = $("ilM1Load20"), ilM2Load20 = $("ilM2Load20");

const runPhase1 = $("runPhase1"), phase1Path = $("phase1Path"), runDone = $("runDone");

/* ======== CSV import ======== */
btnImport?.addEventListener("click", async () => {
  if(!csvFile.files?.length){ toast("Choose a CSV file first.","err",2200); return; }
  const fd = new FormData();
  fd.append("file", csvFile.files[0]);
  buttonBusy(btnImport, true, "Uploading…");
  try{
    const url = `/store/import_csv?overwrite=${overwrite.checked ? 1 : 0}`;
    const r = await fetch(url, { method:"POST", body: fd });
    const data = await r.json();
    importLog.textContent = JSON.stringify(data, null, 2);
    if(!data?.ok) throw new Error(data?.detail || data?.error || "Upload failed");
    toast("CSV imported.", "ok");
  }catch(e){
    importLog.textContent = String(e);
    toast(String(e), "err", 2800);
  }finally{
    buttonBusy(btnImport, false);
  }
});

/* ======== Retrieve single rows (2nd newest per game) ======== */
async function doRetrieve(btn, game, dateStr, previewEl, tier=""){
  if(!dateStr) return toast("Enter a date (MM/DD/YYYY).","err");
  const params = new URLSearchParams({ game, date: dateStr });
  if(tier) params.set("tier", tier);
  buttonBusy(btn, true, "Retrieving…");
  try{
    const data = await getJSON(`/store/get_by_date?${params.toString()}`);
    if(!data?.ok) throw new Error(data?.detail || data?.error || "Retrieve failed");
    previewEl.value = JSON.stringify(data.row);
    toast(`${game}${tier? " "+tier:""} retrieved.`,"ok");
  }catch(e){
    previewEl.value = "";
    toast(String(e),"err",3000);
  }finally{
    buttonBusy(btn,false);
  }
}
mmRetrieve?.addEventListener("click",()=>doRetrieve(mmRetrieve,"MM",mmDate.value.trim(),mmPreview));
pbRetrieve?.addEventListener("click",()=>doRetrieve(pbRetrieve,"PB",pbDate.value.trim(),pbPreview));
ilJPRetrieve?.addEventListener("click",()=>doRetrieve(ilJPRetrieve,"IL",ilJPDate.value.trim(),ilJPPreview,"JP"));
ilM1Retrieve?.addEventListener("click",()=>doRetrieve(ilM1Retrieve,"IL",ilM1Date.value.trim(),ilM1Preview,"M1"));
ilM2Retrieve?.addEventListener("click",()=>doRetrieve(ilM2Retrieve,"IL",ilM2Date.value.trim(),ilM2Preview,"M2"));

/* ======== History “Load 20” ======== */
async function load20(btn, gameKey, fromDate, target){
  if(!fromDate) return toast("Enter start date for history (MM/DD/YYYY).","err");
  buttonBusy(btn,true,"Loading…");
  try{
    // expected gameKey examples: "MM", "PB", "IL_JP", "IL_M1", "IL_M2"
    const p = new URLSearchParams({ game: gameKey, from: fromDate, limit: 20 });
    const data = await getJSON(`/store/get_history?${p.toString()}`);
    if(!data?.ok) throw new Error(data?.detail || data?.error || "Load failed");
    // data.rows is array of strings; join nicely
    target.value = (data.rows || []).join("\n");
    toast(`${gameKey} history loaded.`,"ok");
  }catch(e){
    target.value = "";
    toast(String(e),"err",3000);
  }finally{
    buttonBusy(btn,false);
  }
}
mmLoad20?.addEventListener("click",()=>load20(mmLoad20,"MM",mmHistDate.value.trim(),mmHist));
pbLoad20?.addEventListener("click",()=>load20(pbLoad20,"PB",pbHistDate.value.trim(),pbHist));
ilJPLoad20?.addEventListener("click",()=>load20(ilJPLoad20,"IL_JP",ilJPHistDate.value.trim(),ilJPHist));
ilM1Load20?.addEventListener("click",()=>load20(ilM1Load20,"IL_M1",ilM1HistDate.value.trim(),ilM1Hist));
ilM2Load20?.addEventListener("click",()=>load20(ilM2Load20,"IL_M2",ilM2HistDate.value.trim(),ilM2Hist));

/* ======== Phase 1 run ======== */
runPhase1?.addEventListener("click", async () => {
  const body = {
    LATEST_MM: safeStr(mmPreview.value),
    LATEST_PB: safeStr(pbPreview.value),
    LATEST_IL_JP: safeStr(ilJPPreview.value),
    LATEST_IL_M1: safeStr(ilM1Preview.value),
    LATEST_IL_M2: safeStr(ilM2Preview.value),
    FEED_MM: feedMM.value || "",
    FEED_PB: feedPB.value || "",
    FEED_IL: feedIL.value || "",
    HIST_MM_BLOB: mmHist.value || "",
    HIST_PB_BLOB: pbHist.value || "",
    HIST_IL_JP_BLOB: ilJPHist.value || "",
    HIST_IL_M1_BLOB: ilM1Hist.value || "",
    HIST_IL_M2_BLOB: ilM2Hist.value || "",
  };

  buttonBusy(runPhase1,true,"Running…");
  $("runDone").textContent = "";
  try{
    const data = await postJSON("/phase1/run", body);
    if(!data?.ok) throw new Error(data?.detail || data?.error || "Phase-1 failed");
    phase1Path.value = data.saved_path || "";

    // pretty render
    renderPhase1Pretty(data);

    $("runDone").textContent = "Done";
    toast("Phase 1 complete.","ok");
  }catch(e){
    toast(String(e),"err",3000);
  }finally{
    buttonBusy(runPhase1,false);
  }
});

// enforce the backend’s “LATEST_* must be a string like '[..],b' or '[..],null'”
function safeStr(s){
  // pass-through if s already looks like a JSON array pair
  const t = (s || "").trim();
  if (t.startsWith("[[")) return t;
  return t; // let backend validate and error clearly
}

/* ======== Phase 1 pretty rendering (from earlier message) ======== */
function pill(txt){ const s=document.createElement("span"); s.className="chip"; s.textContent=txt; return s; }
function clearEl(el){ while(el.firstChild) el.removeChild(el.firstChild); }
function fillBatch(listEl, rows){ clearEl(listEl); (rows||[]).forEach((line)=>{ const li=document.createElement("li"); li.textContent=String(line); listEl.appendChild(li); }); }
function copyButton(textProvider){ const b=document.createElement("button"); b.className="btn tiny"; b.textContent="Copy"; b.addEventListener("click", async ()=>{ try{ await navigator.clipboard.writeText(textProvider()); toast("Copied batch.","ok"); }catch(e){ toast("Copy failed: "+e,"err"); } }); return b; }

function setStatsPillsMM(echo){
  const s=$("mmStats"), c=$("mmCounts"); clearEl(s); c.textContent="";
  const counts = echo?.HITS_MM?.counts || {};
  ["3","3+B","4","4+B","5","5+B"].forEach(k=>s.appendChild(pill(`${k}: ${counts[k]??0}`)));
  const exact=(echo?.HITS_MM?.exact_rows||[]).length;
  if(exact) c.textContent=`Exact rows: ${exact}`;
}
function setRowsMM(echo){
  const r=$("mmRows"); const rows=echo?.HITS_MM?.rows||{};
  const show=["3","3+B","4","4+B","5","5+B"]; const obj={}; show.forEach(k=>obj[k]=rows[k]||[]); r.textContent=JSON.stringify(obj,null,2);
}
function setStatsPillsPB(echo){
  const s=$("pbStats"), c=$("pbCounts"); clearEl(s); c.textContent="";
  const counts = echo?.HITS_PB?.counts || {};
  ["3","3+B","4","4+B","5","5+B"].forEach(k=>s.appendChild(pill(`${k}: ${counts[k]??0}`)));
  const exact=(echo?.HITS_PB?.exact_rows||[]).length; if(exact) c.textContent=`Exact rows: ${exact}`;
}
function setRowsPB(echo){
  const r=$("pbRows"); const rows=echo?.HITS_PB?.rows||{};
  const show=["3","3+B","4","4+B","5","5+B"]; const obj={}; show.forEach(k=>obj[k]=rows[k]||[]); r.textContent=JSON.stringify(obj,null,2);
}
function setStatsPillsIL(echo){
  const s=$("ilStats"); clearEl(s);
  function group(label, counts){
    const wrap=document.createElement("span"); wrap.className="chipset";
    wrap.appendChild(pill(`${label} 3: ${counts["3"]??0}`));
    wrap.appendChild(pill(`${label} 4: ${counts["4"]??0}`));
    wrap.appendChild(pill(`${label} 5: ${counts["5"]??0}`));
    wrap.appendChild(pill(`${label} 6: ${counts["6"]??0}`));
    return wrap;
  }
  s.appendChild(group("JP", echo?.HITS_IL_JP?.counts||{}));
  s.appendChild(group("M1", echo?.HITS_IL_M1?.counts||{}));
  s.appendChild(group("M2", echo?.HITS_IL_M2?.counts||{}));
}
function setRowsIL(echo){
  $("ilRows").textContent = JSON.stringify({
    JP: echo?.HITS_IL_JP?.rows || {"3":[],"4":[],"5":[],"6":[]},
    M1: echo?.HITS_IL_M1?.rows || {"3":[],"4":[],"5":[],"6":[]},
    M2: echo?.HITS_IL_M2?.rows || {"3":[],"4":[],"5":[],"6":[]},
  }, null, 2);
}
function renderPhase1Pretty(resp){
  const dbg=$("phase1Debug"); if(dbg) dbg.textContent = JSON.stringify(resp, null, 2);
  fillBatch($("mmBatch"), resp?.echo?.BATCH_MM || []);
  fillBatch($("pbBatch"), resp?.echo?.BATCH_PB || []);
  fillBatch($("ilBatch"), resp?.echo?.BATCH_IL || []);

  // add Copy once per column
  if(!$("mmBatchCopy")){ $("mmBatch").parentElement.prepend(Object.assign(copyButton(()=> (resp?.echo?.BATCH_MM||[]).join("\n")),{id:"mmBatchCopy"})); }
  if(!$("pbBatchCopy")){ $("pbBatch").parentElement.prepend(Object.assign(copyButton(()=> (resp?.echo?.BATCH_PB||[]).join("\n")),{id:"pbBatchCopy"})); }
  if(!$("ilBatchCopy")){ $("ilBatch").parentElement.prepend(Object.assign(copyButton(()=> (resp?.echo?.BATCH_IL||[]).join("\n")),{id:"ilBatchCopy"})); }

  setStatsPillsMM(resp?.echo); setRowsMM(resp?.echo);
  setStatsPillsPB(resp?.echo); setRowsPB(resp?.echo);
  setStatsPillsIL(resp?.echo); setRowsIL(resp?.echo);
}
