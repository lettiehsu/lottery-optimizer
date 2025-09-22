// ---------- helpers ----------
const $ = (id) => document.getElementById(id);
function setLog(msg, isErr=false){ const o=$("runLog"); if(o){o.className=isErr?"log err":"log ok"; o.textContent=msg;} }
async function fetchJSON(url, opts={}){ const r=await fetch(url,opts); if(!r.ok){let d=await r.text(); try{d=JSON.parse(d)}catch{}; throw new Error(typeof d==="string"?d:(d.detail||d.error||r.statusText));} return r.json(); }

// ---------- CSV upload ----------
function hookCSVUpload(){
  const file=$("csvFile"), btn=$("btnImportCSV"), chk=$("csvOverwrite"), pre=$("csvResult");
  if(!file||!btn) return;
  btn.addEventListener("click", async ()=>{
    try{
      if(!file.files || !file.files[0]) return setLog("Choose a CSV file first.", true);
      const fd=new FormData();
      fd.append("file", file.files[0]);
      if(chk) fd.append("overwrite", chk.checked ? "true" : "false");
      const j=await fetchJSON("/store/import_csv",{method:"POST", body:fd});
      pre && (pre.textContent = JSON.stringify(j, null, 2));
      setLog("CSV imported.");
    }catch(e){ pre && (pre.textContent = JSON.stringify({ok:false,error:e.message},null,2)); setLog(`Import failed: ${e.message}`, true); }
  });
}

// ---------- format/extract ----------
function formatLatest(mains, bonus){
  const body=`[${(mains||[]).map(Number).join(",")}]`;
  const b = (bonus==null || Number.isNaN(Number(bonus))) ? "null" : String(Number(bonus));
  return `[${body}, ${b}]`;
}
function extractMainsBonus(row, {forceNoBonus=false}={}){
  let mains=[];
  if(row && Array.isArray(row.mains)&&row.mains.length){ mains=row.mains.map(Number); }
  else{
    const nums=[]; for(let i=1;i<=6;i++){ const k="n"+i; if(row&&row[k]!=null&&row[k]!=="") nums.push(Number(row[k])); }
    mains=nums;
  }
  let bonus=null;
  if(!forceNoBonus){
    if(row && row.bonus!=null) bonus=Number(row.bonus);
    else if(row && row.mb!=null) bonus=Number(row.mb);
    else if(row && row.pb!=null) bonus=Number(row.pb);
  }
  return {mains, bonus};
}

// ---------- API wrappers ----------
async function retrieveByDate(game,date,tier=""){ const p=new URLSearchParams({game,date}); if(tier)p.set("tier",tier); const j=await fetchJSON(`/store/get_by_date?${p.toString()}`); return j.row||j; }
async function loadHistory(gameKey, fromDate, limit=20){ const p=new URLSearchParams({game:gameKey, from:fromDate, limit:String(limit)}); return fetchJSON(`/store/get_history?${p.toString()}`); }
function renderHistoryBlob(rows, kind){
  const out=[]; for(const r of rows||[]){ const d=r.draw_date_mmddyy||r.draw_date||r.date||""; const nums=[]; for(let i=1;i<=6;i++){const k="n"+i; if(r[k]!=null&&r[k]!=="") nums.push(String(r[k]).padStart(2,"0"));} if(kind==="MM"||kind==="PB"){ const five=nums.slice(0,5).join("-"); const b=String(r.bonus ?? r.mb ?? r.pb ?? "").padStart(2,"0"); out.push(`${d}  ${five}  ${b}`);} else { out.push(`${d}  ${nums.join("-")}`);} } return out.join("\n");
}

