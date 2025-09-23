// --- helpers ---
async function getJSON(url) {
  const r = await fetch(url);
  if (!r.ok) throw new Error(`${r.status} ${r.statusText}`);
  return r.json();
}
// format the <input type="date"> value (YYYY-MM-DD) to MM/DD/YYYY *without* using Date()
function asMDY(dateInputValue) {
  if (!dateInputValue) return "";
  const [y, m, d] = dateInputValue.split("-");
  return `${m}/${d}/${y}`;
}
function fmtLatest(row, isIL=false) {
  if (!row) return "";
  const mains = row.mains.map(n => n.toString().padStart(2,"0")).join(", ");
  const bonus = row.bonus == null ? "null" : row.bonus;
  return isIL ? `[[  ${mains.replace(/, /g,",  ") }], null]`
              : `[[  ${mains.replace(/, /g,",  ") }], ${bonus}]`;
}
function qs(id){ return document.getElementById(id); }

// --- on ready ---
window.addEventListener("DOMContentLoaded", () => {
  // Upload
  const form = qs("csvForm");
  form?.addEventListener("submit", async (e) => {
    e.preventDefault();
    const out = qs("csvResult");
    try {
      const fd = new FormData(form);
      const r = await fetch(form.action, { method:"POST", body: fd });
      const j = await r.json();
      out.textContent = JSON.stringify(j, null, 2);
    } catch(err) {
      out.textContent = `Upload failed: ${err}`;
    }
  });

  // Retrieve latest by date (MM)
  qs("mmRetrieve")?.addEventListener("click", async () => {
    const dstr = asMDY(qs("mmDate").value);
    if (!dstr) return;
    try {
      const j = await getJSON(`/store/get_by_date?game=MM&date=${encodeURIComponent(dstr)}`);
      qs("mmLatest").textContent = fmtLatest(j.row, false);
    } catch(e) {
      qs("mmLatest").textContent = `Retrieve failed (MM): ${e}`;
    }
  });

  // PB
  qs("pbRetrieve")?.addEventListener("click", async () => {
    const dstr = asMDY(qs("pbDate").value);
    if (!dstr) return;
    try {
      const j = await getJSON(`/store/get_by_date?game=PB&date=${encodeURIComponent(dstr)}`);
      qs("pbLatest").textContent = fmtLatest(j.row, false);
    } catch(e) {
      qs("pbLatest").textContent = `Retrieve failed (PB): ${e}`;
    }
  });

  // IL JP/M1/M2 (now pass tier)
  async function getIL(outId, dateInputId, tier){
    const dstr = asMDY(qs(dateInputId).value);
    if (!dstr) return;
    try {
      const j = await getJSON(`/store/get_by_date?game=IL&date=${encodeURIComponent(dstr)}&tier=${encodeURIComponent(tier)}`);
      qs(outId).textContent = fmtLatest(j.row, true);
    } catch(e) {
      qs(outId).textContent = `Retrieve failed (IL ${tier}): ${e}`;
    }
  }
  qs("ilJpRetrieve")?.addEventListener("click", () => getIL("ilJpLatest","ilJpDate","JP"));
  qs("ilM1Retrieve")?.addEventListener("click", () => getIL("ilM1Latest","ilM1Date","M1"));
  qs("ilM2Retrieve")?.addEventListener("click", () => getIL("ilM2Latest","ilM2Date","M2"));

  // Load 20 history blobs (now pass tier for IL)
  async function loadHist(game, dateInputId, blobId, tier=""){
    const dstr = asMDY(qs(dateInputId).value);
    if (!dstr) return;
    const url = tier
      ? `/store/get_history?game=${game}&from=${encodeURIComponent(dstr)}&limit=20&tier=${encodeURIComponent(tier)}`
      : `/store/get_history?game=${game}&from=${encodeURIComponent(dstr)}&limit=20`;
    try {
      const j = await getJSON(url);
      qs(blobId).textContent = j.blob || "";
    } catch(e) {
      qs(blobId).textContent = `Load failed (${game}${tier?"/"+tier:""}): ${e}`;
    }
  }
  qs("histMmLoad")?.addEventListener("click", () => loadHist("MM","histMmFrom","HIST_MM_BLOB"));
  qs("histPbLoad")?.addEventListener("click", () => loadHist("PB","histPbFrom","HIST_PB_BLOB"));
  qs("histIlJpLoad")?.addEventListener("click", () => loadHist("IL","histIlJpFrom","HIST_IL_JP_BLOB","JP"));
  qs("histIlM1Load")?.addEventListener("click", () => loadHist("IL","histIlM1From","HIST_IL_M1_BLOB","M1"));
  qs("histIlM2Load")?.addEventListener("click", () => loadHist("IL","histIlM2From","HIST_IL_M2_BLOB","M2"));

  // Run Phase 1
  qs("runPhase1")?.addEventListener("click", async () => {
    const body = {
      LATEST_MM: qs("mmLatest").textContent.trim(),
      LATEST_PB: qs("pbLatest").textContent.trim(),
      LATEST_IL_JP: qs("ilJpLatest").textContent.trim(),
      LATEST_IL_M1: qs("ilM1Latest").textContent.trim(),
      LATEST_IL_M2: qs("ilM2Latest").textContent.trim(),
      FEED_MM: qs("FEED_MM").value,
      FEED_PB: qs("FEED_PB").value,
      FEED_IL: qs("FEED_IL").value,
      HIST_MM_BLOB: qs("HIST_MM_BLOB").textContent,
      HIST_PB_BLOB: qs("HIST_PB_BLOB").textContent,
      HIST_IL_JP_BLOB: qs("HIST_IL_JP_BLOB").textContent,
      HIST_IL_M1_BLOB: qs("HIST_IL_M1_BLOB").textContent,
      HIST_IL_M2_BLOB: qs("HIST_IL_M2_BLOB").textContent
    };
    const out = qs("phase1Result");
    try {
      const r = await fetch("/run_json", {
        method: "POST",
        headers: {"Content-Type":"application/json"},
        body: JSON.stringify(body)
      });
      const j = await r.json();
      if (j.ok) qs("phase1Path").value = j.saved_path || "";
      out.textContent = JSON.stringify(j, null, 2);
    } catch(e) {
      out.textContent = `Phase 1 failed: ${e}`;
    }
  });
});
