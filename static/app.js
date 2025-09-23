/* global fetch */
const $ = (sel) => document.querySelector(sel);
const set = (id, v) => { const el = $(id); if (el) el.value = v; };
const text = (id, v) => { const el = $(id); if (el) el.textContent = v; };
const html = (id, v) => { const el = $(id); if (el) el.innerHTML = v; };
const byId = (id) => document.getElementById(id);

// ---------- Helpers ----------
function toMMDDYYYY(dateStr) {
  // input is yyyy-mm-dd from <input type="date">
  if (!dateStr) return "";
  const [y, m, d] = dateStr.split("-");
  return `${m}/${d}/${y}`;
}
function fmtLineMM(row) {
  // ["02-22-23-56-70  08", ...] already formatted by backend
  return row;
}
function fmtLinePB(row) { return row; }
function fmtLineIL(row) { return row; }

async function getJSON(url) {
  const r = await fetch(url);
  if (!r.ok) throw new Error(`${r.status} ${r.statusText}`);
  return r.json();
}
async function postJSON(url, body) {
  const r = await fetch(url, {
    method: "POST",
    headers: {"Content-Type":"application/json"},
    body: JSON.stringify(body)
  });
  if (!r.ok) {
    let txt = await r.text();
    throw new Error(txt || r.statusText);
  }
  return r.json();
}

// ---------- Upload ----------
byId("btnImport").addEventListener("click", async () => {
  const f = byId("csvFile").files[0];
  const overwrite = byId("overwrite").checked;
  const status = byId("importStatus");
  try {
    if (!f) { status.textContent = "Choose a file first."; return; }
    const fd = new FormData();
    fd.append("file", f, f.name);
    fd.append("overwrite", overwrite ? "true" : "false");
    const r = await fetch("/store/import_csv", { method:"POST", body: fd });
    const j = await r.json();
    status.textContent = JSON.stringify(j);
  } catch(e){
    status.textContent = `Upload failed: ${e}`;
  }
});

// ---------- Retrieve (2nd newest jackpots) ----------
byId("btnMM").addEventListener("click", async () => {
  const d = toMMDDYYYY(byId("mmDate").value);
  if (!d) return alert("Pick MM date");
  try {
    const j = await getJSON(`/store/get_by_date?game=MM&date=${encodeURIComponent(d)}`);
    // Server returns row = {mains:[...], bonus:n}
    set("#LATEST_MM", JSON.stringify([j.row.mains, j.row.bonus]));
  } catch(e){ alert(`Retrieve failed (MM): ${e}`); }
});

byId("btnPB").addEventListener("click", async () => {
  const d = toMMDDYYYY(byId("pbDate").value);
  if (!d) return alert("Pick PB date");
  try {
    const j = await getJSON(`/store/get_by_date?game=PB&date=${encodeURIComponent(d)}`);
    set("#LATEST_PB", JSON.stringify([j.row.mains, j.row.bonus]));
  } catch(e){ alert(`Retrieve failed (PB): ${e}`); }
});

byId("btnILJP").addEventListener("click", async () => {
  const d = toMMDDYYYY(byId("ilJPDate").value);
  if (!d) return alert("Pick IL JP date");
  try {
    const j = await getJSON(`/store/get_by_date?game=IL_JP&date=${encodeURIComponent(d)}`);
    set("#LATEST_IL_JP", JSON.stringify([j.row.mains, null]));
  } catch(e){ alert(`Retrieve failed (IL JP): ${e}`); }
});
byId("btnILM1").addEventListener("click", async () => {
  const d = toMMDDYYYY(byId("ilM1Date").value);
  if (!d) return alert("Pick IL M1 date");
  try {
    const j = await getJSON(`/store/get_by_date?game=IL_M1&date=${encodeURIComponent(d)}`);
    set("#LATEST_IL_M1", JSON.stringify([j.row.mains, null]));
  } catch(e){ alert(`Retrieve failed (IL M1): ${e}`); }
});
byId("btnILM2").addEventListener("click", async () => {
  const d = toMMDDYYYY(byId("ilM2Date").value);
  if (!d) return alert("Pick IL M2 date");
  try {
    const j = await getJSON(`/store/get_by_date?game=IL_M2&date=${encodeURIComponent(d)}`);
    set("#LATEST_IL_M2", JSON.stringify([j.row.mains, null]));
  } catch(e){ alert(`Retrieve failed (IL M2): ${e}`); }
});

