/* static/app.js — Phase-1 now uses dates only (no LATEST_* inputs).
   We keep:
   - CSV upload
   - NJ fetch by date → previews
   - History Load 20
   - Run Phase 1 using fetched NJ
   - Save current NJ → history
*/

const ROUTES = {
  upload:   '/hist_upload',   // POST form-data: file, overwrite
  nj:       '/store/nj',      // GET ?game=MM|PB|IL&date=YYYY-MM-DD[&tier=JP|M1|M2]
  hist20:   '/store/hist20',  // GET ?game=MM|PB|IL&start=YYYY-MM-DD[&tier=JP|M1|M2]
  save_nj:  '/store/save_nj', // POST { dates:{...}, nj:{...} }
  run_p1:   '/run_json'       // POST
};

// hold fetched values
const NJ = { MM:null, PB:null, IL_JP:null, IL_M1:null, IL_M2:null };
const DATES = { MM:null, PB:null, IL_JP:null, IL_M1:null, IL_M2:null };

const $ = (s)=>document.querySelector(s);
const setText = (s,v)=>{ const el=$(s); if(el) el.textContent=v; };
const setVal = (s,v)=>{ const el=$(s); if(el) el.value=v; };

function ymd(v){
  if(!v) return '';
  if(/^\d{4}-\d{2}-\d{2}$/.test(v)) return v;
  const m=v.match(/^(\d{1,2})[/\-](\d{1,2})[/\-](\d{4})$/);
  if(m) return `${m[3]}-${String(m[1]).padStart(2,'0')}-${String(m[2]).padStart(2,'0')}`;
  return v;
}

function toMMDDYYYY(iso){
  const d=new Date(iso);
  if(isNaN(d)) return iso;
  const mm=String(d.getMonth()+1).padStart(2,'0');
  const dd=String(d.getDate()).padStart(2,'0');
  const yy=d.getFullYear();
  return `${mm}/${dd}/${yy}`;
}

async function getJSON(url){
  const r=await fetch(url,{credentials:'same-origin'});
  if(!r.ok) throw new Error(`${r.status} ${r.statusText}`);
  return await r.json();
}

async function postJSON(url,body){
  const r=await fetch(url,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body),credentials:'same-origin'});
  if(!r.ok) throw new Error(`${r.status} ${r.statusText}`);
  return await r.json();
}

/* ---------- Upload ---------- */
(function bindUpload(){
  const fi=$('#upload_csv'), over=$('#upload_over'), btn=$('#upload_btn');
  const chosen=$('#upload_selected'), out=$('#upload_result');

  fi?.addEventListener('change',()=>{
    chosen.textContent = fi.files?.[0]?.name ? `${fi.files[0].name} (${fi.files[0].size} bytes)` : '—';
  });

  btn?.addEventListener('click', async ()=>{
    if(!fi?.files?.length){ out.textContent='No file chosen.'; return; }
    out.textContent='Uploading…';
    const fd=new FormData();
    fd.append('file', fi.files[0]);
    if(over?.checked) fd.append('overwrite','on');
    try{
      const r=await fetch(ROUTES.upload,{method:'POST',body:fd,credentials:'same-origin'});
      const j=await r.json().catch(()=>null);
      out.textContent=j?JSON.stringify(j,null,2):'Upload did not return JSON.';
    }catch(e){ out.textContent=`Upload failed: ${e.message}`; }
  });
})();

/* ---------- Fetch NJ by date ---------- */
function previewText(mains, bonus){
  const b = (bonus===null || bonus===undefined) ? '' : ` + ${bonus}`;
  return `[${mains.join(', ')}]${b}`;
}

async function loadNJ(game, tier, dateSel, previewSel, key){
  const dateISO = ymd($(dateSel)?.value);
  if(!dateISO) return;
  const qs = new URLSearchParams({ game, date: dateISO });
  if(game==='IL' && tier) qs.set('tier', tier);

  try{
    const j = await getJSON(`${ROUTES.nj}?${qs.toString()}`);
    if(!j?.ok) throw new Error('not ok');
    NJ[key] = { mains: j.mains, bonus: j.bonus };
    DATES[key] = dateISO;
    setText(previewSel, previewText(j.mains, j.bonus));
  }catch(e){
    setText(previewSel, '—');
    NJ[key]=null; DATES[key]=null;
    console.warn('NJ fetch failed', game, tier, e);
  }
}

function bindNJDatePickers(){
  $('#mm_date')   ?.addEventListener('change', ()=>loadNJ('MM','',  '#mm_date',   '#mm_preview',   'MM'));
  $('#pb_date')   ?.addEventListener('change', ()=>loadNJ('PB','',  '#pb_date',   '#pb_preview',   'PB'));
  $('#il_jp_date')?.addEventListener('change', ()=>loadNJ('IL','JP','#il_jp_date','#il_jp_preview','IL_JP'));
  $('#il_m1_date')?.addEventListener('change', ()=>loadNJ('IL','M1','#il_m1_date','#il_m1_preview','IL_M1'));
  $('#il_m2_date')?.addEventListener('change', ()=>loadNJ('IL','M2','#il_m2_date','#il_m2_preview','IL_M2'));
}

