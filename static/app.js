/* static/app.js — Phase 1 date-driven fetch with explicit "Load" buttons */

const R = {
  upload:   '/hist_upload',
  nj:       '/store/nj',        // GET ?game=MM|PB|IL&date=YYYY-MM-DD[&tier=JP|M1|M2]
  hist20:   '/store/hist20',    // GET ?game=MM|PB|IL&start=YYYY-MM-DD[&tier=JP|M1|M2]
  save_nj:  '/store/save_nj',   // POST { dates:{}, nj:{} }
  run_p1:   '/run_json',        // POST
};

const $  = (s)=>document.querySelector(s);
const set = (s,v)=>{ const el=$(s); if(el) el.textContent=v; };
const val = (s)=>($(s)?.value||'').trim();
const setVal=(s,v)=>{ const el=$(s); if(el) el.value=v; };

const NJ    = { MM:null, PB:null, IL_JP:null, IL_M1:null, IL_M2:null };
const DATES = { MM:null, PB:null, IL_JP:null, IL_M1:null, IL_M2:null };

function toISO(dateInputValue){
  // accept "YYYY-MM-DD" or "MM/DD/YYYY"
  if (/^\d{4}-\d{2}-\d{2}$/.test(dateInputValue)) return dateInputValue;
  const m=dateInputValue.match(/^(\d{1,2})\/(\d{1,2})\/(\d{4})$/);
  if (m) return `${m[3]}-${m[1].padStart(2,'0')}-${m[2].padStart(2,'0')}`;
  return '';
}
function fmtPreview(mains, bonus){
  return bonus===null || bonus===undefined
    ? `[${mains.join(', ')}]`
    : `[${mains.join(', ')}] + ${bonus}`;
}
async function getJSON(url){
  const r=await fetch(url,{credentials:'same-origin'});
  if(!r.ok) throw new Error(`${r.status} ${r.statusText}`);
  return r.json();
}
async function postJSON(url,body){
  const r=await fetch(url,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body),credentials:'same-origin'});
  if(!r.ok) throw new Error(`${r.status} ${r.statusText}`);
  return r.json();
}

/* --------- CSV upload ---------- */
(function(){
  const file = $('#upload_csv');
  const over = $('#upload_over');
  const btn  = $('#upload_btn');
  const chosen = $('#upload_selected');
  const out  = $('#upload_result');

  file?.addEventListener('change', ()=>{
    if(file.files?.[0]) chosen.textContent = `${file.files[0].name} (${file.files[0].size} bytes)`;
    else chosen.textContent = '—';
  });

  btn?.addEventListener('click', async ()=>{
    if(!file.files?.length){ out.textContent='No file chosen.'; return; }
    out.textContent='Uploading…';
    const fd=new FormData();
    fd.append('file', file.files[0]);
    if(over?.checked) fd.append('overwrite','on');
    try{
      const r=await fetch(R.upload,{method:'POST',body:fd,credentials:'same-origin'});
      const j=await r.json().catch(()=>null);
      out.textContent = j ? JSON.stringify(j,null,2) : 'Upload did not return JSON.';
    }catch(e){ out.textContent=`Upload failed: ${e.message}`; }
  });
})();

/* --------- Fetch NJ by date (buttons) ---------- */
async function fetchNJ(game, tier, dateSel, previewSel, key){
  const iso = toISO(val(dateSel));
  if(!iso){ set(previewSel,'—'); NJ[key]=null; DATES[key]=null; return; }
  const qs = new URLSearchParams({ game, date: iso });
  if (game==='IL' && tier) qs.set('tier', tier);
  try{
    const j = await getJSON(`${R.nj}?${qs.toString()}`);
    if(!j?.ok) throw new Error('not ok');
    NJ[key]    = { mains:j.mains, bonus:j.bonus };
    DATES[key] = iso;
    set(previewSel, fmtPreview(j.mains, j.bonus));
  }catch(e){
    NJ[key]=null; DATES[key]=null; set(previewSel,'—');
    console.warn('fetchNJ failed', game, tier, e);
  }
}

function bindNJButtons(){
  $('#mm_load')   ?.addEventListener('click', ()=>fetchNJ('MM','',  '#mm_date',   '#mm_preview','MM'));
  $('#pb_load')   ?.addEventListener('click', ()=>fetchNJ('PB','',  '#pb_date',   '#pb_preview','PB'));
  $('#iljp_load') ?.addEventListener('click', ()=>fetchNJ('IL','JP','#il_jp_date','#il_jp_preview','IL_JP'));
  $('#ilm1_load') ?.addEventListener('click', ()=>fetchNJ('IL','M1','#il_m1_date','#il_m1_preview','IL_M1'));
  $('#ilm2_load') ?.addEventListener('click', ()=>fetchNJ('IL','M2','#il_m2_date','#il_m2_preview','IL_M2'));
  $('#load_all')  ?.addEventListener('click', async ()=>{
    await fetchNJ('MM','',  '#mm_date',   '#mm_preview','MM');
    await fetchNJ('PB','',  '#pb_date',   '#pb_preview','PB');
    await fetchNJ('IL','JP','#il_jp_date','#il_jp_preview','IL_JP');
    await fetchNJ('IL','M1','#il_m1_date','#il_m1_preview','IL_M1');
    await fetchNJ('IL','M2','#il_m2_date','#il_m2_preview','IL_M2');
  });
}

