/* static/app.js — buttons with clear feedback + full Phase 1 wiring */

(() => {
  // ---------- helpers ----------
  const $ = (sel) => document.querySelector(sel);
  const j = (sel) => Array.from(document.querySelectorAll(sel));

  const setJSON = (el, obj) => {
    el.textContent = JSON.stringify(obj, null, 2);
  };

  const toast = (msg, type = "info", ms = 2200) => {
    let t = document.createElement("div");
    t.className = `toast toast-${type}`;
    t.textContent = msg;
    document.body.appendChild(t);
    requestAnimationFrame(() => t.classList.add("show"));
    setTimeout(() => {
      t.classList.remove("show");
      setTimeout(() => t.remove(), 300);
    }, ms);
  };

  const buttonBusy = (btn, on = true, label = "Working…") => {
    if (!btn) return;
    if (on) {
      btn.dataset.label = btn.textContent;
      btn.textContent = `🟦 ${label}`;
      btn.classList.add("busy");
      btn.setAttribute("disabled", "disabled");
      btn.setAttribute("aria-busy", "true");
    } else {
      btn.textContent = btn.dataset.label || btn.textContent.replace(/^🟦\s*/, "");
      btn.classList.remove("busy");
      btn.removeAttribute("disabled");
      btn.removeAttribute("aria-busy");
    }
  };

  const getJSON = async (url) => {
    const r = await fetch(url, { credentials: "same-origin" });
    if (!r.ok) throw new Error(`${r.status} ${r.statusText}`);
    return r.json();
  };

  const postJSON = async (url, payload) => {
    const r = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "same-origin",
      body: JSON.stringify(payload),
    });
    const data = await r.json().catch(() => ({}));
    if (!r.ok) {
      const err = data?.detail || data?.error || `${r.status} ${r.statusText}`;
      throw new Error(err);
    }
    return data;
  };

  // ---------- DOM refs ----------
  const uploadOut = $("#uploadOut");
  const overwrite = $("#overwrite");
  const csvFile = $("#csvFile");
  const importBtn = $("#importBtn");

  // per-game retrieve (2nd newest JP)
  const mmDate = $("#mmDate");
  const pbDate = $("#pbDate");
  const ilJPDate = $("#ilJPDate");
  const ilM1Date = $("#ilM1Date");
  const ilM2Date = $("#ilM2Date");

  const mmPreview = $("#mmPreview");
  const pbPreview = $("#pbPreview");
  const ilJPPreview = $("#ilJPPreview");
  const ilM1Preview = $("#ilM1Preview");
  const ilM2Preview = $("#ilM2Preview");

  const mmRetrieve = $("#mmRetrieve");
  const pbRetrieve = $("#pbRetrieve");
  const ilJPRetrieve = $("#ilJPRetrieve");
  const ilM1Retrieve = $("#ilM1Retrieve");
  const ilM2Retrieve = $("#ilM2Retrieve");

  // feeds
  const feedMM = $("#feedMM");
  const feedPB = $("#feedPB");
  const feedIL = $("#feedIL");

  // history load 20
  const histMMDate = $("#histMMDate");
  const histPBDate = $("#histPBDate");
  const histILJPDate = $("#histILJPDate");
  const histILM1Date = $("#histILM1Date");
  const histILM2Date = $("#histILM2Date");

  const histMMLoad = $("#histMMLoad");
  const histPBLoad = $("#histPBLoad");
  const histILJPLoad = $("#histILJPLoad");
  const histILM1Load = $("#histILM1Load");
  const histILM2Load = $("#histILM2Load");

  const histMMBlob = $("#histMMBlob");
  const histPBBlob = $("#histPBBlob");
  const histILJPBlob = $("#histILJPBlob");
  const histILM1Blob = $("#histILM1Blob");
  const histILM2Blob = $("#histILM2Blob");

  // run phase 1
  const runPhase1 = $("#runPhase1");
  const phase1Path = $("#phase1Path");
  const phase1Done = $("#phase1Done");
  const phase1Result = $("#phase1Result");

  // results zones
  const mmBatchEl = $("#mmBatch");
  const pbBatchEl = $("#pbBatch");
  const ilBatchEl = $("#ilBatch");

  const mmStatsEl = $("#mmStats");
  const pbStatsEl = $("#pbStats");
  const ilStatsEl = $("#ilStats");

  const mmRowsEl = $("#mmRows");
  const pbRowsEl = $("#pbRows");
  const ilRowsEl = $("#ilRows");

  const mmCounts = $("#mmCounts");
  const pbCounts = $("#pbCounts");
  const ilCounts = $("#ilCounts");

  // ---------- upload ----------
  importBtn?.addEventListener("click", async () => {
    const file = csvFile?.files?.[0];
    if (!file) return toast("Choose a CSV file first.", "warn");
    const fd = new FormData();
    fd.append("file", file);
    fd.append("overwrite", overwrite?.checked ? "true" : "false");
    buttonBusy(importBtn, true, "Importing…");
    try {
      const r = await fetch("/store/import_csv", {
        method: "POST",
        body: fd,
        credentials: "same-origin",
      });
      const data = await r.json();
      setJSON(uploadOut, data);
      if (data.ok) toast("CSV imported.", "ok");
      else toast(data.detail || data.error || "Import failed", "error", 3200);
    } catch (e) {
      setJSON(uploadOut, { ok: false, error: String(e) });
      toast(String(e), "error", 3200);
    } finally {
      buttonBusy(importBtn, false);
    }
  });

  // ---------- retrieve 2nd newest (per game) ----------
  const doRetrieve = async (btn, game, dateStr, previewEl, tier = "") => {
    if (!dateStr) return toast("Enter a date (MM/DD/YYYY).", "warn");
    const params = new URLSearchParams({ game, date: dateStr });
    if (tier) params.set("tier", tier);
    buttonBusy(btn, true, "Retrieving…");
    try {
      const data = await getJSON(`/store/get_by_date?${params.toString()}`);
      if (!data?.ok) throw new Error(data?.detail || data?.error || "Retrieve failed");
      // Expect row = [[mains..], bonus] or [[mains..], null] for IL
      previewEl.value = JSON.stringify(data.row, null, 0);
      toast(`${game}${tier ? " " + tier : ""} retrieved.`, "ok");
    } catch (e) {
      previewEl.value = "";
      toast(String(e), "error", 3200);
    } finally {
      buttonBusy(btn, false);
    }
  };

  mmRetrieve?.addEventListener("click", () =>
    doRetrieve(mmRetrieve, "MM", mmDate.value.trim(), mmPreview)
  );
  pbRetrieve?.addEventListener("click", () =>
    doRetrieve(pbRetrieve, "PB", pbDate.value.trim(), pbPreview)
  );
  ilJPRetrieve?.addEventListener("click", () =>
    doRetrieve(ilJPRetrieve, "IL", ilJPDate.value.trim(), ilJPPreview, "JP")
  );
  ilM1Retrieve?.addEventListener("click", () =>
    doRetrieve(ilM1Retrieve, "IL", ilM1Date.value.trim(), ilM1Preview, "M1")
  );
  ilM2Retrieve?.addEventListener("click", () =>
    doRetrieve(ilM2Retrieve, "IL", ilM2Date.value.trim(), ilM2Preview, "M2")
  );

  // ---------- history load 20 ----------
  const formatRow = (r) => {
    // r: {"date":"MM/DD/YYYY","n":[...], "bonus":int|null} (store is flexible)
    const d = r.date || r.draw_date || "";
    const dt = d ? new Date(d) : null;
    const mmddyy = dt
      ? `${String(dt.getMonth() + 1).padStart(2, "0")}-${String(dt.getDate()).padStart(2, "0")}-${String(dt.getFullYear()).slice(-2)}`
      : (r.mmddyy || d);
    const n = r.n || r.mains || [];
    const main = Array.isArray(n) ? n.map((x) => String(x).padStart(2, "0")).join("-") : n;
    const b = (r.bonus ?? r.mb ?? r.pb ?? null);
    return b == null ? `${mmddyy}  ${main}` : `${mmddyy}  ${main}  ${String(b).padStart(2, "0")}`;
  };

  const doLoad20 = async (btn, game, startDate, blobEl, tier = "") => {
    if (!startDate) return toast("Enter a start date.", "warn");
    const params = new URLSearchParams({ game, from: startDate, limit: "20" });
    if (tier) params.set("tier", tier);
    buttonBusy(btn, true, "Loading…");
    try {
      const data = await getJSON(`/store/get_history?${params.toString()}`);
      let txt = data?.blob;
      if (!txt) {
        const rows = data?.rows || [];
        txt = rows.map(formatRow).join("\n");
      }
      blobEl.value = txt || "";
      toast(`Loaded ${game}${tier ? " " + tier : ""} history.`, "ok");
    } catch (e) {
      blobEl.value = "";
      toast(String(e), "error", 3200);
    } finally {
      buttonBusy(btn, false);
    }
  };

  histMMLoad?.addEventListener("click", () =>
    doLoad20(histMMLoad, "MM", histMMDate.value.trim(), histMMBlob)
  );
  histPBLoad?.addEventListener("click", () =>
    doLoad20(histPBLoad, "PB", histPBDate.value.trim(), histPBBlob)
  );
  histILJPLoad?.addEventListener("click", () =>
    doLoad20(histILJPLoad, "IL", histILJPDate.value.trim(), histILJPBlob, "JP")
  );
  histILM1Load?.addEventListener("click", () =>
    doLoad20(histILM1Load, "IL", histILM1Date.value.trim(), histILM1Blob, "M1")
  );
  histILM2Load?.addEventListener("click", () =>
    doLoad20(histILM2Load, "IL", histILM2Date.value.trim(), histILM2Blob, "M2")
  );

  // ---------- Phase 1 renderers ----------
  const clearResults = () => {
    [mmBatchEl, pbBatchEl, ilBatchEl].forEach((ol) => (ol.innerHTML = ""));
    [mmStatsEl, pbStatsEl, ilStatsEl].forEach((el) => (el.innerHTML = ""));
    [mmRowsEl, pbRowsEl, ilRowsEl].forEach((el) => (el.textContent = ""));
    [mmCounts, pbCounts, ilCounts].forEach((el) => (el.textContent = ""));
  };

  const renderBatchList = (ol, list) => {
    ol.innerHTML = "";
    (list || []).forEach((line) => {
      const li = document.createElement("li");
      li.textContent = line;
      ol.appendChild(li);
    });
  };

  const chips = (statsObj, order) => {
    const frag = document.createDocumentFragment();
    (order || Object.keys(statsObj || {})).forEach((k) => {
      const v = statsObj?.[k] ?? 0;
      const span = document.createElement("span");
      span.className = "chip";
      span.textContent = `${k}: ${v}`;
      frag.appendChild(span);
    });
    return frag;
  };

  const rowsText = (rowsObj, order) => {
    const parts = [];
    (order || Object.keys(rowsObj || {})).forEach((k) => {
      const arr = rowsObj?.[k] || [];
      parts.push(`${k}: ${arr.join(", ") || "—"}`);
    });
    return parts.join("\n");
  };

  const renderGame = (batchEl, statsEl, rowsEl, countsEl, batch, hits, order) => {
    renderBatchList(batchEl, batch);
    statsEl.innerHTML = "";
    const counts = hits?.counts || {};
    statsEl.appendChild(chips(counts, order));
    rowsEl.textContent = rowsText(hits?.rows || {}, order);
    // small total helper
    const total = Object.values(counts).reduce((a, b) => a + (b || 0), 0);
    countsEl.textContent = total ? `hits total: ${total}` : "";
  };

  // ---------- Run Phase 1 ----------
  runPhase1?.addEventListener("click", async () => {
    clearResults();
    phase1Done.style.display = "none";
    phase1Path.value = "";
    setJSON(phase1Result, {});

    // Build payload for backend
    const payload = {
      phase: "phase1",
      // latest 2nd-newest draws (strings)
      LATEST_MM: mmPreview.value.trim(),
      LATEST_PB: pbPreview.value.trim(),
      LATEST_IL_JP: ilJPPreview.value.trim(),
      LATEST_IL_M1: ilM1Preview.value.trim(),
      LATEST_IL_M2: ilM2Preview.value.trim(),

      // feeds
      FEED_MM: feedMM.value,
      FEED_PB: feedPB.value,
      FEED_IL: feedIL.value,

      // histories (top-down, newest-first)
      HIST_MM_BLOB: histMMBlob.value,
      HIST_PB_BLOB: histPBBlob.value,
      HIST_IL_JP_BLOB: histILJPBlob.value,
      HIST_IL_M1_BLOB: histILM1Blob.value,
      HIST_IL_M2_BLOB: histILM2Blob.value,

      // force new randomness each click so batches differ
      seed: Math.random().toString(36).slice(2),
    };

    // quick front validation notes for most common “no output” cases
    if (!payload.LATEST_MM || !payload.LATEST_PB) {
      toast("Tip: retrieve MM and PB (left column) before running Phase 1.", "warn", 2600);
    }
    if (!payload.HIST_MM_BLOB || !payload.HIST_PB_BLOB) {
      toast("Tip: load 20 rows for MM/PB history (right column).", "warn", 2600);
    }

    buttonBusy(runPhase1, true, "Running Phase 1…");
    try {
      const res = await postJSON("/run_json", payload);
      setJSON(phase1Result, res);

      if (!res?.ok) {
        toast(res?.detail || res?.error || "Phase 1 failed", "error", 3200);
        return;
      }

      // The backend echoes structured fields inside res.echo
      const E = res.echo || {};

      // Render MM
      renderGame(
        mmBatchEl,
        mmStatsEl,
        mmRowsEl,
        mmCounts,
        E.BATCH_MM || [],
        E.HITS_MM || { counts: {}, rows: {} },
        ["3", "3+B", "4", "4+B", "5", "5+B"]
      );

      // Render PB
      renderGame(
        pbBatchEl,
        pbStatsEl,
        pbRowsEl,
        pbCounts,
        E.BATCH_PB || [],
        E.HITS_PB || { counts: {}, rows: {} },
        ["3", "3+B", "4", "4+B", "5", "5+B"]
      );

      // Render IL (aggregate JP/M1/M2 with label chips)
      // If your backend already aggregates into HITS_IL_* and BATCH_IL, we show those.
      // BATCH_IL should be 50 rows of “A-B-C-D-E-F” style.
      renderGame(
        ilBatchEl,
        ilStatsEl,
        ilRowsEl,
        ilCounts,
        E.BATCH_IL || [],
        {
          counts: {
            "JP 3:": E?.HITS_IL_JP?.counts?.["3"] || 0,
            "JP 4:": E?.HITS_IL_JP?.counts?.["4"] || 0,
            "JP 5:": E?.HITS_IL_JP?.counts?.["5"] || 0,
            "JP 6:": E?.HITS_IL_JP?.counts?.["6"] || 0,
            "M1 3:": E?.HITS_IL_M1?.counts?.["3"] || 0,
            "M1 4:": E?.HITS_IL_M1?.counts?.["4"] || 0,
            "M1 5:": E?.HITS_IL_M1?.counts?.["5"] || 0,
            "M1 6:": E?.HITS_IL_M1?.counts?.["6"] || 0,
            "M2 3:": E?.HITS_IL_M2?.counts?.["3"] || 0,
            "M2 4:": E?.HITS_IL_M2?.counts?.["4"] || 0,
            "M2 5:": E?.HITS_IL_M2?.counts?.["5"] || 0,
            "M2 6:": E?.HITS_IL_M2?.counts?.["6"] || 0,
          },
          rows: {
            "JP 3": (E?.HITS_IL_JP?.rows?.["3"] || []),
            "JP 4": (E?.HITS_IL_JP?.rows?.["4"] || []),
            "JP 5": (E?.HITS_IL_JP?.rows?.["5"] || []),
            "JP 6": (E?.HITS_IL_JP?.rows?.["6"] || []),
            "M1 3": (E?.HITS_IL_M1?.rows?.["3"] || []),
            "M1 4": (E?.HITS_IL_M1?.rows?.["4"] || []),
            "M1 5": (E?.HITS_IL_M1?.rows?.["5"] || []),
            "M1 6": (E?.HITS_IL_M1?.rows?.["6"] || []),
            "M2 3": (E?.HITS_IL_M2?.rows?.["3"] || []),
            "M2 4": (E?.HITS_IL_M2?.rows?.["4"] || []),
            "M2 5": (E?.HITS_IL_M2?.rows?.["5"] || []),
            "M2 6": (E?.HITS_IL_M2?.rows?.["6"] || []),
          },
        },
        [
          "JP 3:", "JP 4:", "JP 5:", "JP 6:",
          "M1 3:", "M1 4:", "M1 5:", "M1 6:",
          "M2 3:", "M2 4:", "M2 5:", "M2 6:",
        ]
      );

      // saved path & “Done” pill
      phase1Path.value = res.saved_path || "";
      phase1Done.style.display = "inline-block";
      toast("Phase 1 complete.", "ok");
    } catch (e) {
      setJSON(phase1Result, { ok: false, error: String(e) });
      toast(String(e), "error", 3600);
    } finally {
      buttonBusy(runPhase1, false);
    }
  });

  // ---------- small cue on button press (visual) ----------
  j(".btn").forEach((b) => {
    b.addEventListener("mousedown", () => b.classList.add("pressed"));
    ["mouseleave", "mouseup", "blur"].forEach((ev) =>
      b.addEventListener(ev, () => b.classList.remove("pressed"))
    );
  });
})();
