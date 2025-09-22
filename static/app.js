/* ------------------------------
   Lottery Optimizer – Phase 1 UI
   (safe date handling: never use new Date())
--------------------------------*/

(() => {
  // ----- helpers -----
  const $ = (sel) => document.querySelector(sel);
  const setVal = (sel, v) => { const n = $(sel); if (n) n.value = v; };
  const getStr = (sel) => {
    const n = $(sel);
    return (n && typeof n.value === 'string') ? n.value.trim() : '';
  };
  const msg = (t, kind = 'info') => {
    const m = $('#phase1_msg');
    if (!m) return;
    m.textContent = t || '';
    m.className = kind; // style with .info, .warn, .err if you like
  };
  const fetchJSON = async (url) => {
    const r = await fetch(url);
    if (!r.ok) {
      const text = await r.text();
      throw new Error(`${r.status} ${r.statusText}: ${text}`);
    }
    return r.json();
  };

  // ----- element IDs (adjust here if yours differ) -----
  const el = {
    // date inputs
    mmDate:     '#mm_date',
    pbDate:     '#pb_date',
    ilJPDate:   '#il_jp_date',
    ilM1Date:   '#il_m1_date',
    ilM2Date:   '#il_m2_date',

    // preview outputs
    mmPreview:  '#mm_preview',
    pbPreview:  '#pb_preview',
    ilJPPrev:   '#il_jp_preview',
    ilM1Prev:   '#il_m1_preview',
    ilM2Prev:   '#il_m2_preview',

    // retrieve buttons
    mmBtn:      '#btn_mm_retrieve',
    pbBtn:      '#btn_pb_retrieve',
    ilJPBtn:    '#btn_il_jp_retrieve',
    ilM1Btn:    '#btn_il_m1_retrieve',
    ilM2Btn:    '#btn_il_m2_retrieve',

    // history blocks
    mmHistDate: '#hist_mm_date',
    pbHistDate: '#hist_pb_date',
    ilJPHDate:  '#hist_il_jp_date',
    ilM1HDate:  '#hist_il_m1_date',
    ilM2HDate:  '#hist_il_m2_date',

    mmHistLoad: '#btn_hist_mm_load',
    pbHistLoad: '#btn_hist_pb_load',
    ilJPHLoad:  '#btn_hist_il_jp_load',
    ilM1HLoad:  '#btn_hist_il_m1_load',
    ilM2HLoad:  '#btn_hist_il_m2_load',

    mmHistBlob: '#hist_mm_blob',
    pbHistBlob: '#hist_pb_blob',
    ilJPHBlob:  '#hist_il_jp_blob',
    ilM1HBlob:  '#hist_il_m1_blob',
    ilM2HBlob:  '#hist_il_m2_blob',
  };

  // ----- wire up “Retrieve” for MM/PB -----
  const retrieveMM = async () => {
    try {
      msg('');
      const date = getStr(el.mmDate);         // <-- raw string (MM/DD/YYYY)
      if (!date) throw new Error('Pick Mega Millions date.');
      const q = `/store/get_by_date?game=MM&date=${encodeURIComponent(date)}`;
      const j = await fetchJSON(q);
      // store returns: { ok:true, row:{ mains:[...], bonus:number|null, ... } }
      const mains = j.row.mains || [];
      const bonus = (j.row.bonus === null || j.row.bonus === undefined) ? 'null' : j.row.bonus;
      setVal(el.mmPreview, `[${mains.join(',')}], ${bonus}`);
    } catch (e) { msg(`Retrieve failed (MM): ${e.message}`, 'err'); }
  };

  const retrievePB = async () => {
    try {
      msg('');
      const date = getStr(el.pbDate);
      if (!date) throw new Error('Pick Powerball date.');
      const q = `/store/get_by_date?game=PB&date=${encodeURIComponent(date)}`;
      const j = await fetchJSON(q);
      const mains = j.row.mains || [];
      const bonus = (j.row.bonus === null || j.row.bonus === undefined) ? 'null' : j.row.bonus;
      setVal(el.pbPreview, `[${mains.join(',')}], ${bonus}`);
    } catch (e) { msg(`Retrieve failed (PB): ${e.message}`, 'err'); }
  };

  // ----- wire up “Retrieve” for IL tiers -----
  const retrieveIL = (tier, dateSel, outSel, label) => async () => {
    try {
      msg('');
      const date = getStr(dateSel);
      if (!date) throw new Error(`Pick ${label} date.`);
      const q = `/store/get_by_date?game=IL&tier=${encodeURIComponent(tier)}&date=${encodeURIComponent(date)}`;
      const j = await fetchJSON(q);
      const mains = j.row.mains || [];
      // IL tiers have no bonus → use null
      setVal(outSel, `[${mains.join(',')}], null`);
    } catch (e) { msg(`Retrieve failed (${label}): ${e.message}`, 'err'); }
  };

  // ----- history “Load 20” for blobs -----
  const loadHist = (game, dateSel, outSel, extraParams = '') => async () => {
    try {
      msg('');
      const from = getStr(dateSel);
      if (!from) throw new Error('Pick a start date (3rd newest).');
      const q = `/store/get_history?game=${encodeURIComponent(game)}&from=${encodeURIComponent(from)}&limit=20${extraParams}`;
      const j = await fetchJSON(q);
      // Expect j.blob to be the formatted multi-line text
      setVal(outSel, j.blob || '');
    } catch (e) { msg(`Load 20 failed (${game}): ${e.message}`, 'err'); }
  };

  // ----- attach listeners -----
  const on = (sel, fn) => { const n = $(sel); if (n) n.addEventListener('click', fn); };

  on(el.mmBtn, retrieveMM);
  on(el.pbBtn, retrievePB);
  on(el.ilJPBtn, retrieveIL('JP', el.ilJPDate, el.ilJPPrev, 'IL JP'));
  on(el.ilM1Btn, retrieveIL('M1', el.ilM1Date, el.ilM1Prev, 'IL M1'));
  on(el.ilM2Btn, retrieveIL('M2', el.ilM2Date, el.ilM2Prev, 'IL M2'));

  on(el.mmHistLoad, loadHist('MM', el.mmHistDate, el.mmHistBlob));
  on(el.pbHistLoad, loadHist('PB', el.pbHistDate, el.pbHistBlob));
  on(el.ilJPHLoad,  loadHist('IL_JP', el.ilJPHDate, el.ilJPHBlob));
  on(el.ilM1HLoad,  loadHist('IL_M1', el.ilM1HDate, el.ilM1HBlob));
  on(el.ilM2HLoad,  loadHist('IL_M2', el.ilM2HDate, el.ilM2HBlob));

  // ready
  msg('');
})();
