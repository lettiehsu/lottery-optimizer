// static/app.js (v4) — robust autofill with logging + cache-busting friendly

(function () {
  const log = (...a) => console.log("[autofill]", ...a);
  const $ = (sel) => document.querySelector(sel);

  async function fetchJSON(url) {
    const res = await fetch(url, { cache: "no-store" });
    if (!res.ok) throw new Error(`HTTP ${res.status} for ${url}`);
    return await res.json();
  }

  function fmtPair(pair) {
    if (!pair) return "";
    const mains = Array.isArray(pair[0]) ? pair[0] : [];
    const bonus = pair[1] === null || pair[1] === undefined ? "null" : String(pair[1]);
    return `[${JSON.stringify(mains)}, ${bonus}]`;
  }

  function setVal(id, value, ok) {
    const el = document.getElementById(id);
    if (!el) {
      log("No element with id:", id);
      return;
    }
    el.value = value || "";
    el.style.opacity = ok ? "1" : "0.55";
    el.title = ok ? "" : "No data yet — add history or import CSV";
  }

  async function autofillPhase1() {
    try {
      log("Requesting /autofill?n=3");
      const data = await fetchJSON("/autofill?n=3");
      log("Phase 1 autofill payload:", data);

      const mm = data?.MM ?? null;
      const pb = data?.PB ?? null;
      const il = data?.IL ?? {};

      setVal("mm_latest", fmtPair(mm), !!mm);
      setVal("pb_latest", fmtPair(pb), !!pb);
      setVal("il_jp_latest", fmtPair(il?.JP ?? null), !!il?.JP);
      setVal("il_m1_latest", fmtPair(il?.M1 ?? null), !!il?.M1);
      setVal("il_m2_latest", fmtPair(il?.M2 ?? null), !!il?.M2);
    } catch (e) {
      console.error(e);
      alert("Autofill (Phase 1) failed: " + e.message);
    }
  }

  async function autofillPhase3() {
    try {
      log("Requesting /autofill?n=1");
      const data = await fetchJSON("/autofill?n=1");
      log("Phase 3 autofill payload:", data);

      const nwj = {
        "LATEST_MM": data?.MM ?? null,
        "LATEST_PB": data?.PB ?? null,
        "LATEST_IL_JP": data?.IL?.JP ?? null,
        "LATEST_IL_M1": data?.IL?.M1 ?? null,
        "LATEST_IL_M2": data?.IL?.M2 ?? null
      };

      const el = document.getElementById("nwj_json");
      if (!el) {
        log("No #nwj_json textarea found");
        return;
      }
      el.value = JSON.stringify(nwj);
      el.style.opacity = "1";
      el.title = "";
    } catch (e) {
      console.error(e);
      alert("Autofill (Phase 3) failed: " + e.message);
    }
  }

  // expose for buttons
  window.autofillPhase1 = autofillPhase1;
  window.autofillPhase3 = autofillPhase3;

  document.addEventListener("DOMContentLoaded", () => {
    log("JS loaded, binding buttons…");
    const b1 = document.getElementById("btn_autofill_p1");
    const b3 = document.getElementById("btn_autofill_p3");
    if (b1) b1.addEventListener("click", autofillPhase1);
    if (b3) b3.addEventListener("click", autofillPhase3);

    // sanity check the elements exist
    ["mm_latest","pb_latest","il_jp_latest","il_m1_latest","il_m2_latest","nwj_json"].forEach(id=>{
      if (!document.getElementById(id)) log("Missing expected element id:", id);
    });
  });
})();
