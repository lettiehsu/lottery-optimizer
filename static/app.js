/* static/app.js — Phase 1/2/3 UI + history save/blob + copy helpers */

const RUN1_URL = "/run_json";
const RUN2_URL = "/run_phase2";
const CONFIRM_URL = "/confirm_json";
const RECENT_URL = "/recent";

function $(id) { return document.getElementById(id); }
function el(tag, html) { const e = document.createElement(tag); e.innerHTML = html; return e; }
function clear(node) { if (node) node.innerHTML = ""; }

async function copyText(text) {
  try { await navigator.clipboard.writeText(text); toast("Copied!"); }
  catch { window.prompt("Press Ctrl+C to copy:", text); }
}
function toast(msg) {
  const t = document.createElement("div");
  t.textContent = msg;
  t.style.cssText = "position:fixed;bottom:16px;left:50%;transform:translateX(-50%);"+
    "background:#111;color:#fff;padding:8px 12px;border-radius:8px;opacity:.95;z-index:9999";
  document.body.appendChild(t);
  setTimeout(()=>t.remove(), 1200);
}

let _lastBuyLists = { MM: [], PB: [], IL: [] };
let _lastP1Path = "";
let _lastP2Path = "";

/* ---------- render helpers ---------- */
function renderBands(targetId, bands) {
  const host = $(targetId);
  if (!host || !bands) return;
  const items = [
    { k: "IL", title: "IL middle-50% band" },
    { k: "MM", title: "MM middle-50% band" },
    { k: "PB", title: "PB middle-50% band" },
  ];
  clear(host);
  for (const it of items) {
    const b = bands[it.k] || ["–","–"];
    const lo = Array.isArray(b) ? b[0] : "–";
    const hi = Array.isArray(b) ? b[1] : "–";
    host.appendChild(el("div",
      `<div class="card" style="margin-bottom:8px;">
        <div class="card-title">${it.title}</div>
        <div class="muted">Sum range</div>
        <div class="mono">${lo} – ${hi}</div>
      </div>`
    ));
  }
}

function fillExact(tbodyId, types, src) {
  const tbody = $(tbodyId);
  clear(tbody);
  const defs = JSON.parse(tbody.dataset.types || "[]");
  for (const t of defs) {
    const pos = (src && src[t]) ? src[t] : [];
    const txt = (pos && pos.length) ? pos.join(", ") : "—";
    tbody.appendChild(el("tr", `<td>${t}</td><td>${txt}</td>`));
  }
}

function fillAgg(tbodyId, types, src) {
  const tbody = $(tbodyId);
  clear(tbody);
  for (const t of types) {
    const pos = (src && src[t]) ? src[t] : [];
    const count = Array.isArray(pos) ? pos.length : 0;
    const freq = {};
    (pos || []).forEach(p => { freq[p] = (freq[p] || 0) + 1; });
    const top = Object.entries(freq)
      .sort((a,b) => b[1]-a[1] || (+a[0])-(+b[0]))
      .slice(0, 8)
      .map(([r,c]) => `${r}(${c})`)
      .join(", ");
    tbody.appendChild(el("tr", `<td>${t}</td><td>${count}</td><td>${top || "—"}</td>`));
  }
}

function fillBuy(tbodyId, rows, hasBonus=false) {
  const tbody = $(tbodyId);
  clear(tbody);
  (rows || []).forEach((t, i) => {
    const mains = (t.mains || []).join(", ");
    const bonus = t.bonus ?? "";
    tbody.appendChild(el("tr", `<td>${i+1}</td><td>${mains}</td>${hasBonus?`<td>${bonus}</td>`:""}`));
  });
}

async function getRecent(intoId) {
  const box = $(intoId);
  const res = await fetch(RECENT_URL);
  const data = await res.json().catch(()=>({}));
  const files = Array.isArray(data.files) ? data.files : (Array.isArray(data) ? data : []);
  box.textContent = files.length ? files.join("\n") : "No recent files.";
}

