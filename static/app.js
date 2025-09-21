/* static/app.js — UI logic for Phases 1/2/3 + history + autofill + CSV import */

const RUN1_URL = "/run_json";
const RUN2_URL = "/run_phase2";
const CONFIRM_URL = "/confirm_json";
const RECENT_URL = "/recent";
const AUTOFILL_URL = "/autofill";
const IMPORT_URL = "/hist_import";

function $(id){return document.getElementById(id);}
function el(tag, html){const e=document.createElement(tag); e.innerHTML=html; return e;}
function clear(node){ if(node) node.innerHTML=""; }

async function copyText(text){ try{ await navigator.clipboard.writeText(text); toast("Copied!"); } catch{ window.prompt("Press Ctrl+C to copy:", text); } }
function toast(msg){ const t=document.createElement("div"); t.textContent=msg; t.style.cssText="position:fixed;bottom:16px;left:50%;transform:translateX(-50%);background:#111;color:#fff;padding:8px 12px;border-radius:8px;opacity:.95;z-index:9999"; document.body.appendChild(t); setTimeout(()=>t.remove(),1200); }

let _lastBuyLists={MM:[],PB:[],IL:[]}; let _lastP1Path=""; let _lastP2Path="";

function renderBands(targetId, bands){
  const host=$(targetId); if(!host||!bands) return;
  const items=[["IL","IL middle-50% band"],["MM","MM middle-50% band"],["PB","PB middle-50% band"]];
  clear(host);
  items.forEach(([k,title])=>{
    const b=bands[k]||["–","–"]; const lo=Array.isArray(b)?b[0]:"–"; const hi=Array.isArray(b)?b[1]:"–";
    host.appendChild(el("div", `<div class="card"><div class="card-title">${title}</div><div class="muted">Sum range</div><div class="mono">${lo} – ${hi}</div></div>`));
  });
}
function fillExact(tbodyId, types, src){ const tbody=$(tbodyId); clear(tbody); const defs=JSON.parse(tbody.dataset.types||"[]"); defs.forEach(t=>{const pos=(src&&src[t])?src[t]:[]; tbody.appendChild(el("tr", `<td>${t}</td><td>${pos&&pos.length?pos.join(", "):"—"}</td>`));});}
function fillAgg(tbodyId, types, src){ const tbody=$(tbodyId); clear(tbody); types.forEach(t=>{const pos=(src&&src[t])?src[t]:[]; const count=Array.isArray(pos)?pos.length:0; const freq={}; (pos||[]).forEach(p=>freq[p]=(freq[p]||0)+1); const top=Object.entries(freq).sort((a,b)=>b[1]-a[1]||(+a[0])-(+b[0])).slice(0,8).map(([r,c])=>`${r}(${c})`).join(", "); tbody.appendChild(el("tr", `<td>${t}</td><td>${count}</td><td>${top||"—"}</td>`));});}
function fillBuy(tbodyId, rows, hasBonus=false){ const tbody=$(tbodyId); clear(tbody); (rows||[]).forEach((t,i)=>{const mains=(t.mains||[]).join(", "); const bonus=t.bonus ?? ""; tbody.appendChild(el("tr", `<td>${i+1}</td><td>${mains}</td>${hasBonus?`<td>${bonus}</td>`:""}`));});}
async function getRecent(intoId){ const box=$(intoId); const res=await fetch(RECENT_URL); const data=await res.json().catch(()=>({})); const files=Array.isArray(data.files)?data.files:(Array.isArray(data)?data:[]); box.textContent=files.length?files.join("\n"):"No recent files."; }

