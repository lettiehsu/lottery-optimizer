// ===== Helpers =====
const $ = (sel) => document.querySelector(sel);
const j = (v) => JSON.stringify(v, null, 2);

async function getJSON(url) {
  const r = await fetch(url);
  if (!r.ok) {
    let t = await r.text();
    throw new Error(`${r.status} ${r.statusText} — ${t}`);
  }
  return r.json();
}
async function postForm(url, formData) {
  const r = await fetch(url, { method: "POST", body: formData });
  if (!r.ok) {
    let t = await r.text();
    throw new Error(`${r.status} ${r.statusText} — ${t}`);
  }
  return r.json();
}
async function postJSON(url, payload) {
  const r = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!r.ok) {
    let t = await r.text();
    throw new Error(`${r.status} ${r.statusText} — ${t}`);
  }
  return r.json();
}

function dd(val) {
  // Expecting an <input type="date"> value like "2025-09-16".
  // The store expects "MM/DD/YYYY".
  if (!val) return "";
  const [yyyy, mm, dd] = val.split("-");
  return `${mm}/${dd}/${yyyy}`;
}

// Map friendly names to server keys.
const GAME_KEYS = {
  MM: "MM",
  PB: "PB",
  IL_JP: "IL_JP",
  IL_M1: "IL_M1",
  IL_M2: "IL_M2",
};

// Put a result string into a text input safely
function setPreview(el, mains, bonus) {
  // The Phase-1 backend expects the NJ values **as a string** of the form:
  //   '[[a,b,c,d,e], bonus]'
  // For IL tiers, bonus must be null.
  const s = `[${j(mains)}, ${bonus === null ? "null" : bonus}]`;
  el.value = s;
}

// ===== CSV Upload =====
$("#btnImport").addEventListener("click", async () => {
  try {
    const file = $("#csvFile").files[0];
    if (!file) throw new Error("Choose a CSV first.");
    const form = new FormData();
    form.append("file", file, file.name);
    form.append("overwrite", $("#overwrite").checked ? "true" : "false");
    const res = await postForm("/store/import_csv", form);
    $("#importResult").textContent = j(res);
  } catch (e) {
    $("#importResult").textContent = String(e);
  }
});

// ===== Retrieve single date → preview boxes =====
async function retrieve(gameKey, dateEl, previewEl, forceNullBonus = false) {
  const dateStr = dd(dateEl.value);
  if (!dateStr) {
    previewEl.value = "";
    throw new Error("Pick a date first.");
  }
  const url = `/store/get_by_date?game=${encodeURIComponent(gameKey)}&date=${encodeURIComponent(dateStr)}`;
  const data = await getJSON(url);
  // Expect {ok:true, row:{mains:[..], bonus: <number|null>}}
  const mains = data.row?.mains || [];
  let bonus = data.row?.bonus ?? null;
  if (forceNullBonus) bonus = null;
  setPreview(previewEl, mains, bonus);
}

// Wire up retrieve buttons
$("#mmFetch").addEventListener("click", async () => {
  try { await retrieve(GAME_KEYS.MM, $("#mmDate"), $("#mmPreview")); }
  catch(e){ alert(`MM retrieve failed: ${e.message}`); }
});
$("#pbFetch").addEventListener("click", async () => {
  try { await retrieve(GAME_KEYS.PB, $("#pbDate"), $("#pbPreview")); }
  catch(e){ alert(`PB retrieve failed: ${e.message}`); }
});
$("#ilJPFetch").addEventListener("click", async () => {
  try { await retrieve(GAME_KEYS.IL_JP, $("#ilJPDate"), $("#ilJPPreview"), true); }
  catch(e){ alert(`IL JP retrieve failed: ${e.message}`); }
});
$("#ilM1Fetch").addEventListener("click", async () => {
  try { await retrieve(GAME_KEYS.IL_M1, $("#ilM1Date"), $("#ilM1Preview"), true); }
  catch(e){ alert(`IL M1 retrieve failed: ${e.message}`); }
});
$("#ilM2Fetch").addEventListener("click", async () => {
  try { await retrieve(GAME_KEYS.IL_M2, $("#ilM2Date"), $("#ilM2Preview"), true); }
  catch(e){ alert(`IL M2 retrieve failed: ${e.message}`); }
});