/* ---------- Phase 1 ---------- */
async function runPhase1() {
  const payload = {
    LATEST_MM: $("LATEST_MM").value.trim(),
    LATEST_PB: $("LATEST_PB").value.trim(),
    LATEST_IL_JP: $("LATEST_IL_JP").value.trim(),
    LATEST_IL_M1: $("LATEST_IL_M1").value.trim(),
    LATEST_IL_M2: $("LATEST_IL_M2").value.trim(),
    FEED_MM: $("FEED_MM").value.trim(),
    FEED_PB: $("FEED_PB").value.trim(),
    FEED_IL: $("FEED_IL").value.trim(),
    HIST_MM_BLOB: $("HIST_MM_BLOB").value.trim(),
    HIST_PB_BLOB: $("HIST_PB_BLOB").value.trim(),
    HIST_IL_BLOB: $("HIST_IL_BLOB").value.trim()
  };

  const res = await fetch(RUN1_URL, {
    method:"POST",
    headers:{"Content-Type":"application/json"},
    body: JSON.stringify(payload)
  });

  let data;
  try { data = await res.json(); } catch(e) { alert("Server returned non-JSON."); return; }
  if (!res.ok || !data.ok) { alert("Phase 1 failed: " + (data?.detail || res.status)); return; }

  renderBands("bands", data.bands);

  const e = data.eval_vs_NJ || {};
  fillExact("mm-exact", ["3","3B","4","4B","5","5B"], e.MM || {});
  fillExact("pb-exact", ["3","3B","4","4B","5","5B"], e.PB || {});
  const il = e.IL || {};
  fillExact("iljp-exact", ["3","4","5","6"], il.JP || {});
  fillExact("ilm1-exact", ["3","4","5","6"], il.M1 || {});
  fillExact("ilm2-exact", ["3","4","5","6"], il.M2 || {});

  _lastP1Path = data.saved_path || "";
  $("p1-saved").textContent = "Saved Phase-1 state: " + (_lastP1Path || "(none)");
  $("phase1_path").value = _lastP1Path;  // prefill Phase 2
}

/* ---------- Phase 2 ---------- */
async function runPhase2() {
  const p1path = $("phase1_path").value.trim();
  if (!p1path) { alert("Please paste the saved Phase-1 path first."); return; }

  const res = await fetch(RUN2_URL, {
    method:"POST",
    headers:{"Content-Type":"application/json"},
    body: JSON.stringify({ saved_path: p1path })
  });

  let data;
  try { data = await res.json(); } catch(e) { alert("Server returned non-JSON."); return; }
  if (!res.ok || !data.ok) { alert("Phase 2 failed: " + (data?.detail || res.status)); return; }

  renderBands("p2-bands", data.bands);

  const bl = data.buy_lists || {};
  fillBuy("mm-buy", bl.MM || [], true);
  fillBuy("pb-buy", bl.PB || [], true);
  fillBuy("il-buy", bl.IL || [], false);

  const agg = data.agg_hits || {};
  fillAgg("mm-agg", ["3","3B","4","4B","5","5B"], agg.MM || {});
  fillAgg("pb-agg", ["3","3B","4","4B","5","5B"], agg.PB || {});
  const il = agg.IL || {};
  fillAgg("iljp-agg", ["3","4","5","6"], il.JP || {});
  fillAgg("ilm1-agg", ["3","4","5","6"], il.M1 || {});
  fillAgg("ilm2-agg", ["3","4","5","6"], il.M2 || {});

  _lastBuyLists = { MM: bl.MM || [], PB: bl.PB || [], IL: bl.IL || [] };

  _lastP2Path = data.saved_path || "";
  $("p2-saved").textContent = "Saved Phase-2 state: " + (_lastP2Path || "(none)");
  $("phase2_path_confirm").value = _lastP2Path;  // prefill Phase 3
}

/* ---------- Phase 3 ---------- */
async function confirmPhase3() {
  const path = $("phase2_path_confirm").value.trim();
  if (!path) { alert("Please paste the saved Phase-2 path."); return; }

  let nwj = $("nwj_json").value.trim();
  const payload = { saved_path: path };
  if (nwj) {
    try { payload.NWJ = JSON.parse(nwj); }
    catch(e) { alert('NWJ must be valid JSON (use null, not None).'); return; }
  }

  const res = await fetch(CONFIRM_URL, {
    method:"POST",
    headers:{"Content-Type":"application/json"},
    body: JSON.stringify(payload)
  });
  let data;
  try { data = await res.json(); } catch(e) { alert("Server returned non-JSON."); return; }
  if (!res.ok || !data.ok) { alert("Confirm failed: " + (data?.detail || res.status)); return; }

  renderConfirmBoxes(data.confirm_hits || {});
}

function renderConfirmBoxes(hitObj) {
  const fillTable = (tbodyId) => {
    const tbody = $(tbodyId);
    const defs = JSON.parse(tbody.dataset.types || "[]");
    const src = (() => {
      if (tbodyId.startsWith("mm-")) return hitObj.MM || {};
      if (tbodyId.startsWith("pb-")) return hitObj.PB || {};
      if (tbodyId.startsWith("iljp-")) return (hitObj.IL && hitObj.IL.JP) || {};
      if (tbodyId.startsWith("ilm1-")) return (hitObj.IL && hitObj.IL.M1) || {};
      if (tbodyId.startsWith("ilm2-")) return (hitObj.IL && hitObj.IL.M2) || {};
      return {};
    })();
    clear(tbody);
    for (const t of defs) {
      const pos = (src && src[t]) ? src[t] : [];
      const txt = (Array.isArray(pos) && pos.length) ? pos.join(", ") : "—";
      tbody.appendChild(el("tr", `<td>${t}</td><td>${txt}</td>`));
    }
  };

  ["mm-rows","pb-rows","iljp-rows","ilm1-rows","ilm2-rows"].forEach(fillTable);
}