/* ===================== PHASE 1 ===================== */
async function runPhase1(){
  const payload={
    LATEST_MM: $("LATEST_MM").value.trim(),
    LATEST_PB: $("LATEST_PB").value.trim(),
    LATEST_IL_JP: $("LATEST_IL_JP").value.trim(),
    LATEST_IL_M1: $("LATEST_IL_M1").value.trim(),
    LATEST_IL_M2: $("LATEST_IL_M2").value.trim(),
    FEED_MM: $("FEED_MM").value.trim(),
    FEED_PB: $("FEED_PB").value.trim(),
    FEED_IL: $("FEED_IL").value.trim(),
    HIST_MM_BLOB: $("HIST_MM_BLOB").value.trim(),
    HIST_PB_BLOB: $("HIST_PB_BLOB").value.trim(),
    HIST_IL_BLOB: $("HIST_IL_BLOB").value.trim()
  };
  const res=await fetch(RUN1_URL,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(payload)});
  let data; try{ data=await res.json(); }catch(e){ alert("Server returned non-JSON."); return; }
  if(!res.ok || !data.ok){ alert("Phase 1 failed: "+(data?.detail||res.status)); return; }

  renderBands("bands", data.bands);
  const e=data.eval_vs_NJ||{};
  fillExact("mm-exact", ["3","3B","4","4B","5","5B"], e.MM||{});
  fillExact("pb-exact", ["3","3B","4","4B","5","5B"], e.PB||{});
  const il=e.IL||{};
  fillExact("iljp-exact", ["3","4","5","6"], il.JP||{});
  fillExact("ilm1-exact", ["3","4","5","6"], il.M1||{});
  fillExact("ilm2-exact", ["3","4","5","6"], il.M2||{});

  _lastP1Path=data.saved_path||"";
  $("p1-saved").textContent="Saved Phase-1 state: "+(_lastP1Path||"(none)");
  $("phase1_path").value=_lastP1Path;
  $("phase1_path_input").value=_lastP1Path;
}

/* ===================== PHASE 2 ===================== */
async function runPhase2(){
  const p1path = $("phase1_path_input").value.trim();
  if(!p1path){ alert("Please paste the saved Phase-1 path first."); return; }
  const res=await fetch(RUN2_URL,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({saved_path:p1path})});
  let data; try{ data=await res.json(); }catch(e){ alert("Server returned non-JSON."); return; }
  if(!res.ok || !data.ok){ alert("Phase 2 failed: "+(data?.detail||res.status)); return; }

  const bl=data.buy_lists||{};
  fillBuy("mm-buy", bl.MM||[], true);
  fillBuy("pb-buy", bl.PB||[], true);
  fillBuy("il-buy", bl.IL||[], false);

  const agg=data.agg_hits||{};
  fillAgg("mm-agg", ["3","3B","4","4B","5","5B"], agg.MM||{});
  fillAgg("pb-agg", ["3","3B","4","4B","5","5B"], agg.PB||{});
  const il=agg.IL||{};
  fillAgg("iljp-agg", ["3","4","5","6"], il.JP||{});
  fillAgg("ilm1-agg", ["3","4","5","6"], il.M1||{});
  fillAgg("ilm2-agg", ["3","4","5","6"], il.M2||{});

  _lastBuyLists={MM: bl.MM||[], PB: bl.PB||[], IL: bl.IL||[]};
  _lastP2Path=data.saved_path||"";
  $("p2-saved").textContent="Saved Phase-2 state: "+(_lastP2Path||"(none)");
  $("phase2_path_confirm").value=_lastP2Path;
  $("phase2_path").value=_lastP2Path;
  renderBands("p2-bands", data.bands);
}

/* ===================== PHASE 3 ===================== */
async function confirmPhase3(){
  const path=$("phase2_path").value.trim();
  if(!path){ alert("Please paste the saved Phase-2 path."); return; }
  let nwj=$("nwj_json").value.trim();
  const payload={ saved_path: path };
  if(nwj){ try{ payload.NWJ=JSON.parse(nwj); } catch(e){ alert("NWJ must be valid JSON (use null, not None)."); return; } }
  const res=await fetch(CONFIRM_URL,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(payload)});
  let data; try{ data=await res.json(); }catch(e){ alert("Server returned non-JSON."); return; }
  if(!res.ok || !data.ok){ alert("Confirm failed: "+(data?.detail||res.status)); return; }
  renderConfirmBoxes(data.confirm_hits||{});
}
function renderConfirmBoxes(hitObj){
  const fillTable=(tbodyId)=>{
    const tbody=$(tbodyId); const defs=JSON.parse(tbody.dataset.types||"[]");
    const src=(()=>{ if(tbodyId.startsWith("mm-")) return hitObj.MM||{};
      if(tbodyId.startsWith("pb-")) return hitObj.PB||{};
      if(tbodyId.startsWith("iljp-")) return (hitObj.IL&&hitObj.IL.JP)||{};
      if(tbodyId.startsWith("ilm1-")) return (hitObj.IL&&hitObj.IL.M1)||{};
      if(tbodyId.startsWith("ilm2-")) return (hitObj.IL&&hitObj.IL.M2)||{}; return {};})();
    clear(tbody); defs.forEach(t=>{ const pos=(src&&src[t])?src[t]:[]; tbody.appendChild(el("tr", `<td>${t}</td><td>${pos&&pos.length?pos.join(", "):"—"}</td>`)); });
  };
  ["mm-rows","pb-rows","iljp-rows","ilm1-rows","ilm2-rows"].forEach(fillTable);
}
function formatBuyListText(tag, rows, hasBonus=false){
  const lines=[`${tag} buy list:`];
  (rows||[]).forEach((t,i)=>{ const mains=(t.mains||[]).join(", "); const bonus=(hasBonus&&t.bonus!=null)?`  [bonus ${t.bonus}]`:""; lines.push(`${String(i+1).padStart(2," ")}. ${mains}${bonus}`); });
  return lines.join("\n");
}

