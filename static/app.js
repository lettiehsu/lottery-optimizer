async function jsonFetch(url, opts={}) {
  const r = await fetch(url, opts);
  let data;
  try { data = await r.json(); } catch { data = {ok:false, error:'bad_json'}; }
  if (!r.ok || data.ok === false) throw data;
  return data;
}

function qs(id){ return document.getElementById(id); }

// ---------- CSV import ----------
qs('csvForm').addEventListener('submit', async (e)=>{
  e.preventDefault();
  const fd = new FormData();
  const f = qs('csvFile').files[0];
  if (!f) { qs('csvResult').textContent = 'Pick a CSV first.'; return; }
  fd.append('file', f);
  fd.append('overwrite', qs('overwrite').checked ? 'true' : 'false');
  try{
    const res = await jsonFetch('/store/import_csv', { method:'POST', body:fd });
    qs('csvResult').textContent = JSON.stringify(res, null, 2);
  }catch(err){
    qs('csvResult').textContent = JSON.stringify(err, null, 2);
  }
});

// ---------- Retrieve helpers ----------
async function retrieve(game, dateInput, previewInput) {
  const date = qs(dateInput).value.trim();
  if (!date) return;
  try{
    const r = await jsonFetch(`/store/get_by_date?game=${encodeURIComponent(game)}&date=${encodeURIComponent(date)}`);
    // r.row -> { mains:[...], bonus: n or null }
    const mains = r.row.mains || r.row.numbers || [];
    const bonus = ('bonus' in r.row) ? r.row.bonus : null;
    qs(previewInput).value = JSON.stringify([mains, bonus]);
  }catch(err){
    alert(`Retrieve failed (${game}): ${err.detail||err.error||'error'}`);
  }
}

qs('mmFetch').onclick = ()=>retrieve('MM','mmDate','mmPreview');
qs('pbFetch').onclick = ()=>retrieve('PB','pbDate','pbPreview');
qs('ilJPFetch').onclick= ()=>retrieve('IL_JP','ilJPDate','ilJPPreview');
qs('ilM1Fetch').onclick= ()=>retrieve('IL_M1','ilM1Date','ilM1Preview');
qs('ilM2Fetch').onclick= ()=>retrieve('IL_M2','ilM2Date','ilM2Preview');

// ---------- Load 20 history ----------
async function load20(game, dateInput, textareaId) {
  const from = qs(dateInput).value.trim();
  if (!from) return;
  try{
    const r = await jsonFetch(`/store/get_history?game=${encodeURIComponent(game)}&from=${encodeURIComponent(from)}&limit=20`);
    // Expect r.blob (string) or r.rows
    if (r.blob) qs(textareaId).value = r.blob;
    else qs(textareaId).value = (r.rows || []).map(x=>x.line || '').join("\n");
  }catch(err){
    alert(`Load failed (${game}): ${err.detail||err.error||'error'}`);
  }
}
qs('histMMBtn').onclick = ()=>load20('MM','histMMDate','histMM');
qs('histPBBtn').onclick = ()=>load20('PB','histPBDate','histPB');
qs('histILJPBtn').onclick = ()=>load20('IL_JP','histILJPDate','histILJP');
qs('histILM1Btn').onclick = ()=>load20('IL_M1','histILM1Date','histILM1');
qs('histILM2Btn').onclick = ()=>load20('IL_M2','histILM2Date','histILM2');

// ---------- Run Phase 1 ----------
qs('runPhase1').onclick = async ()=>{
  // Build payload for core.handle_run Phase 1
  const payload = {
    phase: 1,
    LATEST_MM: qs('mmPreview').value.trim(),
    LATEST_PB: qs('pbPreview').value.trim(),
    LATEST_IL_JP: qs('ilJPPreview').value.trim(),
    LATEST_IL_M1: qs('ilM1Preview').value.trim(),
    LATEST_IL_M2: qs('ilM2Preview').value.trim(),
    FEED_MM: qs('feedMM').value,
    FEED_PB: qs('feedPB').value,
    FEED_IL: qs('feedIL').value,
    HIST_MM_BLOB: qs('histMM').value,
    HIST_PB_BLOB: qs('histPB').value,
    HIST_IL_BLOB_JP: qs('histILJP').value,
    HIST_IL_BLOB_M1: qs('histILM1').value,
    HIST_IL_BLOB_M2: qs('histILM2').value
  };
  try{
    const r = await jsonFetch('/run_json', {
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body: JSON.stringify(payload)
    });

    // Save path if provided
    if (r.saved_path) qs('savedPhase1Path').value = r.saved_path;

    // Prefer direct results; otherwise try loading the saved JSON
    let data = r;
    if (!r.results && r.saved_path) {
      try {
        const opened = await jsonFetch(`/open_json?path=${encodeURIComponent(r.saved_path)}`);
        data = opened.data || r;
      } catch(e) { /* ignore; will show raw r */ }
    }
    renderPhase1Results(data);
  }catch(err){
    alert(`Phase 1 failed: ${err.detail||err.error||'error'}`);
  }
};

// ---------- Render results ----------
function renderTable(el, rows){
  if (!rows || !rows.length){ el.innerHTML = '<tr><td class="muted">—</td></tr>'; return; }
  const th = `<tr><th>Type</th><th>Count</th><th>Top positions</th></tr>`;
  const tr = rows.map(r=>{
    const tp = (r.top_positions || r.positions || []).join(', ');
    return `<tr><td>${r.type||''}</td><td>${r.count||0}</td><td>${tp||'—'}</td></tr>`;
  }).join('');
  el.innerHTML = th + tr;
}

function renderPhase1Results(data){
  // Try to be forgiving to whatever keys your core returns.
  // We’ll render:
  // - summary (json)
  // - exact tables: mmExact/pbExact/ilExact  (supports either “exact_mm”, “mm_exact”, etc.)
  // - bands: bandsIL/bandsMM/bandsPB (string blobs)
  const resEl = document.getElementById('phase1Results');
  const sumEl = document.getElementById('p1Summary');
  resEl.style.display = 'block';
  sumEl.textContent = JSON.stringify(data, null, 2);

  const mmRows = data.exact_mm || data.mm_exact || data.MM_exact || data.mm || [];
  const pbRows = data.exact_pb || data.pb_exact || data.PB_exact || data.pb || [];
  const ilRows = data.exact_il || data.il_exact || data.IL_exact || data.il || [];

  renderTable(document.getElementById('mmExact'), mmRows);
  renderTable(document.getElementById('pbExact'), pbRows);
  renderTable(document.getElementById('ilExact'), ilRows);

  document.getElementById('bandsIL').textContent = data.bands_il || data.IL_bands || data.bandsIL || '';
  document.getElementById('bandsMM').textContent = data.bands_mm || data.MM_bands || data.bandsMM || '';
  document.getElementById('bandsPB').textContent = data.bands_pb || data.PB_bands || data.bandsPB || '';
}
