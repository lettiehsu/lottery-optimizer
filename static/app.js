(() => {
  const $ = (id) => document.getElementById(id);
  const logEl = $("log");
  const setLog = (obj, isError=false) => {
    logEl.textContent = typeof obj === "string" ? obj : JSON.stringify(obj, null, 2);
    logEl.className = isError ? "mono error" : "mono";
  };

  async function fetchJSON(url, opts={}) {
    try {
      const res = await fetch(url, opts);
      const txt = await res.text();
      let data = null;
      try { data = JSON.parse(txt); } catch { /* not json */ }
      if (!res.ok) {
        // Prefer server JSON error, else status text
        throw new Error(data?.detail || data?.error || `${res.status} ${res.statusText}`);
      }
      // Some old server code returns plain text; normalize to object
      return (data ?? { ok:true, text:txt });
    } catch (e) {
      throw new Error(e.message || String(e));
    }
  }

  // ---------- CSV import ----------
  $("btnImport").addEventListener("click", async () => {
    const f = $("csvFile").files?.[0];
    if (!f) { setLog("Please choose a CSV file.", true); return; }
    const form = new FormData();
    form.append("file", f);
    form.append("overwrite", $("overwrite").checked ? "true" : "false");
    try {
      const j = await fetchJSON("/store/import_csv", { method:"POST", body: form });
      $("importResult").textContent = JSON.stringify(j, null, 2);
    } catch (e) {
      $("importResult").textContent = `Upload failed: ${e.message}`;
    }
  });

  // ---------- Helpers ----------
  const ensureArrayNums = (arr) => Array.isArray(arr) ? arr.map(x => Number(x)) : [];
  const formatLatest = (mains, bonusOrNull) => {
    const a = ensureArrayNums(mains);
    return `[[${a.join(",")}], ${bonusOrNull === null ? "null" : Number(bonusOrNull)}]`;
  };

  async function retrieveByDate(game, date, tier=null) {
    const p = new URLSearchParams();
    p.set("game", game);
    p.set("date", date);
    if (tier) p.set("tier", tier);
    return await fetchJSON(`/store/get_by_date?${p.toString()}`);
  }

  async function loadHistory(game, fromDate, limit=20, tier=null) {
    const p = new URLSearchParams();
    p.set("game", game);
    p.set("date", fromDate);     // server also accepts "from"; we send "date" for consistency
    p.set("limit", String(limit));
    if (tier) p.set("tier", tier);
    return await fetchJSON(`/store/get_history?${p.toString()}`);
  }

  // ---------- Retrieve buttons ----------
  $("btnRetrieveMM").addEventListener("click", async () => {
    const d = $("mmDate").value.trim();
    if (!d) return setLog("Pick a MM date.", true);
    try {
      const j = await retrieveByDate("MM", d);
      $("mmPreview").value = formatLatest(j.mains, j.bonus ?? j.mb ?? null);
    } catch (e) { setLog(`Retrieve failed (MM): ${e.message}`, true); }
  });

  $("btnRetrievePB").addEventListener("click", async () => {
    const d = $("pbDate").value.trim();
    if (!d) return setLog("Pick a PB date.", true);
    try {
      const j = await retrieveByDate("PB", d);
      $("pbPreview").value = formatLatest(j.mains, j.bonus ?? j.pb ?? null);
    } catch (e) { setLog(`Retrieve failed (PB): ${e.message}`, true); }
  });

  $("btnRetrieveILJP").addEventListener("click", async () => {
    const d = $("ilJPDate").value.trim();
    if (!d) return setLog("Pick IL JP date.", true);
    try {
      const j = await retrieveByDate("IL", d, "JP"); // server also accepts game=IL_JP
      $("ilJPPreview").value = formatLatest(j.mains, null);
    } catch (e) { setLog(`Retrieve failed (IL_JP): ${e.message}`, true); }
  });

  $("btnRetrieveILM1").addEventListener("click", async () => {
    const d = $("ilM1Date").value.trim();
    if (!d) return setLog("Pick IL M1 date.", true);
    try {
      const j = await retrieveByDate("IL", d, "M1");
      $("ilM1Preview").value = formatLatest(j.mains, null);
    } catch (e) { setLog(`Retrieve failed (IL_M1): ${e.message}`, true); }
  });

  $("btnRetrieveILM2").addEventListener("click", async () => {
    const d = $("ilM2Date").value.trim();
    if (!d) return setLog("Pick IL M2 date.", true);
    try {
      const j = await retrieveByDate("IL", d, "M2");
      $("ilM2Preview").value = formatLatest(j.mains, null);
    } catch (e) { setLog(`Retrieve failed (IL_M2): ${e.message}`, true); }
  });

  // ---------- Load 20 history ----------
  $("btnLoadMM20").addEventListener("click", async () => {
    const d = $("histMMFrom").value.trim();
    if (!d) return setLog("Pick MM history start date.", true);
    try {
      const j = await loadHistory("MM", d, 20);
      $("histMM").value = j.blob || (j.rows || []).join("\n");
    } catch (e) { setLog(`Load failed (MM): ${e.message}`, true); }
  });

  $("btnLoadPB20").addEventListener("click", async () => {
    const d = $("histPBFrom").value.trim();
    if (!d) return setLog("Pick PB history start date.", true);
    try {
      const j = await loadHistory("PB", d, 20);
      $("histPB").value = j.blob || (j.rows || []).join("\n");
    } catch (e) { setLog(`Load failed (PB): ${e.message}`, true); }
  });

  $("btnLoadILJP20").addEventListener("click", async () => {
    const d = $("histILJPFrom").value.trim();
    if (!d) return setLog("Pick IL JP history start date.", true);
    try {
      const j = await loadHistory("IL", d, 20, "JP");
      $("histILJP").value = j.blob || (j.rows || []).join("\n");
    } catch (e) { setLog(`Load failed (IL_JP): ${e.message}`, true); }
  });

  $("btnLoadILM120").addEventListener("click", async () => {
    const d = $("histILM1From").value.trim();
    if (!d) return setLog("Pick IL M1 history start date.", true);
    try {
      const j = await loadHistory("IL", d, 20, "M1");
      $("histILM1").value = j.blob || (j.rows || []).join("\n");
    } catch (e) { setLog(`Load failed (IL_M1): ${e.message}`, true); }
  });

  $("btnLoadILM220").addEventListener("click", async () => {
    const d = $("histILM2From").value.trim();
    if (!d) return setLog("Pick IL M2 history start date.", true);
    try {
      const j = await loadHistory("IL", d, 20, "M2");
      $("histILM2").value = j.blob || (j.rows || []).join("\n");
    } catch (e) { setLog(`Load failed (IL_M2): ${e.message}`, true); }
  });

  // ---------- Run Phase 1 ----------
  $("btnRunP1").addEventListener("click", async () => {
    const payload = {
      // EXACT names the core expects:
      LATEST_MM: $("mmPreview").value.trim(),
      LATEST_PB: $("pbPreview").value.trim(),
      LATEST_IL_JP: $("ilJPPreview").value.trim(),
      LATEST_IL_M1: $("ilM1Preview").value.trim(),
      LATEST_IL_M2: $("ilM2Preview").value.trim(),
      FEED_MM: $("feedMM").value,
      FEED_PB: $("feedPB").value,
      FEED_IL: $("feedIL").value,
      HIST_MM_BLOB: $("histMM").value,
      HIST_PB_BLOB: $("histPB").value,
      // Join the three IL blobs into one big HIST_IL_BLOB (the core expects a single field)
      HIST_IL_BLOB: [ $("histILJP").value, $("histILM1").value, $("histILM2").value ].filter(Boolean).join("\n")
    };

    // guard the LATEST_* strings — avoids the “must be a string like '[..]…'” error
    for (const k of ["LATEST_MM","LATEST_PB","LATEST_IL_JP","LATEST_IL_M1","LATEST_IL_M2"]) {
      if (!payload[k] || !payload[k].includes("[[")) {
        return setLog(`Missing or malformed ${k}. Click Retrieve for each game first.`, true);
      }
    }

    try {
      const j = await fetchJSON("/run_json", {
        method: "POST",
        headers: { "Content-Type":"application/json" },
        body: JSON.stringify(payload)
      });
      setLog(j);
      if (j?.ok && j?.saved_path) $("p1Path").value = j.saved_path;
    } catch (e) {
      setLog(e.message, true);
    }
  });
})();
