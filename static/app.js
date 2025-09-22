// ---------- tiny helpers ----------
const $ = (s)=>document.querySelector(s);
const pad2 = (n)=>String(n).padStart(2,'0');
const splitLines = (t)=> (t||'').split(/\r?\n/).filter(Boolean);
function fmtDateMMDDYY(s){ if(!s) return ''; const [m,d,y]=(s||'').split('/'); return `${pad2(+m)}-${pad2(+d)}-${String(+y).slice(-2)}`; }
function setText(id,val){ const el=$('#'+id); if(el) el.textContent=(val??'—'); }
function toInt(x){ const n=parseInt(x,10); return isNaN(n)?null:n; }

// Row parsers used by stats
function parseRowMM_PB(line){
  const parts=line.trim().split(/\s+/);
  if(parts.length<3) return null;
  const mains=parts[1].split('-').map(toInt).filter(x=>x!=null);
  const bonus=toInt(parts[2]);
  if(mains.length!==5||bonus==null) return null;
  return {mains, bonus};
}
function parseRowIL(line){
  const parts=line.trim().split(/\s+/);
  if(parts.length<2) return null;
  const mains=parts[1].split('-').map(toInt).filter(x=>x!=null);
  if(mains.length!==6) return null;
  return {mains};
}
function countMatches(a,b){ const sb=new Set(b.map(Number)); let c=0; for(const n of a) if(sb.has(+n)) c++; return c; }

// ---------- CSV upload ----------
$('#importCsvBtn')?.addEventListener('click', async ()=>{
  const f=$('#importCsvFile')?.files?.[0];
  if(!f){ setText('importResult','No file chosen.'); return; }
  const fd=new FormData();
  fd.append('file',f);
  fd.append('overwrite',$('#overwriteChk')?.checked?'true':'false');
  const res=await fetch('/store/import_csv',{method:'POST',body:fd});
  const json=await res.json();
  setText('importResult', JSON.stringify(json,null,2));
});

// ---------- Retrieve “2nd newest JP per date” ----------
async function retrieve(game,date,targetId){
  const qs=new URLSearchParams({game,date});
  const res=await fetch('/store/get_by_date?'+qs.toString());
  const json=await res.json();
  if(!json.ok){ $('#'+targetId).value=`Retrieve failed (${game}): ${res.status} ${JSON.stringify(json)}`; return; }
  const mains=json.row?.mains??[];
  const bonus=('bonus' in json.row ? json.row.bonus : null);
  $('#'+targetId).value = JSON.stringify([mains, bonus]);
}
$('#btnMM')?.addEventListener('click',()=> retrieve('MM',$('#mm_date').value,'mm_preview'));
$('#btnPB')?.addEventListener('click',()=> retrieve('PB',$('#pb_date').value,'pb_preview'));
$('#btnILJP')?.addEventListener('click',()=> retrieve('IL_JP',$('#il_jp_date').value,'il_jp_preview'));
$('#btnILM1')?.addEventListener('click',()=> retrieve('IL_M1',$('#il_m1_date').value,'il_m1_preview'));
$('#btnILM2')?.addEventListener('click',()=> retrieve('IL_M2',$('#il_m2_date').value,'il_m2_preview'));

// ---------- History “Load 20” buttons (restored) ----------
async function load20(game, fromDate, outTextareaId){
  const qs = new URLSearchParams({game, from:fromDate, limit:'20'});
  const res = await fetch('/store/get_history?'+qs.toString());
  const json = await res.json();
  $('#'+outTextareaId).value = json.ok ? (json.blob || (json.rows||[]).join('\n')) :
                         `Load failed (${game}): ${res.status}\n${JSON.stringify(json)}`;
}
$('#btnLoadMM20') ?.addEventListener('click',()=> load20('MM',   $('#hist_mm_from').value,   'hist_mm_blob'));
$('#btnLoadPB20') ?.addEventListener('click',()=> load20('PB',   $('#hist_pb_from').value,   'hist_pb_blob'));
$('#btnLoadILJP20')?.addEventListener('click',()=> load20('IL_JP',$('#hist_il_jp_from').value,'hist_il_jp_blob'));
$('#btnLoadILM120')?.addEventListener('click',()=> load20('IL_M1',$('#hist_il_m1_from').value,'hist_il_m1_blob'));
$('#btnLoadILM220')?.addEventListener('click',()=> load20('IL_M2',$('#hist_il_m2_from').value,'hist_il_m2_blob'));

