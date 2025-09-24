/* static/app.js — full frontend logic for upload, retrieve, history, phase 1  */

// ------------------------------
// Tiny helpers
// ------------------------------
const $ = (sel) => document.querySelector(sel);
const two = (n) => String(n).padStart(2, "0");

function toast(msg, kind = "ok", ms = 2200) {
  let node = document.createElement("div");
  node.textContent = String(msg);
  node.style.position = "fixed";
  node.style.left = "50%";
  node.style.bottom = "24px";
  node.style.transform = "translateX(-50%)";
  node.style.padding = "10px 14px";
  node.style.borderRadius = "10px";
  node.style.fontSize = "13px";
  node.style.boxShadow = "0 6px 16px rgba(0,0,0,.15)";
  node.style.zIndex = 9999;
  if (kind === "ok") {
    node.style.background = "#e8f4ff";
    node.style.border = "1px solid #bcdcff";
    node.style.color = "#0b4d8a";
  } else if (kind === "warn") {
    node.style.background = "#fff7e6";
    node.style.border = "1px solid #ffd27a";
    node.style.color = "#7a4b00";
  } else {
    node.style.background = "#ffecec";
    node.style.border = "1px solid #ffb4b4";
    node.style.color = "#8a1f1f";
  }
  document.body.appendChild(node);
  setTimeout(() => node.remove(), ms);
}

async function getJSON(url) {
  const r = await fetch(url, { credentials: "same-origin" });
  const t = await r.text();
  try { return JSON.parse(t); } catch { return { ok: false, detail: t }; }
}
async function postJSON(url, body) {
  const r = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    credentials: "same-origin",
  });
  const t = await r.text();
  try { return JSON.parse(t); } catch { return { ok: false, detail: t }; }
}
function buttonBusy(btn, on, label = "") {
  if (!btn) return;
  if (on) {
    btn.setAttribute("data-old", btn.textContent);
    btn.disabled = true;
    if (label) btn.textContent = label;
  } else {
    const old = btn.getAttribute("data-old");
    if (old) btn.textContent = old;
    btn.disabled = false;
  }
}

// ------------------------------
// Upload CSV
// ------------------------------
const csvFile = $("#csvFile");
const overwrite = $("#overwrite");
const importBtn = $("#importBtn");
const importLog = $("#importLog");

importBtn?.addEventListener("click", async () => {
  if (!csvFile?.files?.length) {
    return toast("Choose a CSV file first.", "warn");
  }
  const fd = new FormData();
  fd.append("file", csvFile.files[0]);
  fd.append("overwrite", overwrite?.checked ? "true" : "false");
  buttonBusy(importBtn, true, "Importing…");
  importLog.value = "";
  try {
    const r = await fetch("/store/import_csv", { method: "POST", body: fd });
    const txt = await r.text();
    importLog.value = txt;
    try {
      const js = JSON.parse(txt);
      toast(js.ok ? "CSV imported." : "Import returned an error", js.ok ? "ok" : "error");
    } catch {
      toast("CSV import response received.", "ok");
    }
  } catch (e) {
    importLog.value = String(e);
    toast(String(e), "error", 4000);
  } finally {
    buttonBusy(importBtn, false);
  }
});

// ------------------------------
// Retrieve “2nd newest” (per-game) rows
// ------------------------------
const mmDate = $("#mmDate"), mmPreview = $("#mmPreview"), mmRetrieve = $("#mmRetrieve");
const pbDate = $("#pbDate"), pbPreview = $("#pbPreview"), pbRetrieve = $("#pbRetrieve");
const ilJPDate = $("#ilJPDate"), ilJPPreview = $("#ilJPPreview"), ilJPRetrieve = $("#ilJPRetrieve");
const ilM1Date = $("#ilM1Date"), ilM1Preview = $("#ilM1Preview"), ilM1Retrieve = $("#ilM1Retrieve");
const ilM2Date = $("#ilM2Date"), ilM2Preview = $("#ilM2Preview"), ilM2Retrieve = $("#ilM2Retrieve");

