// -------- helpers --------
const $ = (id) => document.getElementById(id);
const toastEl = $("toast");
function toast(msg, kind="ok", ms=1800){
  toastEl.textContent = msg;
  toastEl.className = `toast ${kind}`;
  toastEl.style.display = "block";
  setTimeout(()=>toastEl.style.display="none", ms);
}
function press(el){ el?.classList.add('pressed'); setTimeout(()=>el?.classList.remove('pressed'),90); }
function busy(btn,on=true,label){
  if(!btn) return;
  if(on){ btn.dataset.lbl = btn.textContent; btn.disabled = true; btn.classList.add("busy"); if(label) btn.textContent = label; }
  else { btn.disabled = false; btn.classList.remove("busy"); btn.textContent = btn.dataset.lbl || btn.textContent; }
}
async function getJSON(url, opts){
  const r = await fetch(url, {headers:{'Accept':'application/json'}, ...(opts||{})});
  if(!r.ok){ const t=await r.text(); throw new Error(`${r.status} ${r.statusText} — ${t}`); }
  return r.json();
}
function latestString(game,row){
  const m = row?.row ? row.row[0] : row[0];
  const b = row?.row ? row.row[1] : row[1];
  return `[[${m.join(',')}],${game==='IL'?'null':(b==null?'null':b)}]`;
}

// ------- element refs -------
const overwriteCsv = $("overwriteCsv");
const csvFile = $("csvFile");
const importCsv = $("importCsv");
const csvLog = $("csvLog");

const mmDate=$("mmDate"), mmRetrieve=$("mmRetrieve"), mmPreview=$("mmPreview");
const pbDate=$("pbDate"), pbRetrieve=$("pbRetrieve"), pbPreview=$("pbPreview");
const ilJPDate=$("ilJPDate"), ilJPRetrieve=$("ilJPRetrieve"), ilJPPreview=$("ilJPPreview");
const ilM1Date=$("ilM1Date"), ilM1Retrieve=$("ilM1Retrieve"), ilM1Preview=$("ilM1Preview");
const ilM2Date=$("ilM2Date"), ilM2Retrieve=$("ilM2Retrieve"), ilM2Preview=$("ilM2Preview");

const histMMDate=$("histMMDate"), mmLoad20=$("mmLoad20"), histMMBlob=$("histMMBlob");
const histPBDate=$("histPBDate"), pbLoad20=$("pbLoad20"), histPBBlob=$("histPBBlob");
const histILJPDate=$("histILJPDate"), ilJPLoad20=$("ilJPLoad20"), histILJPBlob=$("histILJPBlob");
const histILM1Date=$("histILM1Date"), ilM1Load20=$("ilM1Load20"), histILM1Blob=$("histILM1Blob");
const histILM2Date=$("histILM2Date"), ilM2Load20=$("ilM2Load20"), histILM2Blob=$("histILM2Blob");

const runPhase1=$("runPhase1"), phase1Path=$("phase1Path"), doneBadge=$("doneBadge");
const rawPhase1=$("rawPhase1");

// results
const mmBatch=$("mmBatch"), pbBatch=$("pbBatch"), ilBatch=$("ilBatch");
const mmRows=$("mmRows"), pbRows=$("pbRows"), ilRows=$("ilRows");
const mmStats=$("mmStats"), pbStats=$("pbStats"), ilStats=$("ilStats");
const mmCounts=$("mmCounts"), pbCounts=$("pbCounts"), ilCounts=$("ilCounts");

// -------- CSV import --------
importCsv?.addEventListener("click", async ()=>{
  const f = csvFile.files?.[0];
  if(!f){ toast("Choose a CSV file.", "warn"); return;}
  const fd = new FormData();
  fd.set("file", f);
  fd.set("overwrite", String(overwriteCsv.checked));
  busy(importCsv,true,"Uploading…");
  try{
    const r = await fetch("/store/import_csv", {method:"POST", body: fd});
    const data = await r.json();
    csvLog.className = "log " + (data.ok?"ok":"err");
    csvLog.textContent = JSON.stringify(data,null,2);
    toast(data.ok ? "Import ok" : "Import failed", data.ok?"ok":"error");
  }catch(e){
    csvLog.className = "log err";
    csvLog.textContent = String(e);
    toast("Upload failed", "error");
  }finally{
    busy(importCsv,false);
  }
});

// -------- retrieve per game (2nd newest) --------
async function doRetrieve(btn, game, dateStr, out, tier){
  if(!dateStr){ toast("Enter a date.", "warn"); return; }
  const p = new URLSearchParams({game, date: dateStr});
  if(tier) p.set("tier", tier);
  press(btn); busy(btn,true,"Retrieving…");
  try{
    const data = await getJSON(`/store/get_by_date?${p.toString()}`);
    out.value = latestString(game, data.row);
    toast(`${game}${tier?(" "+tier):""} retrieved`, "ok");
  }catch(e){
    out.value = "";
    toast(e.message||e, "error", 3500);
  }finally{
    busy(btn,false);
  }
}
mmRetrieve?.addEventListener("click", ()=>doRetrieve(mmRetrieve,"MM",mmDate.value.trim(),mmPreview));
pbRetrieve?.addEventListener("click", ()=>doRetrieve(pbRetrieve,"PB",pbDate.value.trim(),pbPreview));
ilJPRetrieve?.addEventListener("click", ()=>doRetrieve(ilJPRetrieve,"IL",ilJPDate.value.trim(),ilJPPreview,"JP"));
ilM1Retrieve?.addEventListener("click", ()=>doRetrieve(ilM1Retrieve,"IL",ilM1Date.value.trim(),ilM1Preview,"M1"));
ilM2Retrieve?.addEventListener("click", ()=>doRetrieve(ilM2Retrieve,"IL",ilM2Date.value.trim(),ilM2Preview,"M2"));