/* ---------- History Load 20 ---------- */
async function loadHist20(game, tier, startSel, outSel){
  const startISO = ymd($(startSel)?.value);
  if(!startISO) return;
  const qs = new URLSearchParams({ game, start: startISO });
  if(game==='IL' && tier) qs.set('tier', tier);

  try{
    const j = await getJSON(`${ROUTES.hist20}?${qs.toString()}`);
    if(!j?.ok) throw new Error('not ok');
    const lines = (j.rows||[]).map(r=>{
      const d = toMMDDYYYY(r.date);
      const mains = (r.mains||[]).join('-');
      const bonus = (r.bonus===null||r.bonus===undefined)?'':` ${String(r.bonus).padStart(2,'0')}`;
      return `${d}  ${mains}${bonus}`;
    });
    setVal(outSel, lines.join('\n'));
  }catch(e){ console.warn('hist20 failed', game, tier, e); }
}

function bindHistory(){
  $('#mm_hist_load20')?.addEventListener('click', ()=>loadHist20('MM','',  '#mm_hist_date',  '#HIST_MM_BLOB'));
  $('#pb_hist_load20')?.addEventListener('click', ()=>loadHist20('PB','',  '#pb_hist_date',  '#HIST_PB_BLOB'));
  $('#il_jp_hist_load20')?.addEventListener('click', ()=>loadHist20('IL','JP','#il_jp_hist_date','#HIST_IL_JP_BLOB'));
  $('#il_m1_hist_load20')?.addEventListener('click', ()=>loadHist20('IL','M1','#il_m1_hist_date','#HIST_IL_M1_BLOB'));
  $('#il_m2_hist_load20')?.addEventListener('click', ()=>loadHist20('IL','M2','#il_m2_hist_date','#HIST_IL_M2_BLOB'));
}

/* ---------- Save current NJ to history ---------- */
async function saveNJToHistory(){
  try{
    const body = { dates:DATES, nj:NJ };
    const j = await postJSON(ROUTES.save_nj, body);
    if(j?.ok) alert('Saved to history.'); else alert('Save failed.');
  }catch(e){ alert(`Save failed: ${e.message}`); }
}

/* ---------- Run Phase 1 ---------- */
function getVal(sel){ return $(sel)?.value?.trim() || ''; }

async function runPhase1(){
  // validate we have fetched NJ
  const missing = Object.entries(NJ).filter(([k,v])=>!v);
  if(missing.length){
    alert(`Pick dates to fetch: ${missing.map(([k])=>k).join(', ')}`);
    return;
  }

  const body = {
    // NJ comes from our state
    LATEST_MM:   JSON.stringify([NJ.MM.mains,   NJ.MM.bonus]),
    LATEST_PB:   JSON.stringify([NJ.PB.mains,   NJ.PB.bonus]),
    LATEST_IL_JP:JSON.stringify([NJ.IL_JP.mains,NJ.IL_JP.bonus]),
    LATEST_IL_M1:JSON.stringify([NJ.IL_M1.mains,NJ.IL_M1.bonus]),
    LATEST_IL_M2:JSON.stringify([NJ.IL_M2.mains,NJ.IL_M2.bonus]),
    // Feeds & history blobs
    FEED_MM:     getVal('#FEED_MM'),
    FEED_PB:     getVal('#FEED_PB'),
    FEED_IL:     getVal('#FEED_IL'),
    HIST_MM_BLOB:getVal('#HIST_MM_BLOB'),
    HIST_PB_BLOB:getVal('#HIST_PB_BLOB'),
    HIST_IL_BLOB:`${getVal('#HIST_IL_JP_BLOB')}\n--M1--\n${getVal('#HIST_IL_M1_BLOB')}\n--M2--\n${getVal('#HIST_IL_M2_BLOB')}`
  };

  try{
    const res = await postJSON(ROUTES.run_p1, body);
    if(res?.ok && res.saved_path){
      setText('#p1_path', res.saved_path);
      alert('Phase 1 complete.');
    }else{
      alert(`Phase 1 failed: ${res?.error || 'unknown error'}`);
    }
  }catch(e){ alert(`Phase 1 failed: ${e.message}`); }
}

/* ---------- init ---------- */
document.addEventListener('DOMContentLoaded', ()=>{
  bindNJDatePickers();
  bindHistory();

  $('#run_p1')?.addEventListener('click', runPhase1);
  $('#copy_p1')?.addEventListener('click', ()=>{
    const p=$('#p1_path')?.textContent||'';
    if(p && p!=='—') navigator.clipboard.writeText(p);
  });
  $('#save_nj_to_hist')?.addEventListener('click', saveNJToHistory);
});
