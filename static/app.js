// ===== helpers =====
const $ = (sel) => document.querySelector(sel);
function pad2(n){ return String(n).padStart(2,'0'); }
function fmtDateMMDDYY(s){ if(!s) return ''; const [m,d,y] = (s||'').split('/'); return `${pad2(+m)}-${pad2(+d)}-${String(+y).slice(-2)}`; }
function toInt(x){ const n = parseInt(x,10); return isNaN(n)?null:n; }
function setText(id, val){ const el=$(id.startsWith('#')?id:('#'+id)); if(el) el.textContent = (val ?? '—'); }
function setVal(id,val){ const el=$(id.startsWith('#')?id:('#'+id)); if(el) el.value = (val ?? ''); }
function splitLines(txt){ return (txt||'').split(/\r?\n/).filter(Boolean); }

// Build display lines
function line5(mains, bonus, date){
  const d = fmtDateMMDDYY(date);
  const t = (mains||[]).map(x=>pad2(+x));
  return `${d}  ${t.join('-')}  ${pad2(bonus??0)}`;
}
function line6(mains, date){
  const d = fmtDateMMDDYY(date);
  const t = (mains||[]).map(x=>pad2(+x));
  return `${d}  ${t.join('-')}`;
}

// Parse history rows
function parseRowMM_PB(line){
  // mm-dd-yy  n1-n2-n3-n4-n5  BB
  const parts = line.trim().split(/\s+/);
  if(parts.length < 3) return null;
  const nums = parts[1].split('-').map(toInt).filter(x=>x!=null);
  const bonus = toInt(parts[2]);
  if(nums.length!==5 || bonus==null) return null;
  return { mains: nums, bonus };
}
function parseRowIL(line){
  // mm-dd-yy  A-B-C-D-E-F
  const parts = line.trim().split(/\s+/);
  if(parts.length < 2) return null;
  const nums = parts[1].split('-').map(toInt).filter(x=>x!=null);
  if(nums.length!==6) return null;
  return { mains: nums };
}

// ===== CSV upload =====
$('#importCsvBtn')?.addEventListener('click', async ()=>{
  const f = $('#importCsvFile')?.files?.[0];
  if(!f){ setText('importResult','No file chosen.'); return; }
  const fd = new FormData();
  fd.append('file', f);
  fd.append('overwrite', $('#overwriteChk')?.checked ? 'true':'false');
  const res = await fetch('/store/import_csv',{method:'POST', body:fd});
  const json = await res.json();
  setText('importResult', JSON.stringify(json, null, 2));
});

// ===== Retrieve newest per game/date =====
async function retrieve(game, date, targetInputId){
  const params = new URLSearchParams({game, date});
  const res = await fetch('/store/get_by_date?'+params.toString());
  const json = await res.json();
  if(!json.ok){ setVal(targetInputId, `Retrieve failed (${game}): ${res.status} ${JSON.stringify(json)}`); return; }
  const mains = json.row?.mains ?? [];
  const bonus = ('bonus' in json.row ? json.row.bonus : null);
  setVal(targetInputId, JSON.stringify([mains, bonus]));
}

$('#btnMM')?.addEventListener('click', ()=> retrieve('MM', $('#mm_date').value, 'mm_preview'));
$('#btnPB')?.addEventListener('click', ()=> retrieve('PB', $('#pb_date').value, 'pb_preview'));
$('#btnILJP')?.addEventListener('click',()=> retrieve('IL_JP', $('#il_jp_date').value, 'il_jp_preview'));
$('#btnILM1')?.addEventListener('click',()=> retrieve('IL_M1', $('#il_m1_date').value, 'il_m1_preview'));
$('#btnILM2')?.addEventListener('click',()=> retrieve('IL_M2', $('#il_m2_date').value, 'il_m2_preview'));