// ===== Load 20 history rows into blobs =====
async function load20(gameKey, fromEl, blobEl) {
  const fromStr = dd(fromEl.value);
  if (!fromStr) { blobEl.value = ""; throw new Error("Pick a 'from' date first."); }
  const url = `/store/get_history?game=${encodeURIComponent(gameKey)}&from=${encodeURIComponent(fromStr)}&limit=20`;
  const data = await getJSON(url);
  // Expect { ok:true, blob:"top-down text ..." }
  blobEl.value = data.blob || "";
}

$("#mmHistLoad").addEventListener("click", async () => {
  try { await load20(GAME_KEYS.MM, $("#mmHistFrom"), $("#mmHist")); }
  catch(e){ alert(`Load20 (MM): ${e.message}`); }
});
$("#pbHistLoad").addEventListener("click", async () => {
  try { await load20(GAME_KEYS.PB, $("#pbHistFrom"), $("#pbHist")); }
  catch(e){ alert(`Load20 (PB): ${e.message}`); }
});
$("#ilJPHistLoad").addEventListener("click", async () => {
  try { await load20(GAME_KEYS.IL_JP, $("#ilJPHistFrom"), $("#ilJPHist")); }
  catch(e){ alert(`Load20 (IL_JP): ${e.message}`); }
});
$("#ilM1HistLoad").addEventListener("click", async () => {
  try { await load20(GAME_KEYS.IL_M1, $("#ilM1HistFrom"), $("#ilM1Hist")); }
  catch(e){ alert(`Load20 (IL_M1): ${e.message}`); }
});
$("#ilM2HistLoad").addEventListener("click", async () => {
  try { await load20(GAME_KEYS.IL_M2, $("#ilM2HistFrom"), $("#ilM2Hist")); }
  catch(e){ alert(`Load20 (IL_M2): ${e.message}`); }
});

// ===== Run Phase 1 =====
$("#runPhase1").addEventListener("click", async () => {
  try {
    // IMPORTANT: send the *strings* exactly as Phase-1 expects
    const payload = {
      phase: "phase1",
      LATEST_MM: $("#mmPreview").value.trim(),
      LATEST_PB: $("#pbPreview").value.trim(),
      LATEST_IL_JP: $("#ilJPPreview").value.trim(),
      LATEST_IL_M1: $("#ilM1Preview").value.trim(),
      LATEST_IL_M2: $("#ilM2Preview").value.trim(),
      FEED_MM: $("#feedMM").value.trim(),
      FEED_PB: $("#feedPB").value.trim(),
      FEED_IL: $("#feedIL").value.trim(),
      HIST_MM_BLOB: $("#mmHist").value.trim(),
      HIST_PB_BLOB: $("#pbHist").value.trim(),
      HIST_IL_JP_BLOB: $("#ilJPHist").value.trim(),
      HIST_IL_M1_BLOB: $("#ilM1Hist").value.trim(),
      HIST_IL_M2_BLOB: $("#ilM2Hist").value.trim(),
    };

    // quick validation so we don't send empty strings by accident
    const need = ["LATEST_MM","LATEST_PB","LATEST_IL_JP","LATEST_IL_M1","LATEST_IL_M2"];
    for (const k of need) {
      const v = payload[k] || "";
      if (!v.startsWith("[[")) throw new Error(`${k} is missing or malformed (expected string like '[[..], b]')`);
    }

    const res = await postJSON("/run_json", payload);
    $("#phase1Result").textContent = j(res);
    if (res && res.saved_path) $("#phase1Path").value = res.saved_path;

    // If your core returns richer objects (tables, bands, etc.), you can also
    // render them here. This keeps it generic:
    //   if (res.mm_hits) renderHits("mmBox", res.mm_hits) ...
  } catch (e) {
    $("#phase1Result").textContent = String(e);
  }
});
