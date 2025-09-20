/* static/app.js — clean outputs with 50-row tables */

async function postJSON(url, data) {
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  const txt = await res.text();
  try { return JSON.parse(txt); } catch { return { ok:false, raw: txt }; }
}

function el(tag, cls, html) {
  const n = document.createElement(tag);
  if (cls) n.className = cls;
  if (html !== undefined) n.innerHTML = html;
  return n;
}
function copyBtn(text) {
  const b = el("button", "copy", "Copy");
  b.onclick = () => { navigator.clipboard.writeText(text); b.textContent = "Copied"; setTimeout(()=>b.textContent="Copy",1200); };
  return b;
}
function pill(x){ return `<span class="pill">${x}</span>`; }

function renderBands(bands) {
  const wrap = el("div","cards");
  for (const [game,[lo,hi]] of Object.entries(bands||{})) {
    const c = el("div","card");
    c.append(el("h3","",`${game} middle-50% band`));
    c.append(el("div","kv", `<span>Sum range</span><span class="mono">${lo} – ${hi}</span>`));
    wrap.append(c);
  }
  return wrap;
}
function renderHitPositions(title, hitsObj, withBonus=false) {
  const c = el("div","card");
  c.append(el("h3","",title));
  const cols = withBonus ? ["3","3B","4","4B","5","5B"] : ["3","4","5","6"];
  const tbl = el("table","tbl");
  const thead = el("thead"); thead.innerHTML = `<tr><th>Type</th>${cols.map(k=>`<th>${k}</th>`).join("")}</tr>`;
  const tbody = el("tbody");
  const row = el("tr");
  row.innerHTML = `<td class="muted">Positions</td>` + cols.map(k=>{
    const arr = hitsObj?.[k] || [];
    return `<td>${arr.length ? arr.map(pill).join(" ") : `<span class="muted">—</span>`}</td>`;
  }).join("");
  tbody.append(row); tbl.append(thead, tbody); c.append(tbl); return c;
}
function renderBuyList(title, list) {
  const c = el("div","card"); c.append(el("h3","",title));
  const tbl = el("table","tbl");
  tbl.innerHTML = `<thead><tr><th>#</th><th>Mains</th><th>Bonus</th></tr></thead><tbody></tbody>`;
  const tb = tbl.querySelector("tbody");
  (list||[]).forEach((t,i)=>{
    const tr = el("tr");
    tr.innerHTML = `<td>${i+1}</td><td class="mono">${(t.mains||[]).join(", ")}</td><td class="mono">${t.bonus==null?"—":t.bonus}</td>`;
    tb.append(tr);
  });
  c.append(tbl); return c;
}

/* ----- NEW: detailed batch tables ----- */
function renderBatchTableMM(title, rows) {
  const c = el("div","card"); c.append(el("h3","",title));
  const tbl = el("table","tbl");
  tbl.innerHTML = `<thead><tr><th>#</th><th>Mains</th><th>Bonus</th><th>Sum</th><th>Hit</th></tr></thead><tbody></tbody>`;
  const tb = tbl.querySelector("tbody");
  (rows||[]).forEach(r=>{
    const tr = el("tr");
    tr.innerHTML = `<td>${r.row}</td><td class="mono">${(r.mains||[]).join(", ")}</td><td class="mono">${r.bonus==null?"—":r.bonus}</td><td class="mono">${r.sum}</td><td>${r.hit?`<span class="pill">${r.hit}</span>`:'<span class="muted">—</span>'}</td>`;
    tb.append(tr);
  });
  c.append(tbl); return c;
}
function renderBatchTableIL(title, rows) {
  const c = el("div","card"); c.append(el("h3","",title));
  const tbl = el("table","tbl");
  tbl.innerHTML = `<thead><tr><th>#</th><th>Mains</th><th>Sum</th><th>Hit</th></tr></thead><tbody></tbody>`;
  const tb = tbl.querySelector("tbody");
  (rows||[]).forEach(r=>{
    const tr = el("tr");
    tr.innerHTML = `<td>${r.row}</td><td class="mono">${(r.mains||[]).join(", ")}</td><td class="mono">${r.sum}</td><td>${r.hit?`<span class="pill">${r.hit}</span>`:'<span class="muted">—</span>'}</td>`;
    tb.append(tr);
  });
  c.append(tbl); return c;
}

