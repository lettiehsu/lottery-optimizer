// -------- helpers
const $ = (sel) => document.querySelector(sel);
function pad2(n){ return String(n).padStart(2,'0'); }
function fmtDateMMDDYY(s){ if(!s) return ''; const [m,d,y] = s.split('/'); return `${pad2(+m)}-${pad2(+d)}-${String(+y).slice(-2)}`; }
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
function setText(id, val){ const el=$(id.startsWith('#')?id:('#'+id)); if(el) el.textContent = (val ?? '—'); }
function setVal(id,val){ const el=$(id.startsWith('#')?id:('#'+id)); if(el) el.value = (val ?? ''); }

// -------- CSV upload
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

// -------- Retrieve newest per game/date
async function retrieve(game, date, targetInputId){
  const params = new URLSearchParams({game, date});
  const res = await fetch('/store/get_by_date?'+params.toString());
  const json = await res.json();
  if(!json.ok){ setVal(targetInputId, `Retrieve failed (${game}): ${res.status} ${JSON.stringify(json)}`); return; }
  // Expect row like {mains:[..], bonus:n|null}
  const mains = json.row?.mains ?? [];
  const bonus = ('bonus' in json.row ? json.row.bonus : null);
  setVal(targetInputId, JSON.stringify([mains, bonus]));
}

$('#btnMM')?.addEventListener('click', ()=> retrieve('MM', $('#mm_date').value, 'mm_preview'));
$('#btnPB')?.addEventListener('click', ()=> retrieve('PB', $('#pb_date').value, 'pb_preview'));
$('#btnILJP')?.addEventListener('click',()=> retrieve('IL_JP', $('#il_jp_date').value, 'il_jp_preview'));
$('#btnILM1')?.addEventListener('click',()=> retrieve('IL_M1', $('#il_m1_date').value, 'il_m1_preview'));
$('#btnILM2')?.addEventListener('click',()=> retrieve('IL_M2', $('#il_m2_date').value, 'il_m2_preview'));

// -------- Load 20 history from a start date
document.querySelectorAll('.btnLoad20').forEach(btn=>{
  btn.addEventListener('click', async ()=>{
    const game = btn.dataset.game;
    let from = '';
    let outBox = null;
    if(game==='MM'){ from=$('#hist_mm_from').value; outBox=$('#hist_mm_blob'); }
    if(game==='PB'){ from=$('#hist_pb_from').value; outBox=$('#hist_pb_blob'); }
    if(game==='IL_JP'){ from=$('#hist_il_jp_from').value; outBox=$('#hist_il_jp_blob'); }
    if(game==='IL_M1'){ from=$('#hist_il_m1_from').value; outBox=$('#hist_il_m1_blob'); }
    if(game==='IL_M2'){ from=$('#hist_il_m2_from').value; outBox=$('#hist_il_m2_blob'); }

    const params = new URLSearchParams({game, from, limit:'20'});
    const res = await fetch('/store/get_history?'+params.toString());
    const json = await res.json();
    if(!json.ok){ outBox.value = `Load failed (${game}): ${res.status}\n${JSON.stringify(json)}`; return; }
    // json.blob already formatted by server; fallback to rows if provided
    outBox.value = json.blob || (json.rows||[]).join('\n');
  });
});

// -------- Phase 1 RUN
$('#runPhase1')?.addEventListener('click', async ()=>{
  const payload = {
    phase: 'phase1',
    FEED_MM: $('#feed_mm').value,
    FEED_PB: $('#feed_pb').value,
    FEED_IL: $('#feed_il').value,

    // LATEST_* come from “Retrieve” previews
    LATEST_MM:  $('#mm_preview').value,
    LATEST_PB:  $('#pb_preview').value,
    LATEST_IL_JP: $('#il_jp_preview').value,
    LATEST_IL_M1: $('#il_m1_preview').value,
    LATEST_IL_M2: $('#il_m2_preview').value,

    // history blobs (for exact check & bands)
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
    $('#phase1Path').value = '';
    return;
  }

  $('#phase1Path').value = json.saved_path || '';
  renderPhase1Results(json, {
    mm: $('#mm_date').value,
    pb: $('#pb_date').value,
    il: $('#il_jp_date').value
  });
});

// -------- Phase 1 pretty renderer
function renderPhase1Results(res, dates){
  // Raw JSON panel
  setText('phase1-result-json', JSON.stringify(res, null, 2));

  const echo = res.echo || {};
  // Parse strings like "[[ 10, 14, ...], 5]"
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

  // exact check
  function markBadge(id, ok){
    const el = $('#'+id);
    if(!el) return;
    el.classList.remove('ok','no');
    el.classList.add(ok ? 'ok' : 'no');
    el.textContent = (id==='p1_il_exact' ? 'All three exact: ' : 'Exact: ') + (ok ? 'YES' : 'NO');
  }
  const mmHist = $('#hist_mm_blob').value || '';
  const pbHist = $('#hist_pb_blob').value || '';
  const ilHistAll = [$('#hist_il_jp_blob').value, $('#hist_il_m1_blob').value, $('#hist_il_m2_blob').value].join('\n');

  markBadge('p1_mm_exact', mmLine !== '—' && mmHist.includes(mmLine));
  markBadge('p1_pb_exact', pbLine !== '—' && pbHist.includes(pbLine));

  const okIL =
    (!L_IJP || ilHistAll.includes(line6(L_IJP[0], ilDate))) &&
    (!L_IM1 || ilHistAll.includes(line6(L_IM1[0], ilDate))) &&
    (!L_IM2 || ilHistAll.includes(line6(L_IM2[0], ilDate)));
  markBadge('p1_il_exact', okIL);
}

// -------- Phase 2 (placeholder)
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