async function doRetrieve(btn, game, dateStr, previewEl, tier = "") {
  if (!dateStr) return toast("Enter a date (MM/DD/YYYY).", "warn");
  const params = new URLSearchParams({ game, date: dateStr });
  if (tier) params.set("tier", tier);
  buttonBusy(btn, true, "Retrieving…");
  try {
    const data = await getJSON(`/store/get_by_date?${params.toString()}`);
    if (!data?.ok) throw new Error(data?.detail || data?.error || "Retrieve failed.");
    // Expect [[mains..], bonus] or [[mains..], null] (IL)
    previewEl.value = JSON.stringify(data.row);
    toast(`${game}${tier ? " " + tier : ""} retrieved.`, "ok");
  } catch (e) {
    previewEl.value = "";
    toast(String(e), "error", 3500);
  } finally {
    buttonBusy(btn, false);
  }
}

mmRetrieve?.addEventListener("click", () =>
  doRetrieve(mmRetrieve, "MM", mmDate.value.trim(), mmPreview));
pbRetrieve?.addEventListener("click", () =>
  doRetrieve(pbRetrieve, "PB", pbDate.value.trim(), pbPreview));
ilJPRetrieve?.addEventListener("click", () =>
  doRetrieve(ilJPRetrieve, "IL", ilJPDate.value.trim(), ilJPPreview, "JP"));
ilM1Retrieve?.addEventListener("click", () =>
  doRetrieve(ilM1Retrieve, "IL", ilM1Date.value.trim(), ilM1Preview, "M1"));
ilM2Retrieve?.addEventListener("click", () =>
  doRetrieve(ilM2Retrieve, "IL", ilM2Date.value.trim(), ilM2Preview, "M2"));

// ------------------------------
// History “Load 20” — robust formatting
// ------------------------------
const histMmDate = $("#histMmDate"), histMmBlob = $("#histMmBlob"), histMmLoad = $("#histMmLoad");
const histPbDate = $("#histPbDate"), histPbBlob = $("#histPbBlob"), histPbLoad = $("#histPbLoad");
const histIlJpDate = $("#histIlJpDate"), histIlJpBlob = $("#histIlJpBlob"), histIlJpLoad = $("#histIlJpLoad");
const histIlM1Date = $("#histIlM1Date"), histIlM1Blob = $("#histIlM1Blob"), histIlM1Load = $("#histIlM1Load");
const histIlM2Date = $("#histIlM2Date"), histIlM2Blob = $("#histIlM2Blob"), histIlM2Load = $("#histIlM2Load");

function formatHistoryRow(row, game) {
  if (typeof row === "string") return row.trim();

  // Try fields
  const d = row.draw_date || row.date || row.drawDate || null;

  let mains = row.mains;
  if (!Array.isArray(mains)) {
    const arr = [];
    for (let i = 1; i <= 6; i++) {
      const k = "n" + i;
      if (row[k] != null) arr.push(+row[k]);
    }
    mains = arr.length ? arr : null;
  }
  const bonus =
    row.bonus != null ? row.bonus :
    row.MB != null ? row.MB :
    row.PB != null ? row.PB : null;

  // date: mm-dd-yy
  let mmddy = "--";
  if (d) {
    try {
      if (/\d{2}\/\d{2}\/\d{4}/.test(d)) {
        const [mm, dd, yyyy] = d.split("/").map(Number);
        mmddy = `${two(mm)}-${two(dd)}-${String(yyyy).slice(-2)}`;
      } else if (/\d{4}-\d{2}-\d{2}/.test(d)) {
        const [yyyy, mm, dd] = d.split("-").map(Number);
        mmddy = `${two(mm)}-${two(dd)}-${String(yyyy).slice(-2)}`;
      } else {
        mmddy = String(d);
      }
    } catch { mmddy = String(d); }
  }
  if (Array.isArray(mains) && mains.length) {
    const nums = mains.map((n) => two(n)).join("-");
    if (bonus != null) return `${mmddy}  ${nums}  ${two(bonus)}`;
    return `${mmddy}  ${nums}`;
  }
  return JSON.stringify(row);
}

