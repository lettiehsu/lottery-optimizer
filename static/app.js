// static/app.js — complete wiring for CSV import + Phase 1 (load, history, run) + hooks for Phase 2/3
(function () {
  const $ = (id) => document.getElementById(id);
  const setText = (id, v) => { const el = $(id); if (el) el.textContent = v; };
  const setVal = (id, v) => { const el = $(id); if (el) el.value = v; };
  const getVal = (id) => { const el = $(id); return el ? el.value.trim() : ""; };
  const on = (id, ev, fn) => { const el = $(id); if (el) el.addEventListener(ev, fn); };

  // ---------- HTTP helpers ----------
  async function getJSON(url) {
    const r = await fetch(url, { credentials: "same-origin" });
    if (!r.ok) throw new Error(`${r.status} ${r.statusText}`);
    return r.json();
  }
  async function postForm(url, fields) {
    const fd = new FormData();
    Object.entries(fields).forEach(([k, v]) => fd.append(k, v));
    const r = await fetch(url, { method: "POST", body: fd, credentials: "same-origin" });
    if (!r.ok) throw new Error(`${r.status} ${r.statusText}`);
    return r.json();
  }

  // ---------- CSV upload ----------
  on("upload_csv", "change", () => {
    const f = $("upload_csv").files?.[0];
    if (!f) { setText("upload_selected", "—"); return; }
    setText("upload_selected", `Selected: ${f.name} (${f.size.toLocaleString()} bytes)`);
  });

  on("upload_btn", "click", async () => {
    const file = $("upload_csv").files?.[0];
    if (!file) { $("upload_result").textContent = "No file chosen."; return; }
    $("upload_result").textContent = "Uploading...";
    const fd = new FormData();
    fd.append("csv", file);
    fd.append("overwrite", $("upload_over").checked ? "1" : "0");
    try {
      const r = await fetch("/import_csv", { method: "POST", body: fd, credentials: "same-origin" });
      const j = await r.json();
      $("upload_result").textContent = JSON.stringify(j, null, 2);
    } catch (e) {
      $("upload_result").textContent = `Upload failed: ${e}`;
    }
  });

  // ---------- Format helpers ----------
  function asLatestTuple(d) {
    // d: {mains:[…], bonus:<int|null>}
    const mains = Array.isArray(d.mains) ? d.mains : [];
    const b = (d.bonus === null || d.bonus === undefined) ? "null" : String(d.bonus);
    return `[${JSON.stringify(mains)}, ${b}]`;
  }
  function dateMMDDYYYY(iso) {
    const [y, m, d] = iso.split("-");
    return `${m}/${d}/${y}`;
  }
  function lineFromDraw(one, isIL) {
    // one = {date:"YYYY-MM-DD", mains:[…], bonus:int|null}
    const date = dateMMDDYYYY(one.date);
    const mains = one.mains.join("-");
    const suffix = (one.bonus === null || one.bonus === undefined || isIL) ? "" : ` ${String(one.bonus).padStart(2,"0")}`;
    return `${date}  ${mains}${suffix}`;
  }

  // ---------- Load single NJ by date ----------
  async function loadByDate(game, dateIso, tier) {
    if (!dateIso) throw new Error("Pick a date");
    let url = `/store/get_by_date?game=${encodeURIComponent(game)}&date=${encodeURIComponent(dateIso)}`;
    if (tier) url += `&tier=${encodeURIComponent(tier)}`;
    const j = await getJSON(url);
    return j; // {date,mains,bonus}
  }

  function previewSet(id, latestTuple) {
    const el = $(id);
    if (el) el.textContent = latestTuple;
  }

  async function handleLoadNJ(kind) {
    // kind: 'MM' | 'PB' | 'IL_JP' | 'IL_M1' | 'IL_M2'
    try {
      let game = "MM", tier = null, dateId = "mm_date", targetPreview = "mm_preview";
      if (kind === "PB") { game = "PB"; dateId = "pb_date"; targetPreview = "pb_preview"; }
      if (kind === "IL_JP") { game = "IL"; tier = "JP"; dateId = "il_jp_date"; targetPreview = "il_jp_preview"; }
      if (kind === "IL_M1") { game = "IL"; tier = "M1"; dateId = "il_m1_date"; targetPreview = "il_m1_preview"; }
      if (kind === "IL_M2") { game = "IL"; tier = "M2"; dateId = "il_m2_date"; targetPreview = "il_m2_preview"; }

      const dateIso = $(dateId).value;
      const draw = await loadByDate(game, dateIso, tier);
      const latest = asLatestTuple(draw);
      previewSet(targetPreview, latest);
    } catch (e) {
      alert(`Load failed: ${e.message || e}`);
    }
  }

  // Hook “Load” buttons for NJ
  on("mm_load", "click", () => handleLoadNJ("MM"));
  on("pb_load", "click", () => handleLoadNJ("PB"));
  on("iljp_load", "click", () => handleLoadNJ("IL_JP"));
  on("ilm1_load", "click", () => handleLoadNJ("IL_M1"));
  on("ilm2_load", "click", () => handleLoadNJ("IL_M2"));

  // One-shot “Load all”
  on("load_all", "click", async () => {
    await Promise.allSettled([
      handleLoadNJ("MM"),
      handleLoadNJ("PB"),
      handleLoadNJ("IL_JP"),
      handleLoadNJ("IL_M1"),
      handleLoadNJ("IL_M2"),
    ]);
  });

  // ---------- History “Load 20” ----------
  async function load20(game, dateId, outId, tier) {
    const iso = $(dateId).value;
    if (!iso) { alert("Pick a date first."); return; }
    let url = `/store/get_history?game=${encodeURIComponent(game)}&date=${encodeURIComponent(iso)}&limit=20`;
    if (tier) url += `&tier=${encodeURIComponent(tier)}`;
    try {
      const arr = await getJSON(url); // [{date,mains,bonus}, …] newest->older
      const isIL = (game === "IL");
      const lines = arr.map(x => lineFromDraw(x, isIL)).join("\n");
      setVal(outId, lines);
    } catch (e) {
      alert(`Load 20 failed: ${e.message || e}`);
    }
  }
  on("mm_hist_load20", "click", () => load20("MM", "mm_hist_date", "HIST_MM_BLOB"));
  on("pb_hist_load20", "click", () => load20("PB", "pb_hist_date", "HIST_PB_BLOB"));
  on("il_jp_hist_load20", "click", () => load20("IL", "il_jp_hist_date", "HIST_IL_JP_BLOB", "JP"));
  on("il_m1_hist_load20", "click", () => load20("IL", "il_m1_hist_date", "HIST_IL_M1_BLOB", "M1"));
  on("il_m2_hist_load20", "click", () => load20("IL", "il_m2_hist_date", "HIST_IL_M2_BLOB", "M2"));

  // ---------- Phase 1 run ----------
  function getLatestOrWarn(previewId, name) {
    const t = getVal(previewId);
    if (!t) throw new Error(`Pick ${name} date and click Load`);
    return t;
    // t is string like "[[mains], bonus]"
  }

  on("run_p1", "click", async () => {
    try {
      const LATEST_MM   = getLatestOrWarn("mm_preview", "MM");
      const LATEST_PB   = getLatestOrWarn("pb_preview", "PB");
      const LATEST_IL_JP= getLatestOrWarn("il_jp_preview","IL JP");
      const LATEST_IL_M1= getLatestOrWarn("il_m1_preview","IL M1");
      const LATEST_IL_M2= getLatestOrWarn("il_m2_preview","IL M2");

      const FEED_MM = getVal("FEED_MM");
      const FEED_PB = getVal("FEED_PB");
      const FEED_IL = getVal("FEED_IL");

      const HIST_MM_BLOB = getVal("HIST_MM_BLOB");
      const HIST_PB_BLOB = getVal("HIST_PB_BLOB");
      // Backend expects HIST_IL_BLOB (we'll send JP block here)
      const HIST_IL_BLOB = getVal("HIST_IL_JP_BLOB");

      const payload = {
        LATEST_MM, LATEST_PB, LATEST_IL_JP, LATEST_IL_M1, LATEST_IL_M2,
        FEED_MM, FEED_PB, FEED_IL,
        HIST_MM_BLOB, HIST_PB_BLOB, HIST_IL_BLOB
      };

      const res = await postForm("/run_json", payload);
      if (!res || !res.ok) throw new Error(res?.error || "Phase 1 failed");

      // Show saved path + push into Phase-2 input
      setText("p1_path", res.saved_path || "—");
      if ($("p2_in_path")) setVal("p2_in_path", res.saved_path || "");

      alert("Phase 1 complete.");
    } catch (e) {
      alert(`Phase 1 failed: ${e.message || e}`);
    }
  });

  // Copy Phase-1 saved path button
  on("copy_p1", "click", () => {
    const t = $("p1_path")?.textContent || "";
    if (!t || t === "—") return;
    navigator.clipboard.writeText(t).then(() => {
      alert("Phase-1 path copied.");
    });
  });

  // Save current NJ → History
  on("save_nj_to_hist", "click", async () => {
    try {
      // Reuse previews and dates; backend endpoint assumed: /store/save_nj_batch
      const body = {
        mm_date: $("mm_date").value, pb_date: $("pb_date").value,
        il_jp_date: $("il_jp_date").value, il_m1_date: $("il_m1_date").value, il_m2_date: $("il_m2_date").value,
        LATEST_MM: getVal("mm_preview"),
        LATEST_PB: getVal("pb_preview"),
        LATEST_IL_JP: getVal("il_jp_preview"),
        LATEST_IL_M1: getVal("il_m1_preview"),
        LATEST_IL_M2: getVal("il_m2_preview"),
      };
      const res = await postForm("/store/save_nj_batch", body);
      alert(res?.ok ? "Saved NJ → history." : `Save failed: ${JSON.stringify(res)}`);
    } catch (e) {
      alert(`Save failed: ${e.message || e}`);
    }
  });

  // ---------- Phase 2 hooks ----------
  on("run_p2", "click", async () => {
    const p = getVal("p2_in_path");
    if (!p) return alert("Provide Phase-1 state path first.");
    try {
      const res = await postForm("/phase2_json", { saved_path: p });
      if (!res || !res.ok) throw new Error(res?.error || "Phase 2 failed");

      // buy lists
      function renderList(id, arr, isIL) {
        const ol = $(id); if (!ol) return;
        ol.innerHTML = "";
        (arr || []).forEach((t) => {
          const li = document.createElement("li");
          if (isIL) {
            li.textContent = `[${t.mains.join(", ")}]`;
          } else {
            li.textContent = `[${t.mains.join(", ")}],  ${t.bonus}`;
          }
          ol.appendChild(li);
        });
      }
      renderList("p2_mm_list", res.buy_lists?.MM || []);
      renderList("p2_pb_list", res.buy_lists?.PB || []);
      renderList("p2_il_list", res.buy_lists?.IL || [], true);

      // aggregated hits tables
      function renderAgg(tableId, obj) {
        const tb = $(tableId)?.querySelector("tbody"); if (!tb) return;
        tb.innerHTML = "";
        const order = ["3","3B","4","4B","5","5B","6"]; // 6 for IL tables
        order.forEach(k=>{
          if (obj && k in obj) {
            const tr = document.createElement("tr");
            const td1 = document.createElement("td"); td1.textContent = k;
            const td2 = document.createElement("td"); td2.textContent = (obj[k]?.length || 0).toString();
            const td3 = document.createElement("td"); td3.textContent = (obj[k]||[]).slice(0,8).join(", ");
            tr.append(td1,td2,td3);
            tb.appendChild(tr);
          }
        });
      }
      renderAgg("p2_mm_hits", res.agg_hits?.MM);
      renderAgg("p2_pb_hits", res.agg_hits?.PB);
      renderAgg("p2_il_jp_hits", res.agg_hits?.IL?.JP);
      renderAgg("p2_il_m1_hits", res.agg_hits?.IL?.M1);
      renderAgg("p2_il_m2_hits", res.agg_hits?.IL?.M2);

      setText("p2_saved_path", res.saved_path || "—");
      if ($("p3_in_path")) setVal("p3_in_path", res.saved_path || "");
      alert("Phase 2 complete.");
    } catch (e) {
      alert(`Phase 2 failed: ${e.message || e}`);
    }
  });

  on("copy_p2", "click", () => {
    const t = $("p2_saved_path")?.textContent || "";
    if (!t || t === "—") return;
    navigator.clipboard.writeText(t).then(()=>alert("Phase-2 path copied."));
  });

  // ---------- Phase 3: NWJ loaders + confirm ----------
  async function handleLoadNWJ(kind) {
    // same as NJ, but into NWJ previews
    let game = "MM", tier = null, dateId = "nwj_mm_date", target = "nwj_mm_preview";
    if (kind === "PB") { game = "PB"; dateId = "nwj_pb_date"; target = "nwj_pb_preview"; }
    if (kind === "IL_JP") { game = "IL"; tier = "JP"; dateId = "nwj_il_jp_date"; target = "nwj_il_jp_preview"; }
    if (kind === "IL_M1") { game = "IL"; tier = "M1"; dateId = "nwj_il_m1_date"; target = "nwj_il_m1_preview"; }
    if (kind === "IL_M2") { game = "IL"; tier = "M2"; dateId = "nwj_il_m2_date"; target = "nwj_il_m2_preview"; }
    const dateIso = $(dateId)?.value;
    const d = await loadByDate(game, dateIso, tier);
    previewSet(target, asLatestTuple(d));
  }
  on("nwj_mm_load","click",()=>handleLoadNWJ("MM"));
  on("nwj_pb_load","click",()=>handleLoadNWJ("PB"));
  on("nwj_iljp_load","click",()=>handleLoadNWJ("IL_JP"));
  on("nwj_ilm1_load","click",()=>handleLoadNWJ("IL_M1"));
  on("nwj_ilm2_load","click",()=>handleLoadNWJ("IL_M2"));

  on("run_p3","click", async ()=>{
    const saved_path = getVal("p3_in_path");
    if (!saved_path) return alert("Provide Phase-2 state path first.");
    const LATEST_MM = getVal("nwj_mm_preview");
    const LATEST_PB = getVal("nwj_pb_preview");
    const LATEST_IL_JP = getVal("nwj_il_jp_preview");
    const LATEST_IL_M1 = getVal("nwj_il_m1_preview");
    const LATEST_IL_M2 = getVal("nwj_il_m2_preview");
    try{
      const res = await postForm("/confirm_json", {
        saved_path, LATEST_MM, LATEST_PB, LATEST_IL_JP, LATEST_IL_M1, LATEST_IL_M2
      });
      if (!res?.ok) throw new Error(res?.error || "Confirm failed");

      // Render confirmation hits (simple: show positions)
      function fillConfirm(tableId, obj){
        const tb = $(tableId)?.querySelector("tbody"); if (!tb) return;
        tb.innerHTML = "";
        const types = ["3","3B","4","4B","5","5B","6"];
        types.forEach(t=>{
          if (obj && t in obj){
            const tr = document.createElement("tr");
            const td1=document.createElement("td"); td1.textContent=t;
            const td2=document.createElement("td"); td2.textContent=(obj[t]||[]).join(", ");
            tr.append(td1,td2); tb.appendChild(tr);
          }
        });
      }
      fillConfirm("p3_mm_hits", res.hits?.MM);
      fillConfirm("p3_pb_hits", res.hits?.PB);
      fillConfirm("p3_il_hits", res.hits?.IL); // combined display

      alert("Phase 3 complete.");
    }catch(e){
      alert(`Confirm failed: ${e.message||e}`);
    }
  });

  // ---------- Final: surface Phase 2/3 if HTML present ----------
  // (No-op here; they’re part of the template. If you still don't see them, hard refresh.)
})();
