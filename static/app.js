// ==========================
// small helpers
// ==========================
async function getJSON(url) {
  const r = await fetch(url, { credentials: "same-origin" });
  const ct = r.headers.get("content-type") || "";
  if (!r.ok) throw new Error(await r.text());
  if (ct.includes("application/json")) return await r.json();
  return await r.text();
}
async function postForm(url, formData) {
  const r = await fetch(url, { method: "POST", body: formData, credentials: "same-origin" });
  const ct = r.headers.get("content-type") || "";
  if (!r.ok) throw new Error(await r.text());
  if (ct.includes("application/json")) return await r.json();
  return await r.text();
}
function qs(id) { return document.getElementById(id); }
function setText(id, text) { const el = qs(id); if (el) el.textContent = text; }
function setVal(id, text) { const el = qs(id); if (el) el.value = text; }

function fmtNJ(mains, bonusOrNull) {
  const a = JSON.stringify(mains).replace(/\s+/g, " ");
  return `[${a}, ${bonusOrNull === null ? "null" : bonusOrNull}]`;
}

function blobFromRows_MM_PB(rows) {
  // rows is array of objects from /store/get_history -> {date, mains:[..], bonus:n}
  return rows.map(r => {
    const date = r.date.replaceAll("/", "-").replace(/^(\d{2})\/(\d{2})\/(\d{4})$/,
      (_, m, d, y) => `${m}-${d}-${String(y).slice(-2)}`);
    const mains = r.mains.map(n => String(n).padStart(2, "0")).join("-");
    const bb = String(r.bonus).padStart(2, "0");
    return `${date}  ${mains}  ${bb}`;
  }).join("\n");
}
function blobFromRows_IL(rows) {
  return rows.map(r => {
    const date = r.date.replaceAll("/", "-").replace(/^(\d{2})\/(\d{2})\/(\d{4})$/,
      (_, m, d, y) => `${m}-${d}-${String(y).slice(-2)}`);
    const mains = r.mains.map(n => String(n).padStart(2, "0")).join("-");
    return `${date}  ${mains}`;
  }).join("\n");
}

// create a light results panel if not present
function ensureResultsContainer() {
  let wrap = document.querySelector(".result-light");
  if (wrap) return wrap;

  wrap = document.createElement("div");
  wrap.className = "result-light";
  wrap.style.marginTop = "12px";
  wrap.innerHTML = `
    <div class="result-title">Phase 1 — Results</div>
    <div class="result-grid"></div>
  `;
  // try to insert after the Phase 1 section
  const phase1Btn = qs("runPhase1");
  if (phase1Btn && phase1Btn.closest(".card")) {
    phase1Btn.closest(".card").insertAdjacentElement("afterend", wrap);
  } else {
    document.body.appendChild(wrap);
  }
  return wrap;
}
function ensurePre(anchorId, label){
  const wrap = ensureResultsContainer();
  let grid = wrap.querySelector(".result-grid");
  if (!grid) {
    grid = document.createElement("div");
    grid.className = "result-grid";
    wrap.appendChild(grid);
  }
  let anchor = qs(anchorId);
  if (!anchor) {
    const c = document.createElement("div");
    c.className = "mt";
    c.innerHTML = `<div class="result-title">${label}</div><pre id="${anchorId}" class="result-pre">—</pre>`;
    grid.appendChild(c);
  }
}
function ensureHitsBox(blockId, title){
  if(qs(blockId + "_text")) return;
  const wrap = ensureResultsContainer();
  const el = document.createElement("div");
  el.className = "mt";
  el.innerHTML = `<div class="result-title">${title}</div><pre id="${blockId}_text" class="result-pre">—</pre>`;
  wrap.appendChild(el);
}
function renderList(id, arr) {
  const el = qs(id);
  if (!el) return;
  el.textContent = (arr && arr.length)
    ? arr.map((ln, i)=> `${String(i+1).padStart(2,'0')}. ${ln}`).join('\n')
    : '—';
}

// ==========================
// CSV upload
// ==========================
(function wireUpload(){
  const file = qs("csvFile");
  const b = qs("importBtn");
  const cb = qs("overwrite");
  if (!file || !b) return;

  b.addEventListener("click", async () => {
    try {
      if (!file.files || !file.files[0]) {
        alert("Choose a CSV file first.");
        return;
      }
      const fd = new FormData();
      fd.append("file", file.files[0]);
      fd.append("overwrite", cb && cb.checked ? "true" : "false");
      const out = await postForm("/store/import_csv", fd);
      alert(JSON.stringify(out, null, 2));
    } catch (e) {
      alert("Upload failed:\n" + (e && e.message ? e.message : e));
    }
  });
})();