/* ---------- Copy helpers ---------- */
function formatBuyListText(tag, rows, hasBonus=false) {
  const lines = [`${tag} buy list:`];
  (rows || []).forEach((t, i) => {
    const mains = (t.mains || []).join(", ");
    const bonus = hasBonus && t.bonus != null ? `  [bonus ${t.bonus}]` : "";
    lines.push(`${String(i+1).padStart(2," ")}. ${mains}${bonus}`);
  });
  return lines.join("\n");
}

/* ---------- History: save current NJ → DB ---------- */
async function saveNJtoHistory() {
  const payload = {};

  const mm = $("LATEST_MM").value.trim();
  const pb = $("LATEST_PB").value.trim();
  const iljp = $("LATEST_IL_JP").value.trim();
  const ilm1 = $("LATEST_IL_M1").value.trim();
  const ilm2 = $("LATEST_IL_M2").value.trim();

  function parsePair(txt) {
    // Accepts "[a,b,c,d,e], x" (spaces OK)
    if (!txt) return null;
    try {
      const m = txt.split("]");
      if (m.length < 2) return null;
      const mains = JSON.parse(m[0] + "]");
      const bonus = JSON.parse(m[1].replace(",", "").trim());
      return [mains, bonus];
    } catch { return null; }
  }
  function parseSixOnly(txt) {
    if (!txt) return null;
    try {
      // Allow either [1,2,3,4,5,6] or with spaces
      const arr = JSON.parse(txt.replace(/'/g,'"'));
      if (Array.isArray(arr) && arr.length === 6) return [arr, null];
    } catch {}
    return null;
  }

  const pMM = parsePair(mm);     if (pMM) payload.LATEST_MM = pMM;
  const pPB = parsePair(pb);     if (pPB) payload.LATEST_PB = pPB;
  const pJP = parseSixOnly(iljp); if (pJP) payload.LATEST_IL_JP = pJP;
  const pM1 = parseSixOnly(ilm1); if (pM1) payload.LATEST_IL_M1 = pM1;
  const pM2 = parseSixOnly(ilm2); if (pM2) payload.LATEST_IL_M2 = pM2;

  if (!Object.keys(payload).length) {
    alert("Nothing to save. Fill at least one LATEST_* box first.");
    return;
  }

  const res = await fetch("/hist_add", {
    method:"POST",
    headers:{"Content-Type":"application/json"},
    body: JSON.stringify(payload)
  });
  const data = await res.json().catch(()=>({}));
  if (!res.ok || !data.ok) {
    alert("Save failed: " + (data.detail || res.status));
    return;
  }
  toast("Saved to history: " + (data.added || []).join(", "));
}

/* ---------- History: show BLOB ---------- */
async function showBlob(game) {
  const res = await fetch("/hist_blob?game=" + encodeURIComponent(game));
  const data = await res.json().catch(()=>({}));
  if (!res.ok || !data.ok) { alert("Unable to fetch BLOB for " + game); return; }
  const box = $("blobView");
  box.style.display = "block";
  box.textContent = (data.blob || "(empty)");
}

/* ---------- events ---------- */
$("btnRun1")?.addEventListener("click", runPhase1);
$("btnRun2")?.addEventListener("click", runPhase2);
$("btnConfirm")?.addEventListener("click", confirmPhase3);
$("btnRecent")?.addEventListener("click", () => getRecent("recentList"));

$("btnCopyP1")?.addEventListener("click", () => {
  if (!_lastP1Path) return alert("No saved Phase-1 path yet.");
  copyText(_lastP1Path);
});
$("btnCopyP2")?.addEventListener("click", () => {
  if (!_lastP2Path) return alert("No saved Phase-2 path yet.");
  copyText(_lastP2Path);
});

$("copyMM")?.addEventListener("click", () => {
  if (!_lastBuyLists.MM.length) return alert("Run Phase 2 first.");
  copyText(formatBuyListText("MM", _lastBuyLists.MM, true));
});
$("copyPB")?.addEventListener("click", () => {
  if (!_lastBuyLists.PB.length) return alert("Run Phase 2 first.");
  copyText(formatBuyListText("PB", _lastBuyLists.PB, true));
});
$("copyIL")?.addEventListener("click", () => {
  if (!_lastBuyLists.IL.length) return alert("Run Phase 2 first.");
  copyText(formatBuyListText("IL", _lastBuyLists.IL, false));
});

/* history buttons */
$("btnSaveToHist")?.addEventListener("click", saveNJtoHistory);
$("btnShowMMBlob")?.addEventListener("click", () => showBlob("MM"));
$("btnShowPBBlob")?.addEventListener("click", () => showBlob("PB"));
$("btnShowILBlob")?.addEventListener("click", () => showBlob("IL"));