/* ===================== HISTORY HELPERS ===================== */
async function saveNJtoHistory(){
  const payload={};
  function parsePair(txt){ if(!txt) return null; try{ const idx=txt.indexOf("]"); if(idx<0) return null;
    const mains=JSON.parse(txt.slice(0, idx+1)); const bonus=JSON.parse(txt.slice(idx+1).replace(",","").trim()); return [mains, bonus]; }catch{ return null; } }
  function parseSix(txt){ if(!txt) return null; try{ const arr=JSON.parse(txt.replace(/'/g,'"')); if(Array.isArray(arr)&&arr.length===6) return [arr, null]; }catch{} return null; }
  const mm=parsePair($("LATEST_MM").value.trim()); if(mm) payload.LATEST_MM=mm;
  const pb=parsePair($("LATEST_PB").value.trim()); if(pb) payload.LATEST_PB=pb;
  const iljp=parseSix($("LATEST_IL_JP").value.trim()); if(iljp) payload.LATEST_IL_JP=iljp;
  const ilm1=parseSix($("LATEST_IL_M1").value.trim()); if(ilm1) payload.LATEST_IL_M1=ilm1;
  const ilm2=parseSix($("LATEST_IL_M2").value.trim()); if(ilm2) payload.LATEST_IL_M2=ilm2;
  if(!Object.keys(payload).length){ alert("Nothing to save. Fill at least one LATEST_* box."); return; }
  const res=await fetch("/hist_add",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(payload)});
  const data=await res.json().catch(()=>({})); if(!res.ok || !data.ok){ alert("Save failed: "+(data.detail||res.status)); return; }
  toast("Saved to history: "+(data.added||[]).join(", "));
}
async function showBlob(game){
  const res=await fetch("/hist_blob?game="+encodeURIComponent(game));
  const data=await res.json().catch(()=>({})); if(!res.ok || !data.ok){ alert("Unable to fetch BLOB for "+game); return; }
  const box=$("blobView"); box.style.display="block"; box.textContent=data.blob || "(empty)";
}

/* ===================== AUTOFILL ===================== */
async function doAutofill(which){
  const res=await fetch(AUTOFILL_URL);
  let data; try{ data=await res.json(); }catch{ alert("Autofill fetch failed."); return; }
  if(!data.ok){ alert("Autofill error: "+(data.detail||"unknown")); return; }

  if(which==="p1"){ // 3rd newest → fill Phase 1 boxes (MM, PB, IL JP/M1/M2)
    const j=data.phase1_latest||{};
    if(j.LATEST_MM) $("LATEST_MM").value = `[${j.LATEST_MM[0].join(", ")}], ${j.LATEST_MM[1]}`;
    if(j.LATEST_PB) $("LATEST_PB").value = `[${j.LATEST_PB[0].join(", ")}], ${j.LATEST_PB[1]}`;
    if(j.LATEST_IL_JP) $("LATEST_IL_JP").value = `[${j.LATEST_IL_JP[0].join(", ")}]`;
    if(j.LATEST_IL_M1) $("LATEST_IL_M1").value = `[${j.LATEST_IL_M1[0].join(", ")}]`;
    if(j.LATEST_IL_M2) $("LATEST_IL_M2").value = `[${j.LATEST_IL_M2[0].join(", ")}]`;
    toast("Phase 1 LATEST_* filled (3rd newest, including IL if available).");
  }else if(which==="p2"){ // 2nd newest → prefill Phase 1 boxes
    const j=data.phase2_latest||{};
    if(j.LATEST_MM) $("LATEST_MM").value = `[${j.LATEST_MM[0].join(", ")}], ${j.LATEST_MM[1]}`;
    if(j.LATEST_PB) $("LATEST_PB").value = `[${j.LATEST_PB[0].join(", ")}], ${j.LATEST_PB[1]}`;
    if(j.LATEST_IL_JP) $("LATEST_IL_JP").value = `[${j.LATEST_IL_JP[0].join(", ")}]`;
    if(j.LATEST_IL_M1) $("LATEST_IL_M1").value = `[${j.LATEST_IL_M1[0].join(", ")}]`;
    if(j.LATEST_IL_M2) $("LATEST_IL_M2").value = `[${j.LATEST_IL_M2[0].join(", ")}]`;
    toast("Phase 1 LATEST_* prefilled with 2nd newest (including IL). Run Phase 1 next.");
  }else if(which==="p3"){ // newest → fill NWJ JSON box
    const j=data.phase3_latest||{}; const nwj={};
    if(j.LATEST_MM) nwj.LATEST_MM=j.LATEST_MM;
    if(j.LATEST_PB) nwj.LATEST_PB=j.LATEST_PB;
    if(j.LATEST_IL_JP) nwj.LATEST_IL_JP=j.LATEST_IL_JP;
    if(j.LATEST_IL_M1) nwj.LATEST_IL_M1=j.LATEST_IL_M1;
    if(j.LATEST_IL_M2) nwj.LATEST_IL_M2=j.LATEST_IL_M2;
    $("nwj_json").value = JSON.stringify(nwj);
    toast("Phase 3 NWJ filled (newest).");
  }
}

/* ===================== CSV IMPORT ===================== */
async function doImport(){
  const file = $("csvFile").files[0];
  if(!file){ alert("Choose a .csv file first."); return; }
  const fd = new FormData();
  fd.append("file", file, file.name);
  const res = await fetch(IMPORT_URL, { method: "POST", body: fd });
  let data; try{ data=await res.json(); }catch{ $("importResult").textContent="Server returned non-JSON."; return; }
  if(!res.ok || !data.ok){ $("importResult").textContent = JSON.stringify(data, null, 2); return; }
  $("importResult").textContent = JSON.stringify(data.report, null, 2);
  toast("Import complete");
}

/* ===================== EVENTS ===================== */
$("btnRun1")?.addEventListener("click", runPhase1);
$("btnRun2")?.addEventListener("click", runPhase2);
$("btnConfirm")?.addEventListener("click", confirmPhase3);

$("btnRecent")?.addEventListener("click", ()=>getRecent("recentList"));
$("btnRecent2")?.addEventListener("click", ()=>getRecent("recentList"));
$("btnRecent3")?.addEventListener("click", ()=>getRecent("recentList"));

$("btnCopyP1")?.addEventListener("click", ()=>{ if(!_lastP1Path) return alert("No saved Phase-1 path."); copyText(_lastP1Path); });
$("btnCopyP2")?.addEventListener("click", ()=>{ if(!_lastP2Path) return alert("No saved Phase-2 path."); copyText(_lastP2Path); });

$("copyMM")?.addEventListener("click", ()=>{ if(!_lastBuyLists.MM.length) return alert("Run Phase 2 first."); copyText(formatBuyListText("MM", _lastBuyLists.MM, true)); });
$("copyPB")?.addEventListener("click", ()=>{ if(!_lastBuyLists.PB.length) return alert("Run Phase 2 first."); copyText(formatBuyListText("PB", _lastBuyLists.PB, true)); });
$("copyIL")?.addEventListener("click", ()=>{ if(!_lastBuyLists.IL.length) return alert("Run Phase 2 first."); copyText(formatBuyListText("IL", _lastBuyLists.IL, false)); });

$("btnSaveToHist")?.addEventListener("click", saveNJtoHistory);
$("btnShowMMBlob")?.addEventListener("click", ()=>showBlob("MM"));
$("btnShowPBBlob")?.addEventListener("click", ()=>showBlob("PB"));
$("btnShowILBlob")?.addEventListener("click", ()=>showBlob("IL"));

$("btnAutoP1")?.addEventListener("click", ()=>doAutofill("p1"));
$("btnAutoP2")?.addEventListener("click", ()=>doAutofill("p2"));
$("btnAutoP3")?.addEventListener("click", ()=>doAutofill("p3"));

$("btnImport")?.addEventListener("click", doImport);