function renderRaw(jsonObj, title="Raw JSON (for debugging)") {
  const card = el("div","card");
  card.append(el("h3","",title));
  card.append(el("pre","raw", JSON.stringify(jsonObj, null, 2)));
  return card;
}

/* ---------- Phase 1 ---------- */
async function runPhase1() {
  const payload = {
    LATEST_MM: document.querySelector("#p1_mm").value.trim(),
    LATEST_PB: document.querySelector("#p1_pb").value.trim(),
    LATEST_IL_JP: document.querySelector("#p1_il_jp").value.trim(),
    LATEST_IL_M1: document.querySelector("#p1_il_m1").value.trim(),
    LATEST_IL_M2: document.querySelector("#p1_il_m2").value.trim(),
    FEED_MM: document.querySelector("#p1_feed_mm").value.trim(),
    FEED_PB: document.querySelector("#p1_feed_pb").value.trim(),
    FEED_IL: document.querySelector("#p1_feed_il").value.trim(),
    HIST_MM_BLOB: document.querySelector("#p1_hist_mm").value.trim(),
    HIST_PB_BLOB: document.querySelector("#p1_hist_pb").value.trim(),
    HIST_IL_BLOB: document.querySelector("#p1_hist_il").value.trim(),
    phase: "phase1",
  };
  const btn = document.querySelector("#btn_p1");
  btn.disabled = true; btn.textContent = "Running…";
  const out = document.querySelector("#out_p1"); out.innerHTML = "";

  const data = await postJSON("/run_json", payload);

  if (!data || data.error) {
    out.append(el("div","danger", `Error: ${data?.error || "unknown"}`));
    if (data?.detail) out.append(el("pre","raw", data.detail));
    btn.disabled = false; btn.textContent = "Run Phase 1";
    return;
  }

  out.append(renderBands(data.bands));
  const hits = data.eval_vs_NJ || {};
  const cards = el("div","cards");
  cards.append(renderHitPositions("MM hits vs NJ", hits.MM, true));
  cards.append(renderHitPositions("PB hits vs NJ", hits.PB, true));
  const il = hits.IL || {};
  cards.append(renderHitPositions("IL Jackpot (6) vs NJ", il.JP, false));
  cards.append(renderHitPositions("IL Million 1 (6) vs NJ", il.M1, false));
  cards.append(renderHitPositions("IL Million 2 (6) vs NJ", il.M2, false));
  out.append(cards);

  /* detailed batches */
  if (data.batches) {
    const B = data.batches;
    const wrap = el("div","cards");
    if (Array.isArray(B.MM)) wrap.append(renderBatchTableMM("MM — 50-row batch", B.MM));
    if (Array.isArray(B.PB)) wrap.append(renderBatchTableMM("PB — 50-row batch", B.PB));
    if (B.IL) {
      wrap.append(renderBatchTableIL("IL JP — 50-row batch", B.IL.JP || []));
      wrap.append(renderBatchTableIL("IL M1 — 50-row batch", B.IL.M1 || []));
      wrap.append(renderBatchTableIL("IL M2 — 50-row batch", B.IL.M2 || []));
    }
    out.append(wrap);
  }

  if (data.saved_path) {
    const p = el("div","okline", `Saved Phase-1 state: <span class="mono">${data.saved_path}</span>`);
    p.appendChild(copyBtn(data.saved_path));
    out.append(p);
  }
  out.append(renderRaw(data));
  btn.disabled = false; btn.textContent = "Run Phase 1";
}