// ===== Load history with custom limit =====
document.querySelectorAll('.btn btnLoad,.btn.btnLoad').forEach(b=>b.remove()); // hot reload guard
document.querySelectorAll('.btnLoad').forEach(btn=>{
  btn.addEventListener('click', async ()=>{
    const game = btn.dataset.game;
    let from='', limit=50, outBox=null;
    if(game==='MM'){ from=$('#hist_mm_from').value; limit=+($('#hist_mm_limit').value||50); outBox=$('#hist_mm_blob'); }
    if(game==='PB'){ from=$('#hist_pb_from').value; limit=+($('#hist_pb_limit').value||50); outBox=$('#hist_pb_blob'); }
    if(game==='IL_JP'){ from=$('#hist_il_jp_from').value; limit=+($('#hist_il_jp_limit').value||50); outBox=$('#hist_il_jp_blob'); }
    if(game==='IL_M1'){ from=$('#hist_il_m1_from').value; limit=+($('#hist_il_m1_limit').value||50); outBox=$('#hist_il_m1_blob'); }
    if(game==='IL_M2'){ from=$('#hist_il_m2_from').value; limit=+($('#hist_il_m2_limit').value||50); outBox=$('#hist_il_m2_blob'); }

    const params = new URLSearchParams({game, from, limit:String(limit)});
    const res = await fetch('/store/get_history?'+params.toString());
    const json = await res.json();
    if(!json.ok){ outBox.value = `Load failed (${game}): ${res.status}\n${JSON.stringify(json)}`; return; }
    outBox.value = json.blob || (json.rows||[]).join('\n');
  });
});

// ===== Phase 1 RUN =====
$('#runPhase1')?.addEventListener('click', async ()=>{
  const payload = {
    phase: 'phase1',
    FEED_MM: $('#feed_mm').value,
    FEED_PB: $('#feed_pb').value,
    FEED_IL: $('#feed_il').value,

    LATEST_MM:  $('#mm_preview').value,
    LATEST_PB:  $('#pb_preview').value,
    LATEST_IL_JP: $('#il_jp_preview').value,
    LATEST_IL_M1: $('#il_m1_preview').value,
    LATEST_IL_M2: $('#il_m2_preview').value,

    HIST_MM_BLOB: $('#hist_mm_blob').value,
    HIST_PB_BLOB: $('#hist_pb_blob').value,
    HIST_IL_JP_BLOB: $('#hist_il_jp_blob').value,
    HIST_IL_M1_BLOB: $('#hist_il_m1_blob').value,
    HIST_IL_M2_BLOB: $('#hist_il_m2_blob').value,
  };

  const res = await fetch('/run_json', {
    method:'POST',
    headers:{'Content-Type':'application/json'},
    body: JSON.stringify(payload)
  });
  const json = await res.json();

  if(!json.ok){
    setText('phase1-result-json', JSON.stringify(json, null, 2));
    $('#p1_mm_line').textContent = '—';
    $('#p1_pb_line').textContent = '—';
    $('#p1_il_lines').textContent = '—';
    setText('p1_mm_stats','—'); setText('p1_pb_stats','—'); setText('p1_il_stats','—');
    $('#phase1Path').value = '';
    ['p1_mm_batch','p1_mm_pos','p1_pb_batch','p1_pb_pos','p1_il_batch','p1_il_pos'].forEach(id=>setText(id,'—'));
    return;
  }

  $('#phase1Path').value = json.saved_path || '';
  renderPhase1Results(json, {
    mm: $('#mm_date').value,
    pb: $('#pb_date').value,
    il: $('#il_jp_date').value
  });
});

// ===== Stats helpers =====
function countMatches(a, b){
  let c = 0;
  const bs = new Set(b.map(Number));
  for(const n of a) if(bs.has(+n)) c++;
  return c;
}