// -------- history Load 20 --------
async function load20(btn, game, startInput, outTextarea, tier){
  const start = startInput.value.trim();
  if(!start){ toast("Enter a start date (3rd newest).", "warn"); return; }
  const p = new URLSearchParams({game, from:start, limit:"20"});
  if(tier) p.set("tier", tier);
  press(btn); busy(btn,true,"Loading…");
  try{
    const data = await getJSON(`/store/get_history?${p.toString()}`);
    const lines = data.rows.map(r=>{
      const d = new Date(r.date);
      const mm = String(d.getMonth()+1).padStart(2,"0");
      const dd = String(d.getDate()).padStart(2,"0");
      const yy = String(d.getFullYear()).slice(-2);
      const left = `${mm}-${dd}-${yy}`;
      const mains = r.mains.map(n=>String(n).padStart(2,"0")).join("-");
      if(game==="IL") return `${left}  ${mains}`;
      return `${left}  ${mains}  ${String(r.bonus).padStart(2,"0")}`;
    });
    outTextarea.value = lines.join("\n");
    toast("Loaded 20", "ok");
  }catch(e){
    outTextarea.value = "";
    toast(e.message||e, "error", 3500);
  }finally{
    busy(btn,false);
  }
}
mmLoad20?.addEventListener("click", ()=>load20(mmLoad20,"MM",histMMDate,histMMBlob));
pbLoad20?.addEventListener("click", ()=>load20(pbLoad20,"PB",histPBDate,histPBBlob));
ilJPLoad20?.addEventListener("click", ()=>load20(ilJPLoad20,"IL",histILJPDate,histILJPBlob,"JP"));
ilM1Load20?.addEventListener("click", ()=>load20(ilM1Load20,"IL",histILM1Date,histILM1Blob,"M1"));
ilM2Load20?.addEventListener("click", ()=>load20(ilM2Load20,"IL",histILM2Date,histILM2Blob,"M2"));

// -------- run phase 1 --------
function statChipsMMPB(counts){
  const order=["3","3+B","4","4+B","5","5+B"];
  return order.filter(k=>counts[k]).map(k=>`<span class="chip">${k}: ${counts[k]}</span>`).join(" ");
}
function statChipsIL(c){ const order=["3","4","5","6"]; return order.filter(k=>c[k]).map(k=>`<span class="chip">${k}: ${c[k]}</span>`).join(" "); }
function fillGame(batchEl, rowsEl, statsEl, countsEl, batch, stats, isIL){
  batchEl.innerHTML = "";
  (batch||[]).forEach(s=>{
    const li = document.createElement("li");
    li.textContent = s;
    batchEl.appendChild(li);
  });
  const counts = stats?.counts||{};
  statsEl.innerHTML = isIL ? statChipsIL(counts) : statChipsMMPB(counts);
  const rows = stats?.rows||{};
  const keys = Object.keys(rows);
  rowsEl.textContent = keys.length? keys.map(k=>`${k}: ${rows[k].join(', ')}`).join("\n") : "–";
  countsEl.textContent = Object.keys(counts).length ? JSON.stringify(counts) : "";
}

runPhase1?.addEventListener("click", async ()=>{
  press(runPhase1); busy(runPhase1,true,"Running…"); doneBadge.style.display="none";
  const payload = {
    phase: "phase1",
    LATEST_MM: mmPreview.value.trim(),
    LATEST_PB: pbPreview.value.trim(),
    LATEST_IL_JP: ilJPPreview.value.trim(),
    LATEST_IL_M1: ilM1Preview.value.trim(),
    LATEST_IL_M2: ilM2Preview.value.trim(),
    HIST_MM_BLOB: histMMBlob.value,
    HIST_PB_BLOB: histPBBlob.value,
    HIST_IL_JP_BLOB: histILJPBlob.value,
    HIST_IL_M1_BLOB: histILM1Blob.value,
    HIST_IL_M2_BLOB: histILM2Blob.value,
    FEED_MM: $("feedMM").value,
    FEED_PB: $("feedPB").value,
    FEED_IL: $("feedIL").value
  };
  try{
    const data = await getJSON("/run_json", {method:"POST", headers:{'Content-Type':'application/json'}, body: JSON.stringify(payload)});
    if(!data.ok) throw new Error(data.detail || data.error || "Phase 1 failed");
    rawPhase1.textContent = JSON.stringify(data,null,2);
    phase1Path.value = data.saved_path || "";
    doneBadge.style.display = "inline-block";

    // paint results
    fillGame(mmBatch, mmRows, mmStats, mmCounts, data.echo.BATCH_MM, data.echo.HITS_MM, false);
    fillGame(pbBatch, pbRows, pbStats, pbCounts, data.echo.BATCH_PB, data.echo.HITS_PB, false);
    // IL scored vs JP
    fillGame(ilBatch, ilRows, ilStats, ilCounts, data.echo.BATCH_IL, data.echo.HITS_IL_JP, true);

    toast("Phase 1 complete", "ok");
  }catch(e){
    rawPhase1.textContent = String(e);
    toast(e.message||e, "error", 3500);
  }finally{
    busy(runPhase1,false);
  }
});