/* ---------- Phase 2 ---------- */
async function runPhase2() {
  const saved = document.querySelector("#p2_saved").value.trim();
  if (!saved) { alert("Paste the Phase-1 saved_path first."); return; }
  const payload = { phase: "phase2", saved_path: saved };
  const btn = document.querySelector("#btn_p2");
  btn.disabled = true; btn.textContent = "Running…";
  const out = document.querySelector("#out_p2"); out.innerHTML = "";
  const data = await postJSON("/run_json", payload);

  if (!data || data.error) {
    out.append(el("div","danger", `Error: ${data?.error || "unknown"}`));
    if (data?.detail) out.append(el("pre","raw", data.detail));
    btn.disabled = false; btn.textContent = "Run Phase 2 (100×)";
    return;
  }

  out.append(renderBands(data.bands));
  const buys = data.buy_lists || {};
  const cards = el("div","cards");
  cards.append(renderBuyList("MM — 10 tickets", buys.MM));
  cards.append(renderBuyList("PB — 10 tickets", buys.PB));
  cards.append(renderBuyList("IL — 15 tickets", buys.IL));
  out.append(cards);

  if (data.saved_path) {
    const p = el("div","okline", `Saved Phase-2 state: <span class="mono">${data.saved_path}</span>`);
    p.appendChild(copyBtn(data.saved_path));
    out.append(p);
  }
  out.append(renderRaw(data));
  btn.disabled = false; btn.textContent = "Run Phase 2 (100×)";
}

/* ---------- Phase 3 ---------- */
async function runPhase3() {
  const saved = document.querySelector("#p3_saved").value.trim();
  if (!saved) { alert("Paste the Phase-2 saved_path first."); return; }
  let nwj; try { nwj = JSON.parse(document.querySelector("#p3_nwj").value || "{}"); } catch { nwj = null; }
  const payload = { saved_path: saved }; if (nwj && Object.keys(nwj).length) payload.NWJ = nwj;

  const btn = document.querySelector("#btn_p3");
  btn.disabled = true; btn.textContent = "Running…";
  const out = document.querySelector("#out_p3"); out.innerHTML = "";
  const data = await postJSON("/confirm_json", payload);

  if (!data || data.error) {
    out.append(el("div","danger", `Error: ${data?.error || "unknown"}`));
    if (data?.detail) out.append(el("pre","raw", data.detail));
    btn.disabled = false; btn.textContent = "Confirm vs NWJ";
    return;
  }

  const hits = data.confirm_hits || {};
  const cards = el("div","cards");
  cards.append(renderHitPositions("MM — buy list vs NWJ", hits.MM, true));
  cards.append(renderHitPositions("PB — buy list vs NWJ", hits.PB, true));
  const il = hits.IL || {};
  cards.append(renderHitPositions("IL JP — buy list vs NWJ", il.JP, false));
  cards.append(renderHitPositions("IL M1 — buy list vs NWJ", il.M1, false));
  cards.append(renderHitPositions("IL M2 — buy list vs NWJ", il.M2, false));
  out.append(cards);

  out.append(renderRaw(data));
  btn.disabled = false; btn.textContent = "Confirm vs NWJ";
}

/* ---------- Recent ---------- */
async function getRecent() {
  const out = document.querySelector("#out_recent"); out.innerHTML = "";
  const res = await fetch("/recent"); const data = await res.json();
  const files = (data.files || []).slice(0, 20);
  const list = el("div","cards");
  if (!files.length) list.append(el("div","card","No saved files yet."));
  files.forEach(f => {
    const c = el("div","card");
    c.append(el("div","mono", f));
    c.append(copyBtn(f));
    list.append(c);
  });
  out.append(list);
}

document.querySelector("#btn_p1").addEventListener("click", runPhase1);
document.querySelector("#btn_p2").addEventListener("click", runPhase2);
document.querySelector("#btn_p3").addEventListener("click", runPhase3);
document.querySelector("#btn_recent").addEventListener("click", getRecent);