// ---------- Retrieve buttons ----------
function hookRetrieves(){
  $("btnRetrieveMM")?.addEventListener("click", async()=>{ try{ const d=$("mmDate").value.trim(); if(!d) return setLog("Pick a Mega Millions date.",true); const row=await retrieveByDate("MM",d); const {mains,bonus}=extractMainsBonus(row); $("mmPreview").value=formatLatest(mains,bonus); setLog("MM retrieved."); }catch(e){ setLog(`Retrieve failed (MM): ${e.message}`, true);} });
  $("btnRetrievePB")?.addEventListener("click", async()=>{ try{ const d=$("pbDate").value.trim(); if(!d) return setLog("Pick a Powerball date.",true); const row=await retrieveByDate("PB",d); const {mains,bonus}=extractMainsBonus(row); $("pbPreview").value=formatLatest(mains,bonus); setLog("PB retrieved."); }catch(e){ setLog(`Retrieve failed (PB): ${e.message}`, true);} });
  $("btnRetrieveILJP")?.addEventListener("click", async()=>{ try{ const d=$("ilJPDate").value.trim(); if(!d) return setLog("Pick IL Jackpot date.",true); const row=await retrieveByDate("IL",d,"JP"); const {mains}=extractMainsBonus(row,{forceNoBonus:true}); $("ilJPPreview").value=formatLatest(mains,null); setLog("IL JP retrieved."); }catch(e){ setLog(`Retrieve failed (IL_JP): ${e.message}`, true);} });
  $("btnRetrieveILM1")?.addEventListener("click", async()=>{ try{ const d=$("ilM1Date").value.trim(); if(!d) return setLog("Pick IL Million 1 date.",true); const row=await retrieveByDate("IL",d,"M1"); const {mains}=extractMainsBonus(row,{forceNoBonus:true}); $("ilM1Preview").value=formatLatest(mains,null); setLog("IL M1 retrieved."); }catch(e){ setLog(`Retrieve failed (IL_M1): ${e.message}`, true);} });
  $("btnRetrieveILM2")?.addEventListener("click", async()=>{ try{ const d=$("ilM2Date").value.trim(); if(!d) return setLog("Pick IL Million 2 date.",true); const row=await retrieveByDate("IL",d,"M2"); const {mains}=extractMainsBonus(row,{forceNoBonus:true}); $("ilM2Preview").value=formatLatest(mains,null); setLog("IL M2 retrieved."); }catch(e){ setLog(`Retrieve failed (IL_M2): ${e.message}`, true);} });
}

// ---------- Load 20 ----------
function hookLoad20(){
  $("btnLoad20MM")?.addEventListener("click", async()=>{ try{ const from=$("mmHistDate").value.trim(); const j=await loadHistory("MM",from,20); $("mmHistBlob").value=renderHistoryBlob(j.rows,"MM"); }catch(e){ setLog(`Load failed (MM): ${e.message}`, true);} });
  $("btnLoad20PB")?.addEventListener("click", async()=>{ try{ const from=$("pbHistDate").value.trim(); const j=await loadHistory("PB",from,20); $("pbHistBlob").value=renderHistoryBlob(j.rows,"PB"); }catch(e){ setLog(`Load failed (PB): ${e.message}`, true);} });
  $("btnLoad20ILJP")?.addEventListener("click", async()=>{ try{ const from=$("ilJPHistDate").value.trim(); const j=await loadHistory("IL_JP",from,20); $("ilJPHistBlob").value=renderHistoryBlob(j.rows,"IL"); }catch(e){ setLog(`Load failed (IL_JP): ${e.message}`, true);} });
  $("btnLoad20ILM1")?.addEventListener("click", async()=>{ try{ const from=$("ilM1HistDate").value.trim(); const j=await loadHistory("IL_M1",from,20); $("ilM1HistBlob").value=renderHistoryBlob(j.rows,"IL"); }catch(e){ setLog(`Load failed (IL_M1): ${e.message}`, true);} });
  $("btnLoad20ILM2")?.addEventListener("click", async()=>{ try{ const from=$("ilM2HistDate").value.trim(); const j=await loadHistory("IL_M2",from,20); $("ilM2HistBlob").value=renderHistoryBlob(j.rows,"IL"); }catch(e){ setLog(`Load failed (IL_M2): ${e.message}`, true);} });
}

// ---------- Run Phase 1 ----------
function mustHave(id,label){ const v=$(id)?.value?.trim()||""; if(!v || !v.startsWith("[[")) throw new Error(`${label} is empty or not in '[[..], b]' format`); return v; }
function hookRunPhase1(){
  $("btnRunPhase1")?.addEventListener("click", async()=>{
    try{
      const payload={
        phase:"phase1",
        LATEST_MM: mustHave("mmPreview","LATEST_MM"),
        LATEST_PB: mustHave("pbPreview","LATEST_PB"),
        LATEST_IL_JP: mustHave("ilJPPreview","LATEST_IL_JP"),
        LATEST_IL_M1: mustHave("ilM1Preview","LATEST_IL_M1"),
        LATEST_IL_M2: mustHave("ilM2Preview","LATEST_IL_M2"),
        FEED_MM: $("feedMM")?.value||"",
        FEED_PB: $("feedPB")?.value||"",
        FEED_IL: $("feedIL")?.value||""
      };
      setLog("Running Phase 1...");
      const res=await fetchJSON("/run_json",{method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify(payload)});
      if(res.saved_path) { const p=$("savedPhase1Path"); if(p) p.value=res.saved_path; }
      setLog("Phase 1 complete.");
    }catch(e){ setLog(`Phase 1 failed: ${e.message}`, true); }
  });
}

// ---------- boot ----------
document.addEventListener("DOMContentLoaded", ()=>{
  hookCSVUpload();
  hookRetrieves();
  hookLoad20();
  hookRunPhase1();
  setLog("Ready.");
});