// ---------- Phase 1: run + pretty results ----------
function line5(mains,bonus,date){ return `${fmtDateMMDDYY(date)}  ${mains.map(x=>pad2(+x)).join('-')}  ${pad2(bonus??0)}`; }
function line6(mains,date){ return `${fmtDateMMDDYY(date)}  ${mains.map(x=>pad2(+x)).join('-')}`; }
function computeStatsMM_PB(nj,blob){
  if(!nj) return '—';
  const rows=splitLines(blob), mainsNJ=(nj[0]||[]).map(Number), bonusNJ=(nj[1]??null);
  const b={'3':[], '3+B':[], '4':[], '4+B':[], '5':[], '5+B':[]};
  rows.forEach((line,i)=>{
    const r=parseRowMM_PB(line); if(!r) return;
    const m=countMatches(mainsNJ,r.mains), hasB=(bonusNJ!=null && r.bonus===+bonusNJ);
    if(m===3&&!hasB) b['3'].push(i+1); if(m===3&&hasB) b['3+B'].push(i+1);
    if(m===4&&!hasB) b['4'].push(i+1); if(m===4&&hasB) b['4+B'].push(i+1);
    if(m===5&&!hasB) b['5'].push(i+1); if(m===5&&hasB) b['5+B'].push(i+1);
  });
  const lines=[];
  for(const k of ['3','3+B','4','4+B','5','5+B']){
    const arr=b[k]; lines.push(`${k.padEnd(4)}: ${String(arr.length).padStart(2)}  |  rows: ${arr.join(', ')||'—'}`);
  }
  lines.push(`Total rows: ${rows.length}`);
  return lines.join('\n');
}
function computeStatsIL_All(njJP,njM1,njM2,blobJP,blobM1,blobM2){
  function tier(nj,blob,label){
    if(!nj) return `${label}: —`;
    const rows=splitLines(blob), target=(nj[0]||[]).map(Number), bk={3:[],4:[],5:[],6:[]};
    rows.forEach((line,i)=>{ const r=parseRowIL(line); if(!r) return; const m=countMatches(target,r.mains); if(m>=3&&m<=6) bk[m].push(i+1); });
    return [
      `${label} — Total rows: ${rows.length}`,
      `  3-hit : ${String(bk[3].length).padStart(2)}  | rows: ${bk[3].join(', ')||'—'}`,
      `  4-hit : ${String(bk[4].length).padStart(2)}  | rows: ${bk[4].join(', ')||'—'}`,
      `  5-hit : ${String(bk[5].length).padStart(2)}  | rows: ${bk[5].join(', ')||'—'}`,
      `  6-hit : ${String(bk[6].length).padStart(2)}  | rows: ${bk[6].join(', ')||'—'}`,
    ].join('\n');
  }
  return [ tier(njJP,blobJP,'JP'), tier(njM1,blobM1,'M1'), tier(njM2,blobM2,'M2') ].join('\n');
}

$('#runPhase1')?.addEventListener('click', async ()=>{
  const payload={
    phase:'phase1',
    FEED_MM:$('#feed_mm').value, FEED_PB:$('#feed_pb').value, FEED_IL:$('#feed_il').value,
    LATEST_MM:$('#mm_preview').value, LATEST_PB:$('#pb_preview').value,
    LATEST_IL_JP:$('#il_jp_preview').value, LATEST_IL_M1:$('#il_m1_preview').value, LATEST_IL_M2:$('#il_m2_preview').value,
    HIST_MM_BLOB:$('#hist_mm_blob').value, HIST_PB_BLOB:$('#hist_pb_blob').value,
    HIST_IL_JP_BLOB:$('#hist_il_jp_blob').value, HIST_IL_M1_BLOB:$('#hist_il_m1_blob').value, HIST_IL_M2_BLOB:$('#hist_il_m2_blob').value,
  };
  const res=await fetch('/run_json',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
  const json=await res.json();
  setText('phase1-result-json', JSON.stringify(json,null,2));
  if(!json.ok){ $('#phase1Path').value=''; return; }
  $('#phase1Path').value=json.saved_path||'';
  const e=json.echo||{}; const parse=(s)=>{try{return typeof s==='string'?JSON.parse(s):s;}catch{return null;}};
  const L_MM=parse(e.LATEST_MM), L_PB=parse(e.LATEST_PB), L_IJP=parse(e.LATEST_IL_JP), L_IM1=parse(e.LATEST_IL_M1), L_IM2=parse(e.LATEST_IL_M2);
  const mmDate=$('#mm_date').value, pbDate=$('#pb_date').value, ilDate=$('#il_jp_date').value;

  const mmLine=L_MM? `${fmtDateMMDDYY(mmDate)}  ${L_MM[0].map(x=>pad2(+x)).join('-')}  ${pad2(L_MM[1])}` : '—';
  const pbLine=L_PB? `${fmtDateMMDDYY(pbDate)}  ${L_PB[0].map(x=>pad2(+x)).join('-')}  ${pad2(L_PB[1])}` : '—';
  const ilLines=[];
  if
