/* global fetch */
(function () {
  const $  = (s) => document.querySelector(s);
  const val = (s) => (document.querySelector(s)?.value || "").trim();

  // ---------- helpers ----------
  function setMsg(text, isErr=false) {
    const el = $("#phase1_msg");
    if (!el) return;
    el.textContent = text || "";
    el.classList.toggle("danger", !!isErr);
    el.classList.toggle("muted", !isErr);
  }
  function fmtPreview(row) {
    // row from /store/get_by_date → {mains:[...], bonus: int|null}
    if (!row || !Array.isArray(row.mains)) return "";
    const bonus = (row.bonus === null || row.bonus === undefined) ? "null" : row.bonus;
    return `[${JSON.stringify(row.mains)}, ${bonus}]`;
  }
  function toMMDDYYYY(htmlDateValue) {
    // htmlDateValue is yyyy-mm-dd
    const d = new Date(htmlDateValue);
    if (isNaN(d)) return "";
    const mm = String(d.getMonth()+1).padStart(2,"0");
    const dd = String(d.getDate()).padStart(2,"0");
    const yyyy = d.getFullYear();
    return `${mm}/${dd}/${yyyy}`;
  }
  function toM_D_YYYY(mmddyyyy) {
    // turn "09/16/2025" into "9/16/2025"
    const [mm, dd, yyyy] = mmddyyyy.split("/");
    const m = String(parseInt(mm,10));
    const d = String(parseInt(dd,10));
    return `${m}/${d}/${yyyy}`;
  }
  function qDate(sel) {
    const el = $(sel);
    if (!el || !el.value) return {mmddyyyy:"", mdyyyy:""};
    const mmddyyyy = toMMDDYYYY(el.value);
    return { mmddyyyy, mdyyyy: toM_D_YYYY(mmddyyyy) };
  }
  async function getJSON(url) {
    const r = await fetch(url);
    // if 404: we still return JSON attempt; caller will handle
    if (r.status === 404) return {__404:true, raw: await r.text()};
    const data = await r.json();
    if (!r.ok) {
      const msg = data?.detail || data?.error || `${r.status} ${r.statusText}`;
      throw new Error(msg);
    }
    return data;
  }

  // ---------- CSV import ----------
  const importBtn = $("#csv_import");
  if (importBtn) {
    importBtn.addEventListener("click", async () => {
      const file = $("#csv_file")?.files?.[0];
      if (!file) { $("#csv_result").textContent = "Choose a CSV first."; return; }
      const overwrite = $("#csv_overwrite").checked;
      const fd = new FormData();
      fd.append("file", file);
      fd.append("overwrite", overwrite ? "true" : "false");
      $("#csv_result").textContent = "Uploading…";
      try {
        const res = await fetch("/store/import_csv", { method:"POST", body: fd });
        const data = await res.json();
        $("#csv_result").textContent = JSON.stringify(data, null, 2);
      } catch (e) {
        $("#csv_result").textContent = String(e);
      }
    });
  }

  // ---------- Retrieve buttons (with fallbacks) ----------
  async function retrieve(gameKey, dateSel, previewSel) {
    const {mmddyyyy, mdyyyy} = qDate(dateSel);
    if (!mmddyyyy) { setMsg("Select a date first.", true); return; }

    // Build candidate URLs in order we want to try
    const urls = [];

    // 1) compact game keys (MM, PB, IL_JP, IL_M1, IL_M2)
    urls.push(`/store/get_by_date?game=${encodeURIComponent(gameKey)}&date=${encodeURIComponent(mmddyyyy)}`);
    urls.push(`/store/get_by_date?game=${encodeURIComponent(gameKey)}&date=${encodeURIComponent(mdyyyy)}`);

    // 2) IL split form (game=IL&tier=JP/M1/M2)
    if (gameKey.startsWith("IL_")) {
      const tier = gameKey.split("_")[1]; // JP/M1/M2
      urls.push(`/store/get_by_date?game=IL&tier=${encodeURIComponent(tier)}&date=${encodeURIComponent(mmddyyyy)}`);
      urls.push(`/store/get_by_date?game=IL&tier=${encodeURIComponent(tier)}&date=${encodeURIComponent(mdyyyy)}`);
    }

    let last404 = null, lastErr = null;
    for (const u of urls) {
      try {
        const data = await getJSON(u);
        if (data.__404) { last404 = u; continue; }
        if (!data.ok) { lastErr = data.detail || data.error || "not ok"; continue; }
        const prev = fmtPreview(data.row);
        if (!prev) { lastErr = "No data returned"; continue; }
        $(previewSel).value = `[${prev}]`; // match prior UI: [[mains], bonus]
        setMsg("");
        return;
      } catch (e) {
        lastErr = e.message;
      }
    }
    setMsg(`Retrieve failed (${gameKey}): ${lastErr || "404 not found"}${last404 ? " — " + last404 : ""}`, true);
  }

  $("#btn_get_mm")?.addEventListener("click", () => retrieve("MM", "#date_mm", "#mm_preview"));
  $("#btn_get_pb")?.addEventListener("click", () => retrieve("PB", "#date_pb", "#pb_preview"));
  $("#btn_get_il_jp")?.addEventListener("click", () => retrieve("IL_JP", "#date_il_jp", "#il_jp_preview"));
  $("#btn_get_il_m1")?.addEventListener("click", () => retrieve("IL_M1", "#date_il_m1", "#il_m1_preview"));
  $("#btn_get_il_m2")?.addEventListener("click", () => retrieve("IL_M2", "#date_il_m2", "#il_m2_preview"));

  // ---------- Load 20 history (with date format fallback) ----------
  async function load20(gameKey, fromSel, blobSel) {
    const {mmddyyyy, mdyyyy} = qDate(fromSel);
    if (!mmddyyyy) { setMsg("Pick a history start date (3rd newest).", true); return; }

    const urls = [];

    // compact game keys
    urls.push(`/store/get_history?game=${encodeURIComponent(gameKey)}&from=${encodeURIComponent(mmddyyyy)}&limit=20`);
    urls.push(`/store/get_history?game=${encodeURIComponent(gameKey)}&from=${encodeURIComponent(mdyyyy)}&limit=20`);

    // IL split form
    if (gameKey.startsWith("IL_")) {
      const tier = gameKey.split("_")[1];
      urls.push(`/store/get_history?game=IL&tier=${encodeURIComponent(tier)}&from=${encodeURIComponent(mmddyyyy)}&limit=20`);
      urls.push(`/store/get_history?game=IL&tier=${encodeURIComponent(tier)}&from=${encodeURIComponent(mdyyyy)}&limit=20`);
    }

    let last404 = null, lastErr = null;
    for (const u of urls) {
      try {
        const data = await getJSON(u);
        if (data.__404) { last404 = u; continue; }
        if (!data.ok) { lastErr = data.detail || data.error || "not ok"; continue; }
        $(blobSel).value = (data.blob || (data.rows?.join("\n") || "")).trim();
        setMsg("");
        return;
      } catch (e) {
        lastErr = e.message;
      }
    }
    setMsg(`Load 20 failed (${gameKey}): ${lastErr || "404 not found"}${last404 ? " — " + last404 : ""}`, true);
  }

  $("#btn_load20_mm")?.addEventListener("click", () => load20("MM",   "#date_hist_mm",   "#hist_mm_blob"));
  $("#btn_load20_pb")?.addEventListener("click", () => load20("PB",   "#date_hist_pb",   "#hist_pb_blob"));
  $("#btn_load20_il_jp")?.addEventListener("click", () => load20("IL_JP", "#date_hist_il_jp", "#hist_il_blob_jp"));
  $("#btn_load20_il_m1")?.addEventListener("click", () => load20("IL_M1", "#date_hist_il_m1", "#hist_il_blob_m1"));
  $("#btn_load20_il_m2")?.addEventListener("click", () => load20("IL_M2", "#date_hist_il_m2", "#hist_il_blob_m2"));

  // ---------- Run Phase 1 ----------
  $("#btn_run_phase1")?.addEventListener("click", async () => {
    setMsg("");
    const LATEST_MM    = val("#mm_preview");
    const LATEST_PB    = val("#pb_preview");
    const LATEST_IL_JP = val("#il_jp_preview");
    const LATEST_IL_M1 = val("#il_m1_preview");
    const LATEST_IL_M2 = val("#il_m2_preview");

    if (!LATEST_MM || !LATEST_PB || !LATEST_IL_JP || !LATEST_IL_M1 || !LATEST_IL_M2) {
      setMsg("Pick dates and click Retrieve for all five games first.", true);
      return;
    }

    const payload = {
      LATEST_MM, LATEST_PB, LATEST_IL_JP, LATEST_IL_M1, LATEST_IL_M2,
      FEED_MM: val("#feed_mm"),
      FEED_PB: val("#feed_pb"),
      FEED_IL: val("#feed_il"),
      HIST_MM_BLOB: val("#hist_mm_blob"),
      HIST_PB_BLOB: val("#hist_pb_blob"),
      HIST_IL_BLOB: [val("#hist_il_blob_jp"), val("#hist_il_blob_m1"), val("#hist_il_blob_m2")].filter(Boolean).join("\n")
    };

    const btn = $("#btn_run_phase1");
    btn.disabled = true; document.body.style.cursor = "wait";

    try {
      const r = await fetch("/run_json", {
        method: "POST",
        headers: {"Content-Type":"application/json"},
        body: JSON.stringify(payload)
      });
      const data = await r.json();
      if (!r.ok || data.ok === false) {
        setMsg(`Phase 1 failed: ${data.detail || data.error || (r.status + " " + r.statusText)}`, true);
        return;
      }
      const path = data.saved_path || "";
      if ($("#phase1_saved_path")) $("#phase1_saved_path").value = path;
      setMsg("Phase 1 completed. Saved state ready for Phase 2.");
    } catch (e) {
      setMsg(`Network/parse error: ${e.message}`, true);
    } finally {
      btn.disabled = false; document.body.style.cursor = "default";
    }
  });

})();
