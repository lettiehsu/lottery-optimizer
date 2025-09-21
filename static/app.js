/* static/app.js — complete
   - CSV upload → /hist_upload
   - Phase-1 date pickers fetch NJ rows → /store/nj
   - History “Load 20” fetches → /store/hist20
   - Run Phase-1 → /run_json (kept minimal)
*/

/////////////////////////
// Config (adjust URLs)
/////////////////////////
const ROUTES = {
  upload:     '/hist_upload',    // POST form-data: file, overwrite=("on"|"")
  nj:         '/store/nj',       // GET ?game=MM|PB|IL&date=YYYY-MM-DD[&tier=JP|M1|M2]
  hist20:     '/store/hist20',   // GET ?game=MM|PB|IL&start=YYYY-MM-DD[&tier=JP|M1|M2]
  run_p1:     '/run_json'        // POST application/json
};

/////////////////////////
// Tiny helpers
/////////////////////////
const $ = (sel) => document.querySelector(sel);
const setVal = (sel, v) => { const el = $(sel); if (el) el.value = v; };
const setText = (sel, v) => { const el = $(sel); if (el) el.textContent = v; };

function ymd(x) {
  if (!x) return '';
  if (/^\d{4}-\d{2}-\d{2}$/.test(x)) return x;
  const m = x.match(/^(\d{1,2})[/\-](\d{1,2})[/\-](\d{4})$/);
  if (m) {
    return `${m[3]}-${String(m[1]).padStart(2,'0')}-${String(m[2]).padStart(2,'0')}`;
  }
  return x;
}

function toMMDDYYYY(iso) {
  const d = new Date(iso);
  if (isNaN(d)) return iso;
  const mm = String(d.getMonth()+1).padStart(2,'0');
  const dd = String(d.getDate()).padStart(2,'0');
  const yy = d.getFullYear();
  return `${mm}/${dd}/${yy}`;
}

async function getJSON(url) {
  const r = await fetch(url, { credentials:'same-origin' });
  if (!r.ok) throw new Error(`${r.status} ${r.statusText}`);
  return await r.json();
}

async function postJSON(url, body) {
  const r = await fetch(url, {
    method:'POST',
    headers:{ 'Content-Type':'application/json' },
    body: JSON.stringify(body),
    credentials:'same-origin'
  });
  if (!r.ok) throw new Error(`${r.status} ${r.statusText}`);
  return await r.json();
}

/////////////////////////
// CSV Upload
/////////////////////////
(function bindUpload() {
  const fi = $('#upload_csv');
  const over = $('#upload_over');
  const btn = $('#upload_btn');
  const chosen = $('#upload_selected');
  const out = $('#upload_result');

  fi?.addEventListener('change', () => {
    chosen.textContent = fi.files?.[0]?.name ? `${fi.files[0].name} (${fi.files[0].size} bytes)` : '—';
  });

  btn?.addEventListener('click', async () => {
    if (!fi?.files?.length) {
      out.textContent = 'No file chosen.';
      return;
    }
    out.textContent = 'Uploading…';
    const fd = new FormData();
    fd.append('file', fi.files[0]);
    if (over?.checked) fd.append('overwrite', 'on');

    try {
      const r = await fetch(ROUTES.upload, { method:'POST', body:fd, credentials:'same-origin' });
      const j = await r.json().catch(() => null);
      out.textContent = j ? JSON.stringify(j, null, 2) : 'Upload did not return JSON.';
    } catch (e) {
      out.textContent = `Upload failed: ${e.message}`;
    }
  });
})();

/////////////////////////
// Phase-1: NJ by date
/////////////////////////
function fmtNJ(mains, bonus) {
  return JSON.stringify([mains, bonus]);
}

async function loadNJByDate(game, tier, dateSel, outSel) {
  const dateISO = ymd($(dateSel)?.value);
  if (!dateISO) return;
  const qp = new URLSearchParams({ game, date: dateISO });
  if (game === 'IL' && tier) qp.set('tier', tier);

  try {
    const j = await getJSON(`${ROUTES.nj}?${qp.toString()}`);
    if (!j?.ok) throw new Error('not ok');
    setVal(outSel, fmtNJ(j.mains, j.bonus));
  } catch (e) {
    console.warn('loadNJByDate failed', game, tier, e);
  }
}

