/* static/app.js — COMPLETE */

//////////////////////////
// tiny DOM helpers
//////////////////////////
const $ = (id) => document.getElementById(id);

function setLog(msg, isErr = false) {
  const out = $("runLog");
  if (!out) return;
  out.className = isErr ? "log err" : "log ok";
  out.textContent = msg;
}

async function fetchJSON(url, opts = {}) {
  const res = await fetch(url, opts);
  if (!res.ok) {
    let detail = await res.text();
    try { detail = JSON.parse(detail); } catch {}
    const msg = typeof detail === "string" ? detail : (detail.detail || detail.error || res.statusText);
    throw new Error(msg);
  }
  return res.json();
}

//////////////////////////
// formatting helpers
//////////////////////////

// stringify into EXACT shape Phase-1 expects:
// - for MM/PB -> "[[n1,n2,n3,n4,n5], bonus]"
// - for IL    -> "[[n1,n2,n3,n4,n5,n6], null]"
function formatLatest(mains, bonus) {
  const body = `[${(mains || []).map(Number).join(",")}]`;
  const b = (bonus == null || Number.isNaN(Number(bonus))) ? "null" : String(Number(bonus));
  return `[${body}, ${b}]`;
}

// tolerant extractor for many server shapes
// accepts:
//   { mains:[…], bonus:5 }
//   { n1..n5, bonus }       (PB/MM)
//   { n1..n6 }              (IL tiers, no bonus)
function extractMainsBonus(row, { forceNoBonus = false } = {}) {
  let mains = [];

  if (row && Array.isArray(row.mains) && row.mains.length) {
    mains = row.mains.map(Number);
  } else {
    const nums = [];
    for (let i = 1; i <= 6; i++) {
      const k = "n" + i;
      if (row && row[k] != null && row[k] !== "") nums.push(Number(row[k]));
    }
    if (nums.length) mains = nums;
  }

  let bonus = null;
  if (!forceNoBonus) {
    if (row && row.bonus != null) bonus = Number(row.bonus);
    else if (row && row.mb != null) bonus = Number(row.mb);
    else if (row && row.pb != null) bonus = Number(row.pb);
  }

  return { mains, bonus };
}

//////////////////////////
// store API wrappers
//////////////////////////

// /store/get_by_date?game=MM|PB|IL&date=MM/DD/YYYY[&tier=JP|M1|M2]
async function retrieveByDate(game, date, tier = "") {
  const params = new URLSearchParams({ game, date });
  if (tier) params.set("tier", tier);
  const j = await fetchJSON(`/store/get_by_date?${params.toString()}`);
  if (!j.ok && (j.error || j.detail)) throw new Error(j.detail || j.error);
  return j.row || j; // server may return {ok:true,row:{...}} or just row
}

// /store/get_history?game=MM|PB|IL_JP|IL_M1|IL_M2&from=MM/DD/YYYY&limit=20
async function loadHistory(gameKey, fromDate, limit = 20) {
  const params = new URLSearchParams({ game: gameKey, from: fromDate, limit: String(limit) });
  const j = await fetchJSON(`/store/get_history?${params.toString()}`);
  if (j.ok === false) throw new Error(j.detail || j.error || "history failed");
  return j;
}

function renderHistoryBlob(rows, kind) {
  // kind: "MM" => show "mm-dd-yy  n1-n2-n3-n4-n5 MB"
  // kind: "PB" => show "mm-dd-yy  n1-n2-n3-n4-n5 01"
  // kind: "IL" tiers => "mm-dd-yy  A-B-C-D-E-F"
  const lines = [];
  for (const r of rows || []) {
    const d = r.draw_date_mmddyy || r.draw_date || r.date || "";
    const nums = [];
    for (let i = 1; i <= 6; i++) {
      const k = "n" + i;
      if (r[k] != null && r[k] !== "") nums.push(String(r[k]).padStart(2, "0"));
    }
    if (kind === "MM" || kind === "PB") {
      // only first 5 shown + bonus right aligned
      const five = nums.slice(0, 5).join("-");
      const b = (r.bonus ?? r.mb ?? r.pb ?? "");
      const bb = String(b).padStart(2, "0");
      lines.push(`${d}  ${five}  ${bb}`);
    } else {
      // IL tiers: 6 mains
      lines.push(`${d}  ${nums.join("-")}`);
    }
  }
  return lines.join("\n");
}

//////////////////////////
// wire up: RETRIEVE buttons
//////////////////////////