async function loadHistory20(btn, { game, tier, fromDate, target }) {
  if (!fromDate) return toast("Enter a start date (MM/DD/YYYY).", "warn");
  const params = new URLSearchParams({ game, from: fromDate, limit: "20" });
  if (tier) params.set("tier", tier);

  buttonBusy(btn, true, "Loading…");
  try {
    const data = await getJSON(`/store/get_history?${params.toString()}`);
    if (!data?.ok) throw new Error(data?.detail || data?.error || "History load failed.");

    let lines = [];
    if (Array.isArray(data.rows)) {
      lines = data.rows.map((r) => formatHistoryRow(r, game));
    } else if (typeof data.blob === "string") {
      lines = data.blob.trim().split(/\r?\n/);
    } else if (typeof data === "string") {
      lines = data.trim().split(/\r?\n/);
    }
    target.value = lines.join("\n");
    toast(`${game}${tier ? " " + tier : ""}: loaded ${lines.length} rows.`, "ok");
  } catch (err) {
    target.value = "";
    toast(String(err), "error", 4000);
  } finally {
    buttonBusy(btn, false);
  }
}

histMmLoad?.addEventListener("click", () =>
  loadHistory20(histMmLoad, { game: "MM", fromDate: histMmDate.value.trim(), target: histMmBlob }));
histPbLoad?.addEventListener("click", () =>
  loadHistory20(histPbLoad, { game: "PB", fromDate: histPbDate.value.trim(), target: histPbBlob }));
histIlJpLoad?.addEventListener("click", () =>
  loadHistory20(histIlJpLoad, { game: "IL", tier: "JP", fromDate: histIlJpDate.value.trim(), target: histIlJpBlob }));
histIlM1Load?.addEventListener("click", () =>
  loadHistory20(histIlM1Load, { game: "IL", tier: "M1", fromDate: histIlM1Date.value.trim(), target: histIlM1Blob }));
histIlM2Load?.addEventListener("click", () =>
  loadHistory20(histIlM2Load, { game: "IL", tier: "M2", fromDate: histIlM2Date.value.trim(), target: histIlM2Blob }));

// ------------------------------
// Phase 1 — run + render
// ------------------------------
const feedMM = $("#feedMM"), feedPB = $("#feedPB"), feedIL = $("#feedIL");
const runPhase1 = $("#runPhase1"), phase1Path = $("#phase1Path"), phase1Debug = $("#phase1Debug");

// Output slots
const mmBatch = $("#mmBatch"), mmStats = $("#mmStats"), mmRows = $("#mmRows"), mmCounts = $("#mmCounts");
const pbBatch = $("#pbBatch"), pbStats = $("#pbStats"), pbRows = $("#pbRows"), pbCounts = $("#pbCounts");
const ilBatch = $("#ilBatch"), ilStats = $("#ilStats"), ilRows = $("#ilRows"), ilCounts = $("#ilCounts");

function renderList(olEl, lines) {
  if (!olEl) return;
  olEl.innerHTML = "";
  (lines || []).forEach((txt) => {
    const li = document.createElement("li");
    li.className = "mono";
    li.textContent = txt;
    olEl.appendChild(li);
  });
}
function renderCounts(spanEl, countsObj, mapKeys) {
  if (!spanEl || !countsObj) return;
  const parts = [];
  mapKeys.forEach((k) => parts.push(`${k}:${countsObj[k] ?? 0}`));
  spanEl.textContent = parts.join("   ");
}
function renderRowIndices(preEl, rowsObj, mapKeys) {
  if (!preEl || !rowsObj) return;
  const lines = [];
  mapKeys.forEach((k) => {
    const arr = rowsObj[k] || [];
    const label = (k.includes("+")) ? `${k}` : `${k}:`;
    lines.push(`${label} ${arr.length ? arr.join(", ") : "—"}`);
  });
  preEl.textContent = lines.join("\n");
}