function computeStatsMM_PB(nj, blob){
  if(!nj) return '—';
  const rows = splitLines(blob);
  const mainsNJ = (nj[0]||[]).map(Number);
  const bonusNJ = (nj[1]??null);

  const buckets = { '3':[], '3+B':[], '4':[], '4+B':[], '5':[], '5+B':[] };

  rows.forEach((line, idx)=>{
    const r = parseRowMM_PB(line);
    if(!r) return;
    const m = countMatches(mainsNJ, r.mains);
    const hasBonus = (bonusNJ!=null && r.bonus===+bonusNJ);
    if(m===3 && !hasBonus) buckets['3'].push(idx+1);
    if(m===3 && hasBonus)  buckets['3+B'].push(idx+1);
    if(m===4 && !hasBonus) buckets['4'].push(idx+1);
    if(m===4 && hasBonus)  buckets['4+B'].push(idx+1);
    if(m===5 && !hasBonus) buckets['5'].push(idx+1);
    if(m===5 && hasBonus)  buckets['5+B'].push(idx+1);
  });

  const lines = [];
  for(const key of ['3','3+B','4','4+B','5','5+B']){
    const arr = buckets[key];
    lines.push(`${key.padEnd(4)}: ${String(arr.length).padStart(2)}  |  rows: ${arr.join(', ') || '—'}`);
  }
  lines.push(`Total rows: ${rows.length}`);
  return lines.join('\n');
}

// NEW: IL stats for 3/4/5/6 matches (no bonus) by tier
function computeStatsIL_All(njJP, njM1, njM2, blobJP, blobM1, blobM2){
  function tierReport(nj, blob, label){
    if(!nj) return `${label}: —`;
    const rows = splitLines(blob);
    const target = (nj[0]||[]).map(Number);
    const buckets = { 3:[], 4:[], 5:[], 6:[] };

    rows.forEach((line, i)=>{
      const r = parseRowIL(line);
      if(!r) return;
      const m = countMatches(target, r.mains);
      if(m>=3 && m<=6) buckets[m].push(i+1);
    });

    const lines = [
      `${label} — Total rows: ${rows.length}`,
      `  3-hit : ${String(buckets[3].length).padStart(2)}  | rows: ${buckets[3].join(', ')||'—'}`,
      `  4-hit : ${String(buckets[4].length).padStart(2)}  | rows: ${buckets[4].join(', ')||'—'}`,
      `  5-hit : ${String(buckets[5].length).padStart(2)}  | rows: ${buckets[5].join(', ')||'—'}`,
      `  6-hit : ${String(buckets[6].length).padStart(2)}  | rows: ${buckets[6].join(', ')||'—'}`,
    ];
    return lines.join('\n');
  }

  return [
    tierReport(njJP, blobJP, 'JP'),
    tierReport(njM1, blobM1, 'M1'),
    tierReport(njM2, blobM2, 'M2'),
  ].join('\n');
}