async function hookRetrieves() {
  $("btnRetrieveMM")?.addEventListener("click", async () => {
    try {
      const d = $("mmDate").value.trim();
      if (!d) return setLog("Pick a Mega Millions date.", true);
      const row = await retrieveByDate("MM", d);
      const { mains, bonus } = extractMainsBonus(row);
      $("mmPreview").value = formatLatest(mains, bonus);
      setLog("MM retrieved.");
    } catch (e) { setLog(`Retrieve failed (MM): ${e.message}`, true); }
  });

  $("btnRetrievePB")?.addEventListener("click", async () => {
    try {
      const d = $("pbDate").value.trim();
      if (!d) return setLog("Pick a Powerball date.", true);
      const row = await retrieveByDate("PB", d);
      const { mains, bonus } = extractMainsBonus(row);
      $("pbPreview").value = formatLatest(mains, bonus);
      setLog("PB retrieved.");
    } catch (e) { setLog(`Retrieve failed (PB): ${e.message}`, true); }
  });

  $("btnRetrieveILJP")?.addEventListener("click", async () => {
    try {
      const d = $("ilJPDate").value.trim();
      if (!d) return setLog("Pick IL Jackpot date.", true);
      const row = await retrieveByDate("IL", d, "JP");
      const { mains } = extractMainsBonus(row, { forceNoBonus: true });
      $("ilJPPreview").value = formatLatest(mains, null);
      setLog("IL JP retrieved.");
    } catch (e) { setLog(`Retrieve failed (IL_JP): ${e.message}`, true); }
  });

  $("btnRetrieveILM1")?.addEventListener("click", async () => {
    try {
      const d = $("ilM1Date").value.trim();
      if (!d) return setLog("Pick IL Million 1 date.", true);
      const row = await retrieveByDate("IL", d, "M1");
      const { mains } = extractMainsBonus(row, { forceNoBonus: true });
      $("ilM1Preview").value = formatLatest(mains, null);
      setLog("IL M1 retrieved.");
    } catch (e) { setLog(`Retrieve failed (IL_M1): ${e.message}`, true); }
  });

  $("btnRetrieveILM2")?.addEventListener("click", async () => {
    try {
      const d = $("ilM2Date").value.trim();
      if (!d) return setLog("Pick IL Million 2 date.", true);
      const row = await retrieveByDate("IL", d, "M2");
      const { mains } = extractMainsBonus(row, { forceNoBonus: true });
      $("ilM2Preview").value = formatLatest(mains, null);
      setLog("IL M2 retrieved.");
    } catch (e) { setLog(`Retrieve failed (IL_M2): ${e.message}`, true); }
  });
}

//////////////////////////
// wire up: Load 20 (history)
//////////////////////////

async function hookLoad20() {
  $("btnLoad20MM")?.addEventListener("click", async () => {
    try {
      const from = $("mmHistDate").value.trim();
      if (!from) return setLog("Pick the 3rd-newest MM date above the blob.", true);
      const j = await loadHistory("MM", from, 20);
      $("mmHistBlob").value = renderHistoryBlob(j.rows || [], "MM");
    } catch (e) { setLog(`Load failed (MM): ${e.message}`, true); }
  });

  $("btnLoad20PB")?.addEventListener("click", async () => {
    try {
      const from = $("pbHistDate").value.trim();
      if (!from) return setLog("Pick the 3rd-newest PB date above the blob.", true);
      const j = await loadHistory("PB", from, 20);
      $("pbHistBlob").value = renderHistoryBlob(j.rows || [], "PB");
    } catch (e) { setLog(`Load failed (PB): ${e.message}`, true); }
  });

  $("btnLoad20ILJP")?.addEventListener("click", async () => {
    try {
      const from = $("ilJPHistDate").value.trim();
      const j = await loadHistory("IL_JP", from, 20);
      $("ilJPHistBlob").value = renderHistoryBlob(j.rows || [], "IL");
    } catch (e) { setLog(`Load failed (IL_JP): ${e.message}`, true); }
  });

  $("btnLoad20ILM1")?.addEventListener("click", async () => {
    try {
      const from = $("ilM1HistDate").value.trim();
      const j = await loadHistory("IL_M1", from, 20);
      $("ilM1HistBlob").value = renderHistoryBlob(j.rows || [], "IL");
    } catch (e) { setLog(`Load failed (IL_M1): ${e.message}`, true); }
  });

  $("btnLoad20ILM2")?.addEventListener("click", async () => {
    try {
      const from = $("ilM2HistDate").value.trim();
      const j = await loadHistory("IL_M2", from, 20);
      $("ilM2HistBlob").value = renderHistoryBlob(j.rows || [], "IL");
    } catch (e) { setLog(`Load failed (IL_M2): ${e.message}`, true); }
  });
}

//////////////////////////
// Run Phase 1
//////////////////////////

function mustHave(id, label) {
  const v = $(id)?.value?.trim() || "";
  if (!v || !v.startsWith("[[")) {
    throw new Error(`${label} is empty or not in '[[..], b]' format`);
  }
  return v;
}

async function hookRunPhase1() {
  $("btnRunPhase1")?.addEventListener("click", async () => {
    try {
      // Validate the five LATEST_* previews as strings exactly as backend wants
      const LATEST_MM = mustHave("mmPreview", "LATEST_MM");
      const LATEST_PB = mustHave("pbPreview", "LATEST_PB");
      const LATEST_IL_JP = mustHave("ilJPPreview", "LATEST_IL_JP");
      const LATEST_IL_M1 = mustHave("ilM1Preview", "LATEST_IL_M1");
      const LATEST_IL_M2 = mustHave("ilM2Preview", "LATEST_IL_M2");

      // Feeds (free text)
      const FEED_MM = $("feedMM")?.value || "";
      const FEED_PB = $("feedPB")?.value || "";
      const FEED_IL = $("feedIL")?.value || "";

      const payload = {
        phase: "phase1",
        LATEST_MM,
        LATEST_PB,
        LATEST_IL_JP,
        LATEST_IL_M1,
        LATEST_IL_M2,
        FEED_MM,
        FEED_PB,
        FEED_IL
      };

      setLog("Running Phase 1...");
      const res = await fetchJSON("/run_json", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });

      if (res.ok === false) throw new Error(res.detail || res.error || "Phase 1 failed");
      // If server returns a saved path, show it
      if (res.saved_path) {
        const p = $("savedPhase1Path");
        if (p) p.value = res.saved_path;
      }
      setLog("Phase 1 complete.");
    } catch (e) {
      setLog(`Phase 1 failed: ${e.message}`, true);
    }
  });
}

//////////////////////////
// boot
//////////////////////////
document.addEventListener("DOMContentLoaded", () => {
  hookRetrieves();
  hookLoad20();
  hookRunPhase1();
  setLog("Ready.");
});