// ---------- Load 20 history (3rd newest down) ----------
byId("btnHistMM").addEventListener("click", async () => {
  const d = toMMDDYYYY(byId("histMMDate").value);
  if (!d) return alert("Pick HIST MM start date (the 3rd newest)");
  try {
    const j = await getJSON(`/store/get_history?game=MM&from=${encodeURIComponent(d)}&limit=20`);
    set("#HIST_MM_BLOB", j.blob || "");
  } catch(e){ alert(`Load 20 failed (HIST MM): ${e}`); }
});
byId("btnHistPB").addEventListener("click", async () => {
  const d = toMMDDYYYY(byId("histPBDate").value);
  if (!d) return alert("Pick HIST PB start date (the 3rd newest)");
  try {
    const j = await getJSON(`/store/get_history?game=PB&from=${encodeURIComponent(d)}&limit=20`);
    set("#HIST_PB_BLOB", j.blob || "");
  } catch(e){ alert(`Load 20 failed (HIST PB): ${e}`); }
});
byId("btnHistILJP").addEventListener("click", async () => {
  const d = toMMDDYYYY(byId("histILJPDate").value);
  if (!d) return alert("Pick HIST IL JP start date (the 3rd newest)");
  try {
    const j = await getJSON(`/store/get_history?game=IL_JP&from=${encodeURIComponent(d)}&limit=20`);
    set("#HIST_IL_JP_BLOB", j.blob || "");
  } catch(e){ alert(`Load 20 failed (HIST IL JP): ${e}`); }
});
byId("btnHistILM1").addEventListener("click", async () => {
  const d = toMMDDYYYY(byId("histILM1Date").value);
  if (!d) return alert("Pick HIST IL M1 start date (the 3rd newest)");
  try {
    const j = await getJSON(`/store/get_history?game=IL_M1&from=${encodeURIComponent(d)}&limit=20`);
    set("#HIST_IL_M1_BLOB", j.blob || "");
  } catch(e){ alert(`Load 20 failed (HIST IL M1): ${e}`); }
});
byId("btnHistILM2").addEventListener("click", async () => {
  const d = toMMDDYYYY(byId("histILM2Date").value);
  if (!d) return alert("Pick HIST IL M2 start date (the 3rd newest)");
  try {
    const j = await getJSON(`/store/get_history?game=IL_M2&from=${encodeURIComponent(d)}&limit=20`);
    set("#HIST_IL_M2_BLOB", j.blob || "");
  } catch(e){ alert(`Load 20 failed (HIST IL M2): ${e}`); }
});