// ==========================
// Retrieve NJ (2nd newest) by date → fill LATEST_*
// ==========================
async function retrieveLatest(gameKey, dateInputId, targetId, bonusNull=false){
  const dateEl = qs(dateInputId);
  if (!dateEl || !dateEl.value) { alert(`Pick date for ${gameKey}`); return; }
  const date = dateEl.value; // mm/dd/yyyy from <input type="date"> will be yyyy-mm-dd; normalize
  const mmddyyyy = date.includes("-")
    ? new Date(date).toLocaleDateString("en-US")
    : date;

  const res = await getJSON(`/store/get_by_date?game=${encodeURIComponent(gameKey)}&date=${encodeURIComponent(mmddyyyy)}`);
  if (!res || !res.ok) { alert(`Retrieve failed (${gameKey})`); return; }

  // /store/get_by_date returns { ok, row:{ game, date, tier, mains:[..], bonus } }
  const row = res.row;
  const mains = row.mains || [];
  const bonus = bonusNull ? null : (row.bonus ?? null);
  setVal(targetId, fmtNJ(mains, bonus));
}

(function wireRetrieve(){
  const mmb = qs("retrieveMM");
  if (mmb) mmb.addEventListener("click", () => retrieveLatest("MM", "mmDate", "LATEST_MM", false));

  const pbb = qs("retrievePB");
  if (pbb) pbb.addEventListener("click", () => retrieveLatest("PB", "pbDate", "LATEST_PB", false));

  const jpb = qs("retrieveILJP");
  if (jpb) jpb.addEventListener("click", () => retrieveLatest("IL_JP", "ilJPDate", "LATEST_IL_JP", true));

  const m1b = qs("retrieveILM1");
  if (m1b) m1b.addEventListener("click", () => retrieveLatest("IL_M1", "ilM1Date", "LATEST_IL_M1", true));

  const m2b = qs("retrieveILM2");
  if (m2b) m2b.addEventListener("click", () => retrieveLatest("IL_M2", "ilM2Date", "LATEST_IL_M2", true));
})();

// ==========================
// Load 20 history from 3rd-newest date → fill HIST_* blobs
// ==========================
async function loadHistory(gameKey, fromDateInputId, targetId, limit=20) {
  const dateEl = qs(fromDateInputId);
  if (!dateEl || !dateEl.value) { alert(`Pick 3rd-newest date for ${gameKey}`); return; }
  const mmddyyyy = dateEl.value.includes("-")
    ? new Date(dateEl.value).toLocaleDateString("en-US")
    : dateEl.value;

  const res = await getJSON(`/store/get_history?game=${encodeURIComponent(gameKey)}&from=${encodeURIComponent(mmddyyyy)}&limit=${limit}`);
  if (!res || !res.ok) { alert(`Load 20 failed (${gameKey})`); return; }

  // res.rows = [{date:'MM/DD/YYYY', mains:[..], bonus?}, ...]
  let blob = "";
  if (gameKey === "MM" || gameKey === "PB") {
    blob = blobFromRows_MM_PB(res.rows || []);
  } else {
    blob = blobFromRows_IL(res.rows || []);
  }
  setVal(targetId, blob);
}

(function wireLoad20(){
  const mm = qs("loadHistMM");
  if (mm) mm.addEventListener("click", () => loadHistory("MM", "mmHistDate", "HIST_MM_BLOB", 20));

  const pb = qs("loadHistPB");
  if (pb) pb.addEventListener("click", () => loadHistory("PB", "pbHistDate", "HIST_PB_BLOB", 20));

  const ijp = qs("loadHistILJP");
  if (ijp) ijp.addEventListener("click", () => loadHistory("IL_JP", "ilJPHistDate", "HIST_IL_JP_BLOB", 20));

  const im1 = qs("loadHistILM1");
  if (im1) im1.addEventListener("click", () => loadHistory("IL_M1", "ilM1HistDate", "HIST_IL_M1_BLOB", 20));

  const im2 = qs("loadHistILM2");
  if (im2) im2.addEventListener("click", () => loadHistory("IL_M2", "ilM2HistDate", "HIST_IL_M2_BLOB", 20));
})();

