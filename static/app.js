/* static/app.js — minimal Phase 1 wire-up */

function q(id) { return document.getElementById(id); }
function val(id) { const el = q(id); return el ? el.value.trim() : ""; }

function tryJsonParse(str) {
  // Accept JSON-looking text like [[10,14,34,40,43],5]
  // If not valid JSON, return null so we can show a friendly error
  try {
    return JSON.parse(str);
  } catch {
    return null;
  }
}

function toast(msg, type = "info") {
  const box = q("phase1_msg");
  if (box) {
    box.textContent = msg;
    box.className = `msg ${type}`;
  } else {
    alert(msg);
  }
}

async function runPhase1() {
  // Gather previews: they must be JSON-looking, e.g. [[10,14,34,40,43],5] or [[1,4,5,10,18,49],null]
  const mm = tryJsonParse(val("mm_preview"));
  const pb = tryJsonParse(val("pb_preview"));
  const il_jp = tryJsonParse(val("il_jp_preview"));
  const il_m1 = tryJsonParse(val("il_m1_preview"));
  const il_m2 = tryJsonParse(val("il_m2_preview"));

  const missing = [];
  if (!mm) missing.push("Mega Millions");
  if (!pb) missing.push("Powerball");
  if (!il_jp) missing.push("IL Jackpot");
  if (!il_m1) missing.push("IL Million 1");
  if (!il_m2) missing.push("IL Million 2");
  if (missing.length) {
    toast(`These boxes are empty or not valid JSON: ${missing.join(", ")}.`, "error");
    return;
  }

  // Feeds (plain text is fine)
  const feed_mm = val("feed_mm");
  const feed_pb = val("feed_pb");
  const feed_il = val("feed_il");

  // History blobs (plain text; server understands mm/dd/yyyy lines + rows)
  const hist_mm = val("hist_mm_blob");
  const hist_pb = val("hist_pb_blob");
  const hist_il_jp = val("hist_il_jp_blob");
  const hist_il_m1 = val("hist_il_m1_blob");
  const hist_il_m2 = val("hist_il_m2_blob");

  const payload = {
    // newest jackpot (NJ for Phase 1 training)
    LATEST_MM: mm,            // [[mains], bonus]
    LATEST_PB: pb,            // [[mains], bonus]
    LATEST_IL_JP: il_jp,      // [[mains], null]
    LATEST_IL_M1: il_m1,      // [[mains], null]
    LATEST_IL_M2: il_m2,      // [[mains], null]

    // feeds
    FEED_MM: feed_mm,
    FEED_PB: feed_pb,
    FEED_IL: feed_il,

    // history blobs (top row newest)
    HIST_MM_BLOB: hist_mm,
    HIST_PB_BLOB: hist_pb,
    HIST_IL_JP_BLOB: hist_il_jp,
    HIST_IL_M1_BLOB: hist_il_m1,
    HIST_IL_M2_BLOB: hist_il_m2
  };

  toast("Running Phase 1…");

  let res;
  try {
    res = await fetch("/run_json", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
  } catch (e) {
    toast(`Network error: ${e}`, "error");
    return;
  }

  let data;
  try {
    data = await res.json();
  } catch {
    toast("Server returned non-JSON. Open DevTools → Network → /run_json to see details.", "error");
    return;
  }

  if (!res.ok || data.ok === false) {
    const detail = data && (data.detail || data.error) || "Unknown error";
    toast(`Phase 1 failed: ${detail}`, "error");
    return;
  }

  // Success — show saved path so Phase 2 can auto-fill.
  if (data.saved_path && q("phase1_saved_path")) {
    q("phase1_saved_path").value = data.saved_path;
  }
  toast("Phase 1 finished. Saved path updated.", "success");

  // (Optional) If you have specific fields to render, do it here using 'data'
  // e.g., bands, hit tables, etc. This keeps the first fix focused on wiring.
}

// Hook up the button
document.addEventListener("DOMContentLoaded", () => {
  const btn = q("btn_run_phase1");
  if (btn) btn.addEventListener("click", runPhase1);
});
