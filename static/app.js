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
  function qDate(sel) {
    const el = $(sel);
    if (!el || !el.value) return "";
    // to MM/DD/YYYY
    const d = new Date(el.value);
    if (isNaN(d)) return "";
    const mm = String(d.getMonth()+1).padStart(2,"0");
    const dd = String(d.getDate()).padStart(2,"0");
    const yyyy = d.getFullYear();
    return `${mm}/${dd}/${yyyy}`;
  }
  async function getJSON(url) {
    const r = await fetch(url);
    if (!r.ok) throw new Error(`${r.status} ${r.statusText}`);
    return await r.json();
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

  // ---------- Retrieve buttons ----------
  async function retrieve(game, dateSel, previewSel) {
    const date = qDate(dateSel);
    if (!date) { setMsg("Select a date first.", true); return; }
    try {
      const data = await getJSON(`/store/get_by_date?game=${encodeURIComponent(game)}&date=${encodeURIComponent(date)}`);
      if (!data.ok) throw new Error(data.detail || data.error || "not ok");
      const prev = fmtPreview(data.row);
      if (!prev) throw new Error("No data for that date.");
      $(previewSel).value = `[${prev}]`; // wrap to match your previous UI shape: [[mains], bonus]
      setMsg("");
    } catch (e) {
      setMsg(`Retrieve failed (${game}): ${e.message}`, true);
    }
  }

  $("#btn_get_mm")?.addEventListener("click", () => retrieve("MM", "#date_mm", "#mm_preview"));
  $("#btn_get_pb")?.addEventListener("click", () => retrieve("PB", "#date_pb", "#pb_preview"));
  $("#btn_get_il_jp")?.addEventListener("click", () => retrieve("IL_JP", "#date_il_jp", "#il_jp_preview"));
  $("#btn_get_il_m1")?.addEventListener("click", () => retrieve("IL_M1", "#date_il_m1", "#il_m1_preview"));
  $("#btn_get_il_m2")?.addEventListener("click", () => retrieve("IL_M2", "#date_il_m2", "#il_m2_preview"));

  // ---------- Load 20 history ----------
  async function load20(game, fromSel, blobSel) {
    const from = qDate(fromSel);
    if (!from) { setMsg("Pick a history start date (3rd newest).", true); return; }
    try {
      const data = await getJSON(`/store/get_history?game=${encodeURIComponent(game)}&from=${encodeURIComponent(from)}&limit=20`);
      if (!data.ok) throw new Error(data.detail || data.error || "not ok");
      $(blobSel).value = (data.blob || (data.rows?.join("\n") || "")).trim();
      setMsg("");
    } catch (e) {
      setMsg(`Load 20 failed (${game}): ${e.message}`, true);
    }
  }

  $("#btn_load20_mm")?.addEventListener("click", () => load20("MM", "#date_hist_mm", "#hist_mm_blob"));
  $("#btn_load20_pb")?.addEventListener("click", () => load20("PB", "#date_hist_pb", "#hist_pb_blob"));
  $("#btn_load20_il_jp")?.addEventListener("click", () => load20("IL_JP", "#date_hist_il_jp", "#hist_il_blob_jp"));
  $("#btn_load20_il_m1")?.addEventListener("click", () => load20("IL_M1", "#date_hist_il_m1", "#hist_il_blob_m1"));
  $("#btn_load20_il_m2")?.addEventListener("click", () => load20("IL_M2", "#date_hist_il_m2", "#hist_il_blob_m2"));

  // ---------- Run Phase 1 ----------
  $("#btn_run_phase1")?.addEventListener("click", async () => {
    setMsg("");
    const LATEST_MM   = val("#mm_preview");
    const LATEST_PB   = val("#pb_preview");
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
