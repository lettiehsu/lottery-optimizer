// static/app.js — autofill for MM, PB, IL (JP/M1/M2)

async function fetchJSON(url) {
  const res = await fetch(url, { cache: "no-store" });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return await res.json();
}

function fmtPair(pair) {
  // pair: [[mains...], bonusOrNull] -> "[[a,b,c,...], x]" with null spelled null
  if (!pair) return "";
  const mains = Array.isArray(pair[0]) ? pair[0] : [];
  const bonus = pair[1] === null || pair[1] === undefined ? "null" : String(pair[1]);
  return `[${JSON.stringify(mains)}, ${bonus}]`;
}

function setVal(selector, value) {
  const el = document.querySelector(selector);
  if (el) el.value = value;
}

function setHint(selector, ok) {
  const el = document.querySelector(selector);
  if (!el) return;
  el.style.opacity = ok ? "1" : "0.55";
  el.title = ok ? "" : "No data yet — add history or save a few draws";
}

async function autofillPhase1() {
  try {
    // n=3 → 3rd newest (training/NJ in Phase 1)
    const data = await fetchJSON("/autofill?n=3");
    // data.like: { MM:[[...],b], PB:[[...],b], IL:{ JP:[[...],null], M1:[[...],null], M2:[[...],null] } }
    const mm = data?.MM ?? null;
    const pb = data?.PB ?? null;
    const il = data?.IL ?? {};

    setVal("#mm_latest", fmtPair(mm));
    setHint("#mm_latest", !!mm);

    setVal("#pb_latest", fmtPair(pb));
    setHint("#pb_latest", !!pb);

    setVal("#il_jp_latest", fmtPair(il?.JP ?? null));
    setHint("#il_jp_latest", !!il?.JP);

    setVal("#il_m1_latest", fmtPair(il?.M1 ?? null));
    setHint("#il_m1_latest", !!il?.M1);

    setVal("#il_m2_latest", fmtPair(il?.M2 ?? null));
    setHint("#il_m2_latest", !!il?.M2);
  } catch (e) {
    alert("Autofill (Phase 1) failed: " + e.message);
  }
}

async function autofillPhase2() {
  // if you later want a dedicated autofill for Phase 2, wire it here
}

async function autofillPhase3() {
  try {
    // n=1 → newest draw (NWJ for confirmation)
    const data = await fetchJSON("/autofill?n=1");
    const mm = data?.MM ?? null;
    const pb = data?.PB ?? null;
    const il = data?.IL ?? {};

    // Build full NWJ JSON for the Phase-3 textarea
    const nwj = {
      "LATEST_MM": mm ?? null,
      "LATEST_PB": pb ?? null,
      "LATEST_IL_JP": il?.JP ?? null,
      "LATEST_IL_M1": il?.M1 ?? null,
      "LATEST_IL_M2": il?.M2 ?? null
    };

    // JSON requires 'null', not 'None'
    setVal("#nwj_json", JSON.stringify(nwj));
  } catch (e) {
    alert("Autofill (Phase 3) failed: " + e.message);
  }
}

// Expose to buttons
window.autofillPhase1 = autofillPhase1;
window.autofillPhase2 = autofillPhase2;
window.autofillPhase3 = autofillPhase3;

// Optional: auto-wire buttons if they exist
document.addEventListener("DOMContentLoaded", () => {
  const b1 = document.querySelector("#btn_autofill_p1");
  const b3 = document.querySelector("#btn_autofill_p3");
  if (b1) b1.addEventListener("click", autofillPhase1);
  if (b3) b3.addEventListener("click", autofillPhase3);
});
