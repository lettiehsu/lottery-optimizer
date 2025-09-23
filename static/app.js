// Utility
async function getJSON(url) {
  const r = await fetch(url);
  if (!r.ok) throw new Error(`${r.status} ${r.statusText}`);
  return r.json();
}
function fmtLatest(row, isIL=false) {
  if (!row) return "";
  const mains = row.mains.map(n => n.toString().padStart(2,"0")).join(", ");
  const bonus = row.bonus == null ? "null" : row.bonus;
  return isIL ? `[[  ${mains.replace(/, /g,",  ") }], null]`
              : `[[  ${mains.replace(/, /g,",  ") }], ${bonus}]`;
}
function qs(id) { return document.getElementById(id); }

// Upload CSV
window.addEventListener("DOMContentLoaded", () => {
  const form = qs("csvForm");
  if (form) {
    form.addEventListener("submit", async (e) => {
      e.preventDefault();
      const out = qs("csvResult");
      try {
        const fd = new FormData(form);
        const r = await fetch(form.action, { method: "POST", body: fd });
        const data = await r.json();
        out.textContent = JSON.stringify(data, null, 2);
      } catch (err) {
        out.textContent = `Upload failed: ${err}`;
      }
    });
  }

  // Retrieve latest by date
  qs("mmRetrieve")?.addEventListener("click", async () => {
    const date = qs("mmDate").value;
    if (!date) return;
    const d = new Date(date);
    const dstr = `${(d.getMonth()+1).toString().padStart(2,"0")}/${d.getDate().toString().padStart(2,"0")}/${d.getFullYear()}`;
    try {
      const j = await getJSON(`/store/get_by_date?game=MM&date=${encodeURIComponent(dstr)}`);
      qs("mmLatest").textContent = fmtLatest(j.row, false);
    } catch (e) {
      qs("mmLatest").textContent = `Retrieve failed (MM): ${e}`;
    }
  });
  qs("pbRetrieve")?.addEventListener("click", async () => {
    const date = qs("pbDate").value;
    if (!date) return;
    const d = new Date(date);
    const dstr = `${(d.getMonth()+1).toString().padStart(2,"0")}/${d.getDate().toString().padStart(2,"0")}/${d.getFullYear()}`;
    try {
      const j = await getJSON(`/store/get_by_date?game=PB&date=${encodeURIComponent(dstr)}`);
      qs("pbLatest").textContent = fmtLatest(j.row, false);
    } catch (e) {
      qs("pbLatest").textContent = `Retrieve failed (PB): ${e}`;
    }
  });
  const getIl = async (tierId, outId, tier) => {
    const date = qs(tierId).value;
    if (!date) return;
    const d = new Date(date);
    const dstr = `${(d.getMonth()+1).toString().padStart(2,"0")}/${d.getDate().toString().padStart(2,"0")}/${d.getFullYear()}`;
    try {
      const j = await getJSON(`/store/get_by_date?game=IL&date=${encodeURIComponent(dstr)}`);
      // If caller wants specific tier (JP/M1/M2), fetch exact
      let row = j.row;
      const r2 = await getJSON(`/store/get_history?game=IL&from=${encodeURIComponent(dstr)}&limit=1`);
      // If r2.rows[0].tier exists, or you keep tiers separately, you can adapt.
      // Simpler: query exact tier via store.get_exact using a dedicated endpoint in future.
      qs(outId).textContent = fmtLatest(row, true);
    } catch (e) {
      qs(outId).textContent = `Retrieve failed (IL ${tier}): ${e}`;
    }
  };
  qs("ilJpRetrieve")?.addEventListener("click", () => getIl("ilJpDate","ilJpLatest","JP"));
  qs("ilM1Retrieve")?.addEventListener("click", () => getIl("ilM1Date","ilM1Latest","M1"));
  qs("ilM2Retrieve")?.addEventListener("click", () => getIl("ilM2Date","ilM2Latest","M2"));

  // Load 20 history blobs
  const loadHist = async (game, fromDate, blobId, tier="") => {
    const d = new Date(fromDate);
    const dstr = `${(d.getMonth()+1).toString().padStart(2,"0")}/${d.getDate().toString().padStart(2,"0")}/${d.getFullYear()}`;
    const url = tier ? `/store/get_history?game=${game}&from=${encodeURIComponent(dstr)}&limit=20&tier=${tier}`
                     : `/store/get_history?game=${game}&from=${encodeURIComponent(dstr)}&limit=20`;
    const out = qs(blobId);
    try {
      const j = await getJSON(url);
      out.textContent = j.blob || "";
    } catch (e) {
      out.textContent = `Load failed (${game}${tier?"/"+tier:""}): ${e}`;
    }
  };
  qs("histMmLoad")?.addEventListener("click", () => {
    const v = qs("histMmFrom").value;
    if (v) loadHist("MM", v, "HIST_MM_BLOB");
  });
  qs("histPbLoad")?.addEventListener("click", () => {
    const v = qs("histPbFrom").value;
    if (v) loadHist("PB", v, "HIST_PB_BLOB");
  });
  qs("histIlJpLoad")?.addEventListener("click", () => {
    const v = qs("histIlJpFrom").value;
    if (v) loadHist("IL", v, "HIST_IL_JP_BLOB", "JP");
  });
  qs("histIlM1Load")?.addEventListener("click", () => {
    const v = qs("histIlM1From").value;
    if (v) loadHist("IL", v, "HIST_IL_M1_BLOB", "M1");
  });
  qs("histIlM2Load")?.addEventListener("click", () => {
    const v = qs("histIlM2From").value;
    if (v) loadHist("IL", v, "HIST_IL_M2_BLOB", "M2");
  });

  // Run Phase 1 → send all fields to /run_json
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
      if (j.ok) {
        qs("phase1Path").value = j.saved_path || "";
      }
      out.textContent = JSON.stringify(j, null, 2);
    } catch (e) {
      out.textContent = `Phase 1 failed: ${e}`;
    }
  });
});
