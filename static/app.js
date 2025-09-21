// static/app.js (v5) — robust Phase-1/3 Autofill with endpoint fallbacks + debug

(function () {
  const $ = (sel) => document.querySelector(sel);
  const debugEl = () => document.getElementById("autofill_debug");
  const log = (...a) => {
    console.log("[autofill]", ...a);
    if (debugEl()) {
      debugEl().textContent += a.map(x => (typeof x === "string" ? x : JSON.stringify(x))).join(" ") + "\n";
    }
  };

  async function tryJSON(urls) {
    for (const u of urls) {
      try {
        const r = await fetch(u, { cache: "no-store" });
        if (!r.ok) { log(`HTTP ${r.status} for ${u}`); continue; }
        const j = await r.json();
        log("Fetched from", u, "→", j);
        return j;
      } catch (e) {
        log("Fetch failed:", u, String(e));
      }
    }
    throw new Error("All autofill endpoints failed.");
  }

  function fmtPair(pair) {
    if (!pair) return "";
    const mains = Array.isArray(pair[0]) ? pair[0] : [];
    const bonusVal = (pair[1] === null || pair[1] === undefined) ? "null" : String(pair[1]);
    return `[${JSON.stringify(mains)}, ${bonusVal}]`;
  }

  function setVal(id, value) {
    const el = document.getElementById(id);
    if (!el) { log("Missing element id:", id); return; }
    el.value = value || "";
    el.style.opacity = value ? "1" : "0.6";
    el.title = value ? "" : "No data found (check history / endpoints)";
  }

  async function autofillPhase1() {
    try {
      if (debugEl()) debugEl().textContent = "(starting Phase 1 autofill…)\n";
      const urls = ["/autofill?n=3", "/store/autofill?n=3", "/api/autofill?n=3"];
      const data = await tryJSON(urls);

      // Expecting { MM: [[mains],bonus], PB: [[mains],bonus], IL: {JP:[[]],M1:[[]],M2:[[]]} }
      const mm = data?.MM ?? null;
      const pb = data?.PB ?? null;
      const il = data?.IL ?? {};

      setVal("mm_latest", fmtPair(mm));
      setVal("pb_latest", fmtPair(pb));
      setVal("il_jp_latest", fmtPair(il?.JP ?? null));
      setVal("il_m1_latest", fmtPair(il?.M1 ?? null));
      setVal("il_m2_latest", fmtPair(il?.M2 ?? null));

      log("Phase 1 filled:", {
        mm: fmtPair(mm),
        pb: fmtPair(pb),
        il_jp: fmtPair(il?.JP ?? null),
        il_m1: fmtPair(il?.M1 ?? null),
        il_m2: fmtPair(il?.M2 ?? null)
      });
    } catch (e) {
      log("Autofill Phase 1 error:", String(e));
      alert("Autofill (Phase 1) failed: " + e.message);
    }
  }

  async function autofillPhase3() {
    try {
      if (debugEl()) debugEl().textContent = "(starting Phase 3 autofill…)\n";
      const urls = ["/autofill?n=1", "/store/autofill?n=1", "/api/autofill?n=1"];
      const data = await tryJSON(urls);

      const nwj = {
        "LATEST_MM": data?.MM ?? null,
        "LATEST_PB": data?.PB ?? null,
        "LATEST_IL_JP": data?.IL?.JP ?? null,
        "LATEST_IL_M1": data?.IL?.M1 ?? null,
        "LATEST_IL_M2": data?.IL?.M2 ?? null
      };

      const box = document.getElementById("nwj_json");
      if (!box) { log("Missing #nwj_json"); return; }
      box.value = JSON.stringify(nwj);
      box.style.opacity = "1";
      box.title = "";

      log("Phase 3 NWJ filled:", nwj);
    } catch (e) {
      log("Autofill Phase 3 error:", String(e));
      alert("Autofill (Phase 3) failed: " + e.message);
    }
  }

  // expose for onclick fallback
  window.autofillPhase1 = autofillPhase1;
  window.autofillPhase3 = autofillPhase3;

  document.addEventListener("DOMContentLoaded", () => {
    log("app.js v5 loaded; binding buttons…");
    const b1 = document.getElementById("btn_autofill_p1");
    const b3 = document.getElementById("btn_autofill_p3");
    if (b1) b1.addEventListener("click", autofillPhase1);
    if (b3) b3.addEventListener("click", autofillPhase3);

    // quick sanity check
    ["mm_latest","pb_latest","il_jp_latest","il_m1_latest","il_m2_latest","nwj_json"].forEach(id=>{
      if (!document.getElementById(id)) log("Missing expected element:", id);
    });
  });
})();