function bindPhase1DatePickers() {
  $('#mm_date')?.addEventListener('change', () => loadNJByDate('MM', '', '#mm_date', '#LATEST_MM'));
  $('#pb_date')?.addEventListener('change', () => loadNJByDate('PB', '', '#pb_date', '#LATEST_PB'));
  $('#il_jp_date')?.addEventListener('change', () => loadNJByDate('IL', 'JP', '#il_jp_date', '#LATEST_IL_JP'));
  $('#il_m1_date')?.addEventListener('change', () => loadNJByDate('IL', 'M1', '#il_m1_date', '#LATEST_IL_M1'));
  $('#il_m2_date')?.addEventListener('change', () => loadNJByDate('IL', 'M2', '#il_m2_date', '#LATEST_IL_M2'));
}

/////////////////////////
// History: Load 20
/////////////////////////
async function loadHist20(game, tier, startSel, textSel) {
  const startISO = ymd($(startSel)?.value);
  if (!startISO) return;
  const qp = new URLSearchParams({ game, start: startISO });
  if (game === 'IL' && tier) qp.set('tier', tier);

  try {
    const j = await getJSON(`${ROUTES.hist20}?${qp.toString()}`);
    if (!j?.ok) throw new Error('not ok');

    const lines = (j.rows || []).map(r => {
      const d = toMMDDYYYY(r.date);
      const mains = (r.mains || []).join('-');
      const bonus = (r.bonus === null || r.bonus === undefined) ? '' : ` ${String(r.bonus).padStart(2,'0')}`;
      return `${d}  ${mains}${bonus}`;
    });
    setVal(textSel, lines.join('\n'));
  } catch (e) {
    console.warn('loadHist20 failed', game, tier, e);
  }
}

function bindHistoryButtons() {
  $('#mm_hist_load20')?.addEventListener('click', () => loadHist20('MM', '', '#mm_hist_date', '#HIST_MM_BLOB'));
  $('#pb_hist_load20')?.addEventListener('click', () => loadHist20('PB', '', '#pb_hist_date', '#HIST_PB_BLOB'));
  $('#il_jp_hist_load20')?.addEventListener('click', () => loadHist20('IL', 'JP', '#il_jp_hist_date', '#HIST_IL_JP_BLOB'));
  $('#il_m1_hist_load20')?.addEventListener('click', () => loadHist20('IL', 'M1', '#il_m1_hist_date', '#HIST_IL_M1_BLOB'));
  $('#il_m2_hist_load20')?.addEventListener('click', () => loadHist20('IL', 'M2', '#il_m2_hist_date', '#HIST_IL_M2_BLOB'));
}

/////////////////////////
// Run Phase-1 (minimal)
/////////////////////////
function getVal(sel) { return $(sel)?.value?.trim() || ''; }

async function runPhase1() {
  const body = {
    LATEST_MM:   getVal('#LATEST_MM'),
    LATEST_PB:   getVal('#LATEST_PB'),
    LATEST_IL_JP:getVal('#LATEST_IL_JP'),
    LATEST_IL_M1:getVal('#LATEST_IL_M1'),
    LATEST_IL_M2:getVal('#LATEST_IL_M2'),
    FEED_MM:     getVal('#FEED_MM'),
    FEED_PB:     getVal('#FEED_PB'),
    FEED_IL:     getVal('#FEED_IL'),
    HIST_MM_BLOB:getVal('#HIST_MM_BLOB'),
    HIST_PB_BLOB:getVal('#HIST_PB_BLOB'),
    HIST_IL_BLOB:`${getVal('#HIST_IL_JP_BLOB')}\n--M1--\n${getVal('#HIST_IL_M1_BLOB')}\n--M2--\n${getVal('#HIST_IL_M2_BLOB')}`
  };

  try {
    const res = await postJSON(ROUTES.run_p1, body);
    if (res?.ok && res.saved_path) {
      setText('#p1_path', res.saved_path);
      alert('Phase 1 complete.');
    } else {
      alert(`Phase 1 failed: ${res?.error || 'unknown error'}`);
    }
  } catch (e) {
    alert(`Phase 1 failed: ${e.message}`);
  }
}

/////////////////////////
// Init
/////////////////////////
document.addEventListener('DOMContentLoaded', () => {
  bindUpload();
  bindPhase1DatePickers();
  bindHistoryButtons();

  $('#run_p1')?.addEventListener('click', runPhase1);
  $('#copy_p1')?.addEventListener('click', () => {
    const p = $('#p1_path')?.textContent || '';
    if (!p || p === '—') return;
    navigator.clipboard.writeText(p);
  });
});

/* bindUpload is above, but exported here to make sure it exists if called twice */
function bindUpload(){
  /* already bound in the IIFE; no-op here to avoid duplication */
}