/* --------- History: Load 20 ---------- */
async function load20(game, tier, startSel, outSel){
  const iso = toISO(val(startSel));
  if(!iso) return;
  const qs = new URLSearchParams({ game, start: iso });
  if (game==='IL' && tier) qs.set('tier', tier);
  try{
    const j = await getJSON(`${R.hist20}?${qs.toString()}`);
    if(!j?.ok) throw new Error('not ok');
    const lines=(j.rows||[]).map(r=>{
      const d=new Date(r.date);
      const mm=String(d.getMonth()+1).padStart(2,'0');
      const dd=String(d.getDate()).padStart(2,'0');
      const yy=d.getFullYear();
      const mains=(r.mains||[]).join('-');
      const bonus=(r.bonus===null||r.bonus===undefined)?'':` ${String(r.bonus).padStart(2,'0')}`;
      return `${mm}/${dd}/${yy}  ${mains}${bonus}`;
    });
    setVal(outSel, lines.join('\n'));
  }catch(e){ console.warn('hist20 failed', game, tier, e); }
}
function bindHist(){
  $('#mm_hist_load20') ?.addEventListener('click', ()=>load20('MM','',  '#mm_hist_date',  '#HIST_MM_BLOB'));
  $('#pb_hist_load20') ?.addEventListener('click', ()=>load20('PB','',  '#pb_hist_date',  '#HIST_PB_BLOB'));
  $('#il_jp_hist_load20')?.addEventListener('click', ()=>load20('IL','JP','#il_jp_hist_date','#HIST_IL_JP_BLOB'));
  $('#il_m1_hist_load20')?.addEventListener('click', ()=>load20('IL','M1','#il_m1_hist_date','#HIST_IL_M1_BLOB'));
  $('#il_m2_hist_load20')?.addEventListener('click', ()=>load20('IL','M2','#il_m2_hist_date','#HIST_IL_M2_BLOB'));
}

/* --------- Save NJ to history ---------- */
async function saveNJ(){
  try{
    const j = await postJSON(R.save_nj, { dates: DATES, nj: NJ });
    if(j?.ok) alert('Saved to history.');
    else alert('Save failed.');
  }catch(e){ alert(`Save failed: ${e.message}`); }
}

/* --------- Run Phase 1 ---------- */
function getTxt(id){ return ($(id)?.value||'').trim(); }

async function runP1(){
  const missing = Object.entries(NJ).filter(([,v])=>!v).map(([k])=>k);
  if(missing.length){ alert(`Pick dates then click Load for: ${missing.join(', ')}`); return; }

  const body = {
    LATEST_MM:    JSON.stringify([NJ.MM.mains, NJ.MM.bonus]),
    LATEST_PB:    JSON.stringify([NJ.PB.mains, NJ.PB.bonus]),
    LATEST_IL_JP: JSON.stringify([NJ.IL_JP.mains, NJ.IL_JP.bonus]),
    LATEST_IL_M1: JSON.stringify([NJ.IL_M1.mains, NJ.IL_M1.bonus]),
    LATEST_IL_M2: JSON.stringify([NJ.IL_M2.mains, NJ.IL_M2.bonus]),
    FEED_MM:      getTxt('#FEED_MM'),
    FEED_PB:      getTxt('#FEED_PB'),
    FEED_IL:      getTxt('#FEED_IL'),
    HIST_MM_BLOB: getTxt('#HIST_MM_BLOB'),
    HIST_PB_BLOB: getTxt('#HIST_PB_BLOB'),
    HIST_IL_BLOB: `${getTxt('#HIST_IL_JP_BLOB')}\n--M1--\n${getTxt('#HIST_IL_M1_BLOB')}\n--M2--\n${getTxt('#HIST_IL_M2_BLOB')}`,
  };

  try{
    const j = await postJSON(R.run_p1, body);
    if(j?.ok && j.saved_path){
      set('#p1_path', j.saved_path);
      alert('Phase 1 complete.');
    }else{
      alert(`Phase 1 failed: ${j?.error||'unknown error'}`);
    }
  }catch(e){ alert(`Phase 1 failed: ${e.message}`); }
}

/* --------- init ---------- */
document.addEventListener('DOMContentLoaded', ()=>{
  bindNJButtons();
  bindHist();
  $('#save_nj_to_hist')?.addEventListener('click', saveNJ);
  $('#run_p1')?.addEventListener('click', runP1);
  $('#copy_p1')?.addEventListener('click', ()=>{
    const p=$('#p1_path')?.textContent||'';
    if(p && p!=='—') navigator.clipboard.writeText(p);
  });
});
