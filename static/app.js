// static/app.js

(function(){
  const $ = (id)=>document.getElementById(id);

  // =============== CSV Upload ===============
  (function wireCsvUpload(){
    const fileEl = $("csv_file");
    const lblEl  = $("csv_selected");
    const outEl  = $("import_out");
    const btn    = $("btn_import");

    if (!fileEl || !btn) return; // page didn't render uploader

    fileEl.addEventListener("change", () => {
      const f = fileEl.files && fileEl.files[0];
      lblEl.textContent = f ? `Selected: ${f.name} (${f.size.toLocaleString()} bytes)` : "—";
    });

    btn.addEventListener("click", async () => {
      const file = fileEl.files && fileEl.files[0];
      if (!file) { alert("Choose a CSV file"); return; }

      const fd = new FormData();
      fd.append("file", file);                            // <-- backend expects 'file'
      fd.append("overwrite", $("overwrite").checked ? "1" : "0");

      outEl.textContent = "Uploading...";
      try {
        const res  = await fetch("/hist_upload", { method:"POST", body: fd });
        const text = await res.text(); // accept JSON or text
        try {
          const j = JSON.parse(text);
          outEl.textContent = JSON.stringify(j, null, 2);
          if (!res.ok) alert(`Upload failed: ${j.detail || res.status}`);
        } catch {
          outEl.textContent = text;
          if (!res.ok) alert(`Upload failed (non-JSON): HTTP ${res.status}`);
        }
      } catch (e) {
        outEl.textContent = String(e);
        alert("Upload error: " + (e?.message || e));
      }
    });
  })();

  // =============== Phase-1 (wiring only; keep your existing logic) ===============
  // If you already have handlers for these, remove or merge this section.

  const runP1Btn = $("btn_run_p1");
  if (runP1Btn) {
    runP1Btn.addEventListener("click", async ()=>{
      const payload = {
        LATEST_MM:   tryParse($("mm_latest").value),
        LATEST_PB:   tryParse($("pb_latest").value),
        LATEST_IL_JP: tryParse($("il_jp_latest").value),
        LATEST_IL_M1: tryParse($("il_m1_latest").value),
        LATEST_IL_M2: tryParse($("il_m2_latest").value),
        FEED_MM: $("FEED_MM").value || "",
        FEED_PB: $("FEED_PB").value || "",
        FEED_IL: $("FEED_IL").value || "",
        // Optional dates (backend can ignore or store)
        D_MM: $("mm_date").value || null,
        D_PB: $("pb_date").value || null,
        D_IL_JP: $("il_jp_date").value || null,
        D_IL_M1: $("il_m1_date").value || null,
        D_IL_M2: $("il_m2_date").value || null,
        HIST_MM_BLOB: $("HIST_MM_BLOB")?.value || "",
        HIST_PB_BLOB: $("HIST_PB_BLOB")?.value || "",
        HIST_IL_JP_BLOB: $("HIST_IL_JP_BLOB")?.value || "",
        HIST_IL_M1_BLOB: $("HIST_IL_M1_BLOB")?.value || "",
        HIST_IL_M2_BLOB: $("HIST_IL_M2_BLOB")?.value || ""
      };

      try {
        const res = await fetch("/run_json", {
          method:"POST",
          headers:{ "Content-Type":"application/json" },
          body: JSON.stringify(payload)
        });
        const j = await res.json();
        if (!j.ok) {
          alert("Phase 1 failed: " + (j.detail || JSON.stringify(j)));
          return;
        }
        $("p1_saved_path").textContent = j.saved_path || "—";
      } catch (e) {
        alert("Phase 1 error: " + (e?.message || e));
      }
    });
  }

  // History loaders (Load 20) — call your existing endpoints.
  bindLoad20("hist_mm_load20", "hist_mm_date", "HIST_MM_BLOB", "/hist_load20?game=MM");
  bindLoad20("hist_pb_load20", "hist_pb_date", "HIST_PB_BLOB", "/hist_load20?game=PB");
  bindLoad20("hist_il_jp_load20","hist_il_jp_date","HIST_IL_JP_BLOB","/hist_load20?game=IL&tier=JP");
  bindLoad20("hist_il_m1_load20","hist_il_m1_date","HIST_IL_M1_BLOB","/hist_load20?game=IL&tier=M1");
  bindLoad20("hist_il_m2_load20","hist_il_m2_date","HIST_IL_M2_BLOB","/hist_load20?game=IL&tier=M2");

  function bindLoad20(btnId, dateId, outId, urlBase){
    const btn = $(btnId); if (!btn) return;
    btn.addEventListener("click", async ()=>{
      const date = $(dateId)?.value || "";
      const url  = date ? `${urlBase}&date=${encodeURIComponent(date)}` : urlBase;
      try{
        const res = await fetch(url);
        const j = await res.json();
        if (j.ok && j.text) $(outId).value = j.text;
        else alert("Load failed: " + (j.detail || res.status));
      }catch(e){
        alert("Load error: " + (e?.message || e));
      }
    });
  }

  function tryParse(s){
    try{ return JSON.parse(s); } catch{ return null; }
  }

})();
