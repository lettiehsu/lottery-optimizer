<script>
// ---------- tiny DOM helpers ----------
const $ = (id) => document.getElementById(id);
const on = (id, evt, fn) => $(id) && $(id).addEventListener(evt, fn);

// ---------- Upload master CSV ----------
on("upload_btn", "click", async () => {
  const file = $("upload_csv").files?.[0];
  if (!file) { $("upload_result").textContent = "No file chosen."; return; }
  $("upload_result").textContent = "Uploading...";

  const fd = new FormData();
  fd.append("csv", file);
  fd.append("overwrite", $("upload_over")?.checked ? "1" : "0");

  try {
    const r = await fetch("/store/import_csv", {
      method: "POST",
      body: fd,
      credentials: "same-origin",
    });
    const text = await r.text();            // read as text first
    try {
      const j = JSON.parse(text);           // try JSON if possible
      $("upload_result").textContent = JSON.stringify(j, null, 2);
    } catch {
      $("upload_result").textContent = text; // show HTML/text error for visibility
    }
  } catch (e) {
    $("upload_result").textContent = `Upload failed: ${e}`;
  }
});

// ---------- (optional) examples for Phase-1 loaders ----------
// If you have date inputs and "Load 20" buttons, keep using your existing
// routes (/store/get_by_date and /store/get_history). The below shows the pattern.

async function loadHistory(game, fromDateISO, textareaId) {
  try {
    const r = await fetch(`/store/get_history?game=${encodeURIComponent(game)}&from=${encodeURIComponent(fromDateISO)}&limit=20`);
    const j = await r.json();
    $(textareaId).value = j.blob || "";
  } catch (e) {
    $(textareaId).value = `Error: ${e}`;
  }
}

// Example wiring:
// on("btn_mm_load20", "click", () => loadHistory("MM", $("mm_hist_date").value, "HIST_MM_BLOB"));
// on("btn_pb_load20", "click", () => loadHistory("PB", $("pb_hist_date").value, "HIST_PB_BLOB"));
// on("btn_iljp_load20", "click", () => loadHistory("IL_JP", $("il_jp_hist_date").value, "HIST_IL_JP_BLOB"));
// on("btn_ilm1_load20", "click", () => loadHistory("IL_M1", $("il_m1_hist_date").value, "HIST_IL_M1_BLOB"));
// on("btn_ilm2_load20", "click", () => loadHistory("IL_M2", $("il_m2_hist_date").value, "HIST_IL_M2_BLOB"));
</script>
