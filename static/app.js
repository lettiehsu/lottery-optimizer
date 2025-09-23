/* static/app.js — complete
   - CSV upload -> /store/import_csv
   - Retrieve LATEST_* (MM, PB, IL JP/M1/M2) -> /store/get_by_date
   - Load 20 history blobs (MM, PB, IL JP/M1/M2) -> /store/get_history
   - Run Phase 1 -> /run_json with phase:'phase1'
*/

(() => {
  // ---------- tiny helpers ----------
  const $ = (sel, root = document) => root.querySelector(sel);
  const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));
  const j = (o) => JSON.stringify(o, null, 2);
  const todayStr = () => {
    const d = new Date();
    const mm = String(d.getMonth() + 1).padStart(2, '0');
    const dd = String(d.getDate()).padStart(2, '0');
    const yy = d.getFullYear();
    return `${mm}/${dd}/${yy}`;
  };
  const toast = (msg, elOut) => {
    if (elOut) elOut.value = typeof msg === 'string' ? msg : j(msg);
    console.log(msg);
  };
  const asText = (res) => (res.ok ? res.text() : res.text().then(t => { throw new Error(t); }));
  const asJSON = (res) => (res.ok ? res.json() : res.text().then(t => { throw new Error(t); }));

  // ---------- DOM refs ----------
  // CSV upload
  const fileInput = $('#csvFile');
  const overwriteChk = $('#overwrite');
  const uploadBtn = $('#importBtn');
  const uploadOut = $('#uploadOut');

  // LATEST: MM / PB
  const mmDate = $('#mmDate');
  const mmPreview = $('#mmPreview');
  const mmBtn = $('#mmRetrieve');

  const pbDate = $('#pbDate');
  const pbPreview = $('#pbPreview');
  const pbBtn = $('#pbRetrieve');

  // LATEST: IL (JP / M1 / M2)
  const ilJPDate = $('#ilJPDate');
  const ilJPPreview = $('#ilJPPreview');
  const ilJPBtn = $('#ilJPRetrieve');

  const ilM1Date = $('#ilM1Date');
  const ilM1Preview = $('#ilM1Preview');
  const ilM1Btn = $('#ilM1Retrieve');

  const ilM2Date = $('#ilM2Date');
  const ilM2Preview = $('#ilM2Preview');
  const ilM2Btn = $('#ilM2Retrieve');

  // FEEDS
  const feedMM = $('#feedMM');
  const feedPB = $('#feedPB');
  const feedIL = $('#feedIL');

  // HISTORY: start dates + textareas + load buttons
  const histMMDate = $('#histMMDate');
  const histMMBlob = $('#histMMBlob');
  const histMMLoad = $('#histMMLoad');

  const histPBDate = $('#histPBDate');
  const histPBBlob = $('#histPBBlob');
  const histPBLoad = $('#histPBLoad');

  const histILJPDate = $('#histILJPDate');
  const histILJPBlob = $('#histILJPBlob');
  const histILJPLoad = $('#histILJPLoad');

  const histILM1Date = $('#histILM1Date');
  const histILM1Blob = $('#histILM1Blob');
  const histILM1Load = $('#histILM1Load');

  const histILM2Date = $('#histILM2Date');
  const histILM2Blob = $('#histILM2Blob');
  const histILM2Load = $('#histILM2Load');

  // RUN PHASE 1
  const runBtn = $('#runPhase1');
  const pathBox = $('#phase1Path');
  const resultRaw = $('#phase1Result'); // raw (debug) – still kept but we now render cards
  const cardsWrap = $('#phase1Cards');   // pretty layout container

  // ---------- CSV upload ----------
  uploadBtn?.addEventListener('click', async () => {
    if (!fileInput.files?.length) {
      toast('Pick a CSV first', uploadOut);
      return;
    }
    const fd = new FormData();
    fd.append('file', fileInput.files[0]);
    fd.append('overwrite', overwriteChk.checked ? 'true' : 'false');
    try {
      const res = await fetch('/store/import_csv', { method: 'POST', body: fd });
      const data = await asJSON(res);
      uploadOut.value = j(data);
    } catch (e) {
      uploadOut.value = String(e);
    }
  });

  // ---------- LATEST by date (helpers) ----------
  async function getLatest(game, date, tier = null) {
    const params = new URLSearchParams({ game, date });
    if (tier) params.set('tier', tier);
    const res = await fetch(`/store/get_by_date?${params.toString()}`);
    const js = await asJSON(res);
    if (!js.ok) throw new Error(js.detail || js.error || 'not ok');
    return js.row; // { mains:[...], bonus:int|null, iso:'MM/DD/YYYY' }
  }

  function fmtLatest(row, isIL = false) {
    // show as [[mains], bonus] with bonus=null for IL
    return `[${JSON.stringify(row.mains)}, ${isIL ? 'null' : (row.bonus ?? 'null')}]`;
    // example: [[10,14,34,40,43], 5] ; IL => [[2,7,25,30,44,49], null]
  }

  // MM
  mmBtn?.addEventListener('click', async () => {
    try {
      const row = await getLatest('MM', mmDate.value.trim());
      mmPreview.value = fmtLatest(row, false);
    } catch (e) {
      mmPreview.value = `Retrieve failed (MM): ${String(e).slice(0, 180)}`;
    }
  });

  // PB
  pbBtn?.addEventListener('click', async () => {
    try {
      const row = await getLatest('PB', pbDate.value.trim());
      pbPreview.value = fmtLatest(row, false);
    } catch (e) {
      pbPreview.value = `Retrieve failed (PB): ${String(e).slice(0, 180)}`;
    }
  });

  // IL tiers
  ilJPBtn?.addEventListener('click', async () => {
    try {
      const row = await getLatest('IL', ilJPDate.value.trim(), 'JP');
      ilJPPreview.value = fmtLatest(row, true);
    } catch (e) {
      ilJPPreview.value = `Retrieve failed (IL_JP): ${String(e).slice(0, 180)}`;
    }
  });

  ilM1Btn?.addEventListener('click', async () => {
    try {
      const row = await getLatest('IL', ilM1Date.value.trim(), 'M1');
      ilM1Preview.value = fmtLatest(row, true);
    } catch (e) {
      ilM1Preview.value = `Retrieve failed (IL_M1): ${String(e).slice(0, 180)}`;
    }
  });

  ilM2Btn?.addEventListener('click', async () => {
    try {
      const row = await getLatest('IL', ilM2Date.value.trim(), 'M2');
      ilM2Preview.value = fmtLatest(row, true);
    } catch (e) {
      ilM2Preview.value = `Retrieve failed (IL_M2): ${String(e).slice(0, 180)}`;
    }
  });

  // ---------- HISTORY (Load 20) ----------
  async function loadHistory(game, startDate, limit = 20, tier = null) {
    const p = new URLSearchParams({ game, from: startDate, limit: String(limit) });
    if (tier) p.set('tier', tier);
    const res = await fetch(`/store/get_history?${p.toString()}`);
    const js = await asJSON(res);
    if (!js.ok) throw new Error(js.detail || js.error || 'not ok');
    // js.rows = [{iso:'MM/DD/YY', mains:[...], bonus:int|null}, ...]
    // js.blob = text block already formatted (server did it)
    return js;
  }

  histMMLoad?.addEventListener('click', async () => {
    try {
      const js = await loadHistory('MM', histMMDate.value.trim(), 20);
      histMMBlob.value = js.blob || (js.rows || []).map(r =>
        `${r.iso}  ${r.mains.map(n => String(n).padStart(2, '0')).join('-')}  ${String(r.bonus ?? '').padStart(2, '0')}`
      ).join('\n');
    } catch (e) {
      histMMBlob.value = `Load failed (MM): ${String(e).slice(0, 200)}`;
    }
  });

  histPBLoad?.addEventListener('click', async () => {
    try {
      const js = await loadHistory('PB', histPBDate.value.trim(), 20);
      histPBBlob.value = js.blob || (js.rows || []).map(r =>
        `${r.iso}  ${r.mains.map(n => String(n).padStart(2, '0')).join('-')}  ${String(r.bonus ?? '').padStart(2, '0')}`
      ).join('\n');
    } catch (e) {
      histPBBlob.value = `Load failed (PB): ${String(e).slice(0, 200)}`;
    }
  });

  histILJPLoad?.addEventListener('click', async () => {
    try {
      const js = await loadHistory('IL', histILJPDate.value.trim(), 20, 'JP');
      histILJPBlob.value = js.blob || (js.rows || []).map(r =>
        `${r.iso}  ${r.mains.map(n => String(n).padStart(2, '0')).join('-')}`
      ).join('\n');
    } catch (e) {
      histILJPBlob.value = `Load failed (IL_JP): ${String(e).slice(0, 200)}`;
    }
  });

  histILM1Load?.addEventListener('click', async () => {
    try {
      const js = await loadHistory('IL', histILM1Date.value.trim(), 20, 'M1');
      histILM1Blob.value = js.blob || (js.rows || []).map(r =>
        `${r.iso}  ${r.mains.map(n => String(n).padStart(2, '0')).join('-')}`
      ).join('\n');
    } catch (e) {
      histILM1Blob.value = `Load failed (IL_M1): ${String(e).slice(0, 200)}`;
    }
  });

  histILM2Load?.addEventListener('click', async () => {
    try {
      const js = await loadHistory('IL', histILM2Date.value.trim(), 20, 'M2');
      histILM2Blob.value = js.blob || (js.rows || []).map(r =>
        `${r.iso}  ${r.mains.map(n => String(n).padStart(2, '0')).join('-')}`
      ).join('\n');
    } catch (e) {
      histILM2Blob.value = `Load failed (IL_M2): ${String(e).slice(0, 200)}`;
    }
  });

  // ---------- Phase 1 render cards ----------
  function chip(label, value) {
    return `<span class="chip">${label}: <b>${value}</b></span>`;
  }
  function renderBatch(list, isIL = false) {
    return `<pre class="batch">${list.map((line, i) => `${String(i + 1).padStart(2, '0')}. ${line}`).join('\n')}</pre>`;
  }
  function renderRowsIdx(rows) {
    const show = (k) => (rows[k] && rows[k].length ? rows[k].join(', ') : '—');
    return `
      <div class="rows">
        <div>3: ${show('3')}</div>
        <div>3+B: ${show('3+B')}</div>
        <div>4: ${show('4')}</div>
        <div>4+B: ${show('4+B')}</div>
        <div>5: ${show('5')}</div>
        <div>5+B: ${show('5+B')}</div>
      </div>`;
  }
  function renderILRowsIdx(rows) {
    const show = (k) => (rows[k] && rows[k].length ? rows[k].join(', ') : '—');
    return `
      <div class="rows">
        <div>3: ${show('3')}</div>
        <div>4: ${show('4')}</div>
        <div>5: ${show('5')}</div>
        <div>6: ${show('6')}</div>
      </div>`;
  }
  function renderGameCard(title, batch, stats, rows, extra = '') {
    const statsHtml = Object.entries(stats)
      .map(([k, v]) => chip(k, v))
      .join(' ');
    const rowsHtml = title.startsWith('IL ')
      ? renderILRowsIdx(rows)
      : renderRowsIdx(rows);

    return `
      <div class="game-card">
        <div class="game-title">${title}</div>
        <div class="grid-2">
          <div>${renderBatch(batch)}</div>
          <div>
            <div class="stats">${statsHtml}</div>
            <div class="rows-title">Row indices</div>
            ${rowsHtml}
            ${extra}
          </div>
        </div>
      </div>`;
  }

  function inflatePhase1Cards(payload) {
    const e = payload.echo || {};
    const html = [
      renderGameCard(
        'Mega Millions — 50 rows',
        e.BATCH_MM || [],
        (e.HITS_MM || {}).counts || { '3': 0, '3+B': 0, '4': 0, '4+B': 0, '5': 0, '5+B': 0 },
        (e.HITS_MM || {}).rows || {}
      ),
      renderGameCard(
        'Powerball — 50 rows',
        e.BATCH_PB || [],
        (e.HITS_PB || {}).counts || { '3': 0, '3+B': 0, '4': 0, '4+B': 0, '5': 0, '5+B': 0 },
        (e.HITS_PB || {}).rows || {}
      ),
      renderGameCard(
        'IL Lotto — 50 rows',
        e.BATCH_IL || [],
        (e.HITS_IL_M2 || e.HITS_IL_M1 || e.HITS_IL_JP || {}).counts || { '3': 0, '4': 0, '5': 0, '6': 0 },
        (e.HITS_IL_M2 || e.HITS_IL_M1 || e.HITS_IL_JP || {}).rows || {},
        `<div class="tiny-note">Counts shown are against your selected IL tier’s the 2nd newest draw.</div>`
      )
    ].join('');
    cardsWrap.innerHTML = html;
  }

  // ---------- Run Phase 1 ----------
  runBtn?.addEventListener('click', async () => {
    cardsWrap.innerHTML = '';
    resultRaw.value = '';

    const payload = {
      phase: 'phase1',
      run_id: (crypto.getRandomValues(new Uint32Array(1))[0] >>> 0).toString(36),

      FEED_MM: feedMM.value.trim(),
      FEED_PB: feedPB.value.trim(),
      FEED_IL: feedIL.value.trim(),

      HIST_MM_BLOB: histMMBlob.value.trim(),
      HIST_PB_BLOB: histPBBlob.value.trim(),
      HIST_IL_JP_BLOB: histILJPBlob.value.trim(),
      HIST_IL_M1_BLOB: histILM1Blob.value.trim(),
      HIST_IL_M2_BLOB: histILM2Blob.value.trim(),

      LATEST_MM: mmPreview.value.trim(),
      LATEST_PB: pbPreview.value.trim(),
      LATEST_IL_JP: ilJPPreview.value.trim(),
      LATEST_IL_M1: ilM1Preview.value.trim(),
      LATEST_IL_M2: ilM2Preview.value.trim()
    };

    try {
      const res = await fetch('/run_json', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      const js = await asJSON(res);
      pathBox.value = js.saved_path || '';
      resultRaw.value = j(js); // keep raw debug
      if (js.ok) inflatePhase1Cards(js);
    } catch (e) {
      resultRaw.value = String(e);
    }
  });

  // sensible defaults
  if (mmDate) mmDate.value = '09/16/2025';
  if (pbDate) pbDate.value = '09/17/2025';
  if (ilJPDate) ilJPDate.value = '09/18/2025';
  if (ilM1Date) ilM1Date.value = '09/18/2025';
  if (ilM2Date) ilM2Date.value = '09/18/2025';
  if (histMMDate) histMMDate.value = '09/12/2025';
  if (histPBDate) histPBDate.value = '09/13/2025';
  if (histILJPDate) histILJPDate.value = '09/15/2025';
  if (histILM1Date) histILM1Date.value = '09/15/2025';
  if (histILM2Date) histILM2Date.value = '09/15/2025';
})();
