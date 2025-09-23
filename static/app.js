// Minimal wiring for Phase 1 retrieve/load 20

async function getJSON(url) {
  const r = await fetch(url, { headers: { "Accept": "application/json" } });
  if (!r.ok) throw new Error(`${r.status} ${r.statusText} — ${url}`);
  return await r.json();
}

// ----- helpers to set field text -----
function setVal(id, text) {
  const el = document.getElementById(id);
  if (el) el.value = text;
}
function getVal(id) {
  const el = document.getElementById(id);
  return el ? el.value.trim() : "";
}

// ----- Phase 1: Retrieve newest jackpots by date -----
async function retrieveByDate(gameCode, dateId, outputId) {
  const date = getVal(dateId);
  if (!date) { alert(`Pick a date for ${gameCode}`); return; }
  try {
    const res = await getJSON(`/store/get_by_date?game=${encodeURIComponent(gameCode)}&date=${encodeURIComponent(date)}`);
    if (!res.ok) throw new Error(res.error || "not ok");
    const row = res.row; // {game,date,tier,mains:[...],bonus:null|number}
    const out = (row.bonus == null)
      ? JSON.stringify([row.mains, null])
      : JSON.stringify([row.mains, row.bonus]);
    setVal(outputId, out);
  } catch (e) {
    alert(`Retrieve failed (${gameCode}): ${e.message}`);
  }
}

// ----- Phase 1: Load 20 history (blob) starting from the chosen date -----
// game must be one of: "MM","PB","IL_JP","IL_M1","IL_M2"
async function load20(game, dateId, blobId) {
  const start = getVal(dateId);
  if (!start) { alert(`Pick start date for ${game}`); return; }
  try {
    const res = await getJSON(`/store/get_history?game=${encodeURIComponent(game)}&from=${encodeURIComponent(start)}&limit=20`);
    if (!res.ok) throw new Error(res.error || "not ok");
    setVal(blobId, res.blob || "");
  } catch (e) {
    alert(`Load 20 failed (${game}): ${e.message}`);
  }
}

// ====== WIRE BUTTONS ON PAGE LOAD ======
window.addEventListener("DOMContentLoaded", () => {
  // Newest jackpots (2nd newest) retrieves:
  document.getElementById("btnRetrieveMM")?.addEventListener("click", () => {
    retrieveByDate("MM", "dateMM", "LATEST_MM");
  });
  document.getElementById("btnRetrievePB")?.addEventListener("click", () => {
    retrieveByDate("PB", "datePB", "LATEST_PB");
  });
  document.getElementById("btnRetrieveILJP")?.addEventListener("click", () => {
    retrieveByDate("IL_JP", "dateILJP", "LATEST_IL_JP");
  });
  document.getElementById("btnRetrieveILM1")?.addEventListener("click", () => {
    retrieveByDate("IL_M1", "dateILM1", "LATEST_IL_M1");
  });
  document.getElementById("btnRetrieveILM2")?.addEventListener("click", () => {
    retrieveByDate("IL_M2", "dateILM2", "LATEST_IL_M2");
  });

  // History “Load 20” (3rd newest date for each):
  document.getElementById("btnLoad20MM")?.addEventListener("click", () => {
    load20("MM", "histDateMM", "HIST_MM_BLOB");
  });
  document.getElementById("btnLoad20PB")?.addEventListener("click", () => {
    load20("PB", "histDatePB", "HIST_PB_BLOB");
  });
  document.getElementById("btnLoad20ILJP")?.addEventListener("click", () => {
    load20("IL_JP", "histDateILJP", "HIST_IL_JP_BLOB");
  });
  document.getElementById("btnLoad20ILM1")?.addEventListener("click", () => {
    load20("IL_M1", "histDateILM1", "HIST_IL_M1_BLOB");
  });
  document.getElementById("btnLoad20ILM2")?.addEventListener("click", () => {
    load20("IL_M2", "histDateILM2", "HIST_IL_M2_BLOB");
  });
});