runPhase1?.addEventListener("click", async () => {
  // Collect payload for core
  const payload = {
    phase: "phase1",
    FEED_MM: feedMM?.value || "",
    FEED_PB: feedPB?.value || "",
    FEED_IL: feedIL?.value || "",
    LATEST_MM: (mmPreview?.value || "").trim(),
    LATEST_PB: (pbPreview?.value || "").trim(),
    LATEST_IL_JP: (ilJPPreview?.value || "").trim(),
    LATEST_IL_M1: (ilM1Preview?.value || "").trim(),
    LATEST_IL_M2: (ilM2Preview?.value || "").trim(),
    HIST_MM_BLOB: (histMmBlob?.value || "").trim(),
    HIST_PB_BLOB: (histPbBlob?.value || "").trim(),
    HIST_IL_JP_BLOB: (histIlJpBlob?.value || "").trim(),
    HIST_IL_M1_BLOB: (histIlM1Blob?.value || "").trim(),
    HIST_IL_M2_BLOB: (histIlM2Blob?.value || "").trim(),
  };

  // Basic guard: LATEST_* must be a JSON string like "[[..],b]"
  function saneLatest(s) {
    return /^\s*\[\s*\[/.test(s || "");
  }
  if (!saneLatest(payload.LATEST_MM) || !saneLatest(payload.LATEST_PB) ||
      !saneLatest(payload.LATEST_IL_JP) || !saneLatest(payload.LATEST_IL_M1) || !saneLatest(payload.LATEST_IL_M2)) {
    toast("Error: LATEST_* must be a string like '[[..],b]' or '[[..],null]'.", "error", 4000);
    return;
  }

  buttonBusy(runPhase1, true, "Running…");
  phase1Path.value = "";
  try {
    const res = await postJSON("/core/phase1", payload);
    if (!res?.ok) throw new Error(res?.detail || res?.error || "Phase 1 failed.");

    // Path
    if (phase1Path) {
      phase1Path.value = res.saved_path || "";
    }

    // Optional raw debug
    if (phase1Debug) {
      phase1Debug.textContent = JSON.stringify(res, null, 2);
    }

    // Render 3 columns (defensive to shape)
    const echo = res.echo || {};

    // Mega Millions
    renderList(mmBatch, echo.BATCH_MM || []);
    // counts: 3, 3+B, 4, 4+B, 5, 5+B
    renderCounts(mmStats, (echo.HITS_MM || {}).counts || {}, ["3","3+B","4","4+B","5","5+B"]);
    if (mmCounts) mmCounts.textContent = ""; // (can also show exact rows count, etc)
    renderRowIndices(mmRows, (echo.HITS_MM || {}).rows || {}, ["3","3+B","4","4+B","5","5+B"]);

    // Powerball
    renderList(pbBatch, echo.BATCH_PB || []);
    renderCounts(pbStats, (echo.HITS_PB || {}).counts || {}, ["3","3+B","4","4+B","5","5+B"]);
    renderRowIndices(pbRows, (echo.HITS_PB || {}).rows || {}, ["3","3+B","4","4+B","5","5+B"]);

    // IL Lotto (JP/M1/M2 counts in `echo.HITS_IL_*`)
    // We’ll compose a simple label line in ilStats:
    const jp = (echo.HITS_IL_JP||{}).counts||{};
    const m1 = (echo.HITS_IL_M1||{}).counts||{};
    const m2 = (echo.HITS_IL_M2||{}).counts||{};
    const ilStatsLine = [
      `JP 3:${jp["3"]||0} 4:${jp["4"]||0} 5:${jp["5"]||0} 6:${jp["6"]||0}`,
      `M1 3:${m1["3"]||0} 4:${m1["4"]||0} 5:${m1["5"]||0} 6:${m1["6"]||0}`,
      `M2 3:${m2["3"]||0} 4:${m2["4"]||0} 5:${m2["5"]||0} 6:${m2["6"]||0}`,
    ].join("   ");
    if (ilStats) ilStats.textContent = ilStatsLine;

    // IL batch (some cores return one combined batch, others separate; use BATCH_IL if present)
    renderList(ilBatch, echo.BATCH_IL || []);

    // Show row indices under IL (we’ll put JP/M1/M2 grouped)
    const lines = [];
    const rjp = (echo.HITS_IL_JP||{}).rows||{};
    const rm1 = (echo.HITS_IL_M1||{}).rows||{};
    const rm2 = (echo.HITS_IL_M2||{}).rows||{};
    function groupRows(title, r) {
      lines.push(`${title} rows:`);
      ["3","4","5","6"].forEach((k) => {
        const arr = r[k] || [];
        lines.push(`  ${k}: ${arr.length ? arr.join(", ") : "—"}`);
      });
    }
    groupRows("JP", rjp);
    groupRows("M1", rm1);
    groupRows("M2", rm2);
    if (ilRows) ilRows.textContent = lines.join("\n");

    toast("Phase 1 complete.", "ok");
  } catch (e) {
    toast(String(e), "error", 5000);
  } finally {
    buttonBusy(runPhase1, false);
  }
});