// ===== Phase 1 pretty renderer + stats =====
function renderPhase1Results(res, dates){
  setText('phase1-result-json', JSON.stringify(res, null, 2));

  const echo = res.echo || {};
  function parseMaybe(s){ try{ return (typeof s==='string') ? JSON.parse(s) : s; }catch{ return null; } }

  const L_MM  = parseMaybe(echo.LATEST_MM);
  const L_PB  = parseMaybe(echo.LATEST_PB);
  const L_IJP = parseMaybe(echo.LATEST_IL_JP);
  const L_IM1 = parseMaybe(echo.LATEST_IL_M1);
  const L_IM2 = parseMaybe(echo.LATEST_IL_M2);

  const mmDate = dates?.mm || '';
  const pbDate = dates?.pb || '';
  const ilDate = dates?.il || '';

  const mmLine = L_MM ? line5(L_MM[0], L_MM[1], mmDate) : '—';
  const pbLine = L_PB ? line5(L_PB[0], L_PB[1], pbDate) : '—';
  const ilLines = [];
  if (L_IJP) ilLines.push('JP  ' + line6(L_IJP[0], ilDate));
  if (L_IM1) ilLines.push('M1  ' + line6(L_IM1[0], ilDate));
  if (L_IM2) ilLines.push('M2  ' + line6(L_IM2[0], ilDate));

  setText('p1_mm_line', mmLine);
  setText('p1_pb_line', pbLine);
  setText('p1_il_lines', ilLines.join('\n') || '—');

  // exact badges
  function markBadge(id, ok){
    const el = $('#'+id);
    if(!el) return;
    el.classList.remove('ok','no');
    el.classList.add(ok ? 'ok' : 'no');
    el.textContent = (id==='p1_il_exact' ? 'All three exact: ' : 'Exact: ') + (ok ? 'YES' : 'NO');
  }
  const mmHist = $('#hist_mm_blob').value || '';
  const pbHist = $('#hist_pb_blob').value || '';
  const ilJPHist = $('#hist_il_jp_blob').value || '';
  const ilM1Hist = $('#hist_il_m1_blob').value || '';
  const ilM2Hist = $('#hist_il_m2_blob').value || '';

  markBadge('p1_mm_exact', mmLine !== '—' && mmHist.includes(mmLine));
  markBadge('p1_pb_exact', pbLine !== '—' && pbHist.includes(pbLine));
  const okIL =
    (!L_IJP || ilJPHist.includes(line6(L_IJP[0], ilDate))) &&
    (!L_IM1 || ilM1Hist.includes(line6(L_IM1[0], ilDate))) &&
    (!L_IM2 || ilM2Hist.includes(line6(L_IM2[0], ilDate)));
  markBadge('p1_il_exact', okIL);

  // Batch size & position
  function posInBatch(blobText, targetLine){
    if(!blobText || !targetLine) return {size:0, pos:'—'};
    const rows = splitLines(blobText);
    const idx = rows.indexOf(targetLine);
    return { size: rows.length, pos: (idx>=0 ? (idx+1) : '—') };
  }
  const mmBP = posInBatch(mmHist, mmLine);
  const pbBP = posInBatch(pbHist, pbLine);
  const ilJPBP = posInBatch(ilJPHist, L_IJP ? line6(L_IJP[0], ilDate) : '');
  const ilM1BP = posInBatch(ilM1Hist, L_IM1 ? line6(L_IM1[0], ilDate) : '');
  const ilM2BP = posInBatch(ilM2Hist, L_IM2 ? line6(L_IM2[0], ilDate) : '');

  setText('p1_mm_batch', mmBP.size || '0');
  setText('p1_mm_pos', mmBP.pos);
  setText('p1_pb_batch', pbBP.size || '0');
  setText('p1_pb_pos', pbBP.pos);
  setText('p1_il_batch', [ilJPBP.size, ilM1BP.size, ilM2BP.size].join('/'));
  setText('p1_il_pos', [ilJPBP.pos, ilM1BP.pos, ilM2BP.pos].join('/'));

  // Stats
  setText('p1_mm_stats', L_MM ? computeStatsMM_PB(L_MM, mmHist) : '—');
  setText('p1_pb_stats', L_PB ? computeStatsMM_PB(L_PB, pbHist) : '—');
  setText('p1_il_stats', computeStatsIL_All(L_IJP, L_IM1, L_IM2, ilJPHist, ilM1Hist, ilM2Hist));
}

// ===== Phase 2 placeholder =====
$('#btn_run_p2')?.addEventListener('click', ()=>{
  const game = $('#p2_game').value;
  const date = $('#p2_date').value;
  const hotN = +($('#p2_hot_n').value||0);
  const ovN  = +($('#p2_overdue_n').value||0);
  $('#p2_output').textContent = [
    `Game: ${game}`,
    `Date: ${date}`,
    `Hot N: ${hotN}`,
    `Overdue N: ${ovN}`,
    '',
    '→ Connect to your backend Phase-2 logic.'
  ].join('\n');
});