// ==========================
// Run Phase 1
// ==========================
(function wirePhase1(){
  const btn = qs("runPhase1");
  if (!btn) return;

  btn.addEventListener("click", async () => {
    try {
      // gather all inputs (strings exactly as backend expects)
      const payload = {
        phase: "phase1",
        LATEST_MM: (qs("LATEST_MM")?.value || "").trim(),
        LATEST_PB: (qs("LATEST_PB")?.value || "").trim(),
        LATEST_IL_JP: (qs("LATEST_IL_JP")?.value || "").trim(),
        LATEST_IL_M1: (qs("LATEST_IL_M1")?.value || "").trim(),
        LATEST_IL_M2: (qs("LATEST_IL_M2")?.value || "").trim(),

        FEED_MM: (qs("FEED_MM")?.value || "").trim(),
        FEED_PB: (qs("FEED_PB")?.value || "").trim(),
        FEED_IL: (qs("FEED_IL")?.value || "").trim(),

        HIST_MM_BLOB: (qs("HIST_MM_BLOB")?.value || "").trim(),
        HIST_PB_BLOB: (qs("HIST_PB_BLOB")?.value || "").trim(),
        HIST_IL_JP_BLOB: (qs("HIST_IL_JP_BLOB")?.value || "").trim(),
        HIST_IL_M1_BLOB: (qs("HIST_IL_M1_BLOB")?.value || "").trim(),
        HIST_IL_M2_BLOB: (qs("HIST_IL_M2_BLOB")?.value || "").trim(),
      };

      // quick validation — MM/PB require a bonus; IL tiers bonus must be null
      function looksNJ(s, needsBonus) {
        if (!s) return false;
        // examples: "[[1,2,3,4,5], 7]"  or  "[[1,2,3,4,5,6], null]"
        return needsBonus
          ? /^\s*\[\s*\[\s*\d+(?:\s*,\s*\d+){4}\s*\]\s*,\s*\d+\s*\]\s*$/.test(s)
          : /^\s*\[\s*\[\s*\d+(?:\s*,\s*\d+){5}\s*\]\s*,\s*null\s*\]\s*$/.test(s);
      }
      if (payload.LATEST_MM && !looksNJ(payload.LATEST_MM, true)) {
        alert("MM line must look like: [[10, 14, 34, 40, 43], 5]");
        return;
      }
      if (payload.LATEST_PB && !looksNJ(payload.LATEST_PB, true)) {
        alert("PB line must look like: [[7, 30, 50, 54, 62], 20]");
        return;
      }
      // IL tiers (no bonus)
      ["LATEST_IL_JP","LATEST_IL_M1","LATEST_IL_M2"].forEach(k=>{
        const v = payload[k];
        if (v && !/^\s*\[\s*\[\s*\d+(?:\s*,\s*\d+){5}\s*\]\s*,\s*null\s*\]\s*$/.test(v)) {
          throw new Error(`${k} must look like: [[1, 4, 5, 10, 18, 49], null]`);
        }
      });

      const fd = new FormData();
      Object.entries(payload).forEach(([k,v]) => fd.append(k, v));

      const res = await postForm("/run_json", fd);
      if (!res || !res.ok) throw new Error(JSON.stringify(res));

      // saved path if provided (Phase 1 can save state)
      if (res.saved_path) setVal("phase1Path", res.saved_path);

      // show JSON briefly in the legacy pre (if exists)
      if (qs("phase1Result")) {
        qs("phase1Result").textContent = JSON.stringify(res, null, 2);
      }

      // ===== render batches and hits =====
      const ech = res.echo || {};

      // 50-row batches
      ensurePre("p1_mm_batch_rows","MM — 50-row batch");
      ensurePre("p1_pb_batch_rows","PB — 50-row batch");
      ensurePre("p1_il_batch_rows","IL — 50-row batch");

      renderList("p1_mm_batch_rows", ech.BATCH_MM || []);
      renderList("p1_pb_batch_rows", ech.BATCH_PB || []);
      renderList("p1_il_batch_rows", ech.BATCH_IL || []);

      // hit tables
      function hitsMM_PB(blockId, hits, title){
        ensureHitsBox(blockId, title);
        const counts = (hits && hits.counts) || {};
        const rows = (hits && hits.rows) || {};
        const exact = (hits && hits.exact_rows) || [];
        const fmt = a => (a && a.length) ? a.join(", ") : "0";
        const text =
`3    : ${counts['3']||0}    rows: ${fmt(rows['3'])}
3 + B: ${counts['3+B']||0}  rows: ${fmt(rows['3+B'])}
4    : ${counts['4']||0}    rows: ${fmt(rows['4'])}
4 + B: ${counts['4+B']||0}  rows: ${fmt(rows['4+B'])}
5    : ${counts['5']||0}    rows: ${fmt(rows['5'])}
5 + B: ${counts['5+B']||0}  rows: ${fmt(rows['5+B'])}
Exact rows: ${fmt(exact)}`;
        setText(blockId + "_text", text);
      }
      hitsMM_PB("mm_hits", ech.HITS_MM, "MM — Hits in 50-row batch");
      hitsMM_PB("pb_hits", ech.HITS_PB, "PB — Hits in 50-row batch");

      function hitsIL(blockId, title, tierHits){
        ensureHitsBox(blockId, title);
        const counts = (tierHits && tierHits.counts) || {};
        const rows = (tierHits && tierHits.rows) || {};
        const fmt = a => (a && a.length) ? a.join(", ") : "0";
        const text =
`3-hit : ${counts['3']||0}  rows: ${fmt(rows['3'])}
4-hit : ${counts['4']||0}  rows: ${fmt(rows['4'])}
5-hit : ${counts['5']||0}  rows: ${fmt(rows['5'])}
6-hit : ${counts['6']||0}  rows: ${fmt(rows['6'])}`;
        setText(blockId + "_text", text);
      }
      hitsIL("il_hits_jp","IL — JP hits in 50-row batch", ech.HITS_IL_JP);
      hitsIL("il_hits_m1","IL — M1 hits in 50-row batch", ech.HITS_IL_M1);
      hitsIL("il_hits_m2","IL — M2 hits in 50-row batch", ech.HITS_IL_M2);

    } catch (e) {
      alert("Phase 1 failed:\n" + (e && e.message ? e.message : e));
    }
  });
})();