// ---------- Run Phase 1 ----------
byId("runPhase1").addEventListener("click", async () => {
  const payload = {
    phase: "phase1",
    LATEST_MM: byId("LATEST_MM").value.trim(),
    LATEST_PB: byId("LATEST_PB").value.trim(),
    LATEST_IL_JP: byId("LATEST_IL_JP").value.trim(),
    LATEST_IL_M1: byId("LATEST_IL_M1").value.trim(),
    LATEST_IL_M2: byId("LATEST_IL_M2").value.trim(),
    FEED_MM: byId("FEED_MM").value.trim(),
    FEED_PB: byId("FEED_PB").value.trim(),
    FEED_IL: byId("FEED_IL").value.trim(),
    HIST_MM_BLOB: byId("HIST_MM_BLOB").value.trim(),
    HIST_PB_BLOB: byId("HIST_PB_BLOB").value.trim(),
    HIST_IL_JP_BLOB: byId("HIST_IL_JP_BLOB").value.trim(),
    HIST_IL_M1_BLOB: byId("HIST_IL_M1_BLOB").value.trim(),
    HIST_IL_M2_BLOB: byId("HIST_IL_M2_BLOB").value.trim(),
  };

  try {
    const res = await postJSON("/run_json", payload);
    if (!res.ok) {
      byId("phase1Msg").textContent = "Phase 1 error";
      return;
    }
    if (res.saved_path) byId("phase1Path").value = res.saved_path;
    byId("phase1Msg").textContent = "Done";

    const E = (res.echo || {});
    renderBatch("#mmBatch", E.BATCH_MM || [], fmtLineMM);
    renderBatch("#pbBatch", E.BATCH_PB || [], fmtLinePB);
    renderBatch("#ilBatch", E.BATCH_IL || [], fmtLineIL);

    renderHitsMM("#mmStats", "#mmRows", "#mmCounts", E.HITS_MM);
    renderHitsMM("#pbStats", "#pbRows", "#pbCounts", E.HITS_PB);
    renderHitsIL("#ilStats", "#ilRows", "#ilCounts", {
      JP: E.HITS_IL_JP, M1: E.HITS_IL_M1, M2: E.HITS_IL_M2
    });

  } catch(e){
    byId("phase1Msg").textContent = `Error: ${e}`;
  }
});

// ---------- renderers ----------
function renderBatch(listSel, lines, fmt) {
  const el = $(listSel);
  el.innerHTML = "";
  lines.forEach((row) => {
    const li = document.createElement("li");
    li.textContent = fmt(row);
    el.appendChild(li);
  });
}

function renderHitsMM(statsSel, rowsSel, countsSel, H) {
  if (!H) { html(statsSel, ""); text(rowsSel,""); text(countsSel,""); return; }
  const chips = [];
  const order = ["3","3+B","4","4+B","5","5+B"];
  order.forEach(k=>{
    const c = (H.counts && H.counts[k]) || 0;
    chips.push(`<span class="chip">${k}: ${c}</span>`);
  });
  html(statsSel, chips.join(" "));
  text(countsSel, "");
  const lines = [];
  order.forEach(k=>{
    const arr = (H.rows && H.rows[k]) || [];
    lines.push(`${k}: ${arr.join(", ") || "—"}`);
  });
  lines.push("");
  if (Array.isArray(H.exact_rows) && H.exact_rows.length){
    lines.push("Exact rows (mains + bonus):");
    H.exact_rows.forEach(r => lines.push(JSON.stringify(r)));
  }
  $(rowsSel).textContent = lines.join("\n");
}

function renderHitsIL(statsSel, rowsSel, countsSel, obj) {
  // Show combined chips for JP/M1/M2
  const chips = [];
  ["JP","M1","M2"].forEach(tag=>{
    const H = obj[tag] || {};
    const c3 = (H.counts && H.counts["3"])||0;
    const c4 = (H.counts && H.counts["4"])||0;
    const c5 = (H.counts && H.counts["5"])||0;
    const c6 = (H.counts && H.counts["6"])||0;
    chips.push(`<span class="chip">${tag} 3:${c3}</span>`);
    chips.push(`<span class="chip">${tag} 4:${c4}</span>`);
    chips.push(`<span class="chip">${tag} 5:${c5}</span>`);
    chips.push(`<span class="chip">${tag} 6:${c6}</span>`);
  });
  html(statsSel, chips.join(" "));

  const lines = [];
  ["JP","M1","M2"].forEach(tag=>{
    const H = obj[tag] || {};
    lines.push(`${tag} rows:`);
    ["3","4","5","6"].forEach(k=>{
      const arr = (H.rows && H.rows[k]) || [];
      lines.push(`  ${k}: ${arr.join(", ") || "—"}`);
    });
    lines.push("");
  });
  $(rowsSel).textContent = lines.join("\n");
  text(countsSel, "");
}
