// static/app.js v8 — layout-only update per your requests.
// - No Phase-1/3 autofill buttons.
// - Date boxes are plain text "M/D/YYYY".
// - On load, we prefill the pivot boxes with 3rd-newest dates so that "Load 20" puts that 3rd newest line first.

(function () {
  const $ = (id) => document.getElementById(id);

  async function postJSON(url, payload) {
    const res = await fetch(url, {
      method: "POST",
      headers: {"Content-Type":"application/json"},
      body: JSON.stringify(payload)
    });
    const txt = await res.text();
    try {
      const j = JSON.parse(txt);
      if (!res.ok) throw new Error(j.detail || ("HTTP " + res.status));
      return j;
    } catch {
      if (!res.ok) throw new Error("HTTP " + res.status + " (non-JSON)");
      throw new Error("Server returned non-JSON");
    }
  }

  // -------- CSV Upload ----------
  $("csv_form").addEventListener("submit", async (e)=>{
    e.preventDefault();
    const file = $("csv_file").files[0];
    if (!file) { alert("Choose a CSV file"); return; }
    const fd = new FormData();
    fd.append("file", file);
    fd.append("overwrite", $("overwrite").checked ? "1":"0");
    const res = await fetch("/hist_upload", { method: "POST", body: fd });
    const j = await res.json().catch(()=>null);
    $("import_out").textContent = j ? JSON.stringify(j, null, 2) : await res.text();
  });

  // -------- History Slice helpers ----------
  async function historySlice(game, tier, pivot, limit=20) {
    return await postJSON("/history_slice", { game, tier, pivot_date: pivot, limit });
  }

  async function load20_MM(){
    const p = $("mmPivot").value.trim();
    if(!p) return alert("Enter MM pivot date (M/D/YYYY)");
    const r = await historySlice("MM","",p,20);
    if(r.ok) $("histMM").value = r.blob || "";
  }
  async function load20_PB(){
    const p = $("pbPivot").value.trim();
    if(!p) return alert("Enter PB pivot date (M/D/YYYY)");
    const r = await historySlice("PB","",p,20);
    if(r.ok) $("histPB").value = r.blob || "";
  }
  async function load20_IL(tier){
    const id = tier==="JP"?"ilJpPivot":tier==="M1"?"ilM1Pivot":"ilM2Pivot";
    const outId = tier==="JP"?"histIL_JP":tier==="M1"?"histIL_M1":"histIL_M2";
    const p = $(id).value.trim();
    if(!p) return alert(`Enter IL ${tier} pivot date (M/D/YYYY)`);
    const r = await historySlice("IL",tier,p,20);
    if(r.ok) $(outId).value = r.blob || "";
  }

  $("mmRetrieve")?.addEventListener("click", load20_MM);
  $("pbRetrieve")?.addEventListener("click", load20_PB);
  $("ilJpRetrieve")?.addEventListener("click", ()=>load20_IL("JP"));
  $("ilM1Retrieve")?.addEventListener("click", ()=>load20_IL("M1"));
  $("ilM2Retrieve")?.addEventListener("click", ()=>load20_IL("M2"));

  // Prefill pivot dates with 3rd newest on load (no buttons shown)
  (async function prefillPivots(){
    try{
      const j = await fetch("/third_newest_dates", {cache:"no-store"}).then(r=>r.json());
      const p = j?.phase1 || {};
      if (p.MM)   $("mmPivot").value  = p.MM;
      if (p.PB)   $("pbPivot").value  = p.PB;
      if (p.IL_JP) $("ilJpPivot").value = p.IL_JP;
      if (p.IL_M1) $("ilM1Pivot").value = p.IL_M1;
      if (p.IL_M2) $("ilM2Pivot").value = p.IL_M2;
    }catch(e){
      console.warn("prefill pivots failed", e);
    }
  })();

  // -------- Save current NJ → History ----------
  $("btn_save_nj").addEventListener("click", async ()=>{
    try{
      const payload = {
        LATEST_MM   : eval($("mm_latest").value || "null"),
        LATEST_PB   : eval($("pb_latest").value || "null"),
        LATEST_IL_JP: eval($("il_jp_latest").value || "null"),
        LATEST_IL_M1: eval($("il_m1_latest").value || "null"),
        LATEST_IL_M2: eval($("il_m2_latest").value || "null"),
        dates: {
          MM  : $("mm_date").value || null,
          PB  : $("pb_date").value || null,
          IL_JP: $("il_jp_date").value || null,
          IL_M1: $("il_m1_date").value || null,
          IL_M2: $("il_m2_date").value || null,
        }
      };
      const out = await postJSON("/hist_add", payload);
      alert("Saved: " + JSON.stringify(out.added||[]));
    }catch(e){ alert("Save failed: " + e.message); }
  });

  // -------- Phase 1 ----------
  $("btn_run_p1").addEventListener("click", async ()=>{
    try{
      const body = {
        LATEST_MM:    eval($("mm_latest").value||"null"),
        LATEST_PB:    eval($("pb_latest").value||"null"),
        LATEST_IL_JP: eval($("il_jp_latest").value||"null"),
        LATEST_IL_M1: eval($("il_m1_latest").value||"null"),
        LATEST_IL_M2: eval($("il_m2_latest").value||"null"),
        FEED_MM: $("feed_mm").value||"",
        FEED_PB: $("feed_pb").value||"",
        FEED_IL: $("feed_il").value||""
      };
      const out = await postJSON("/run_json", body);
      $("p1_results").textContent = JSON.stringify(out, null, 2);
      if (out.saved_path){ $("p1_saved_path").value = out.saved_path; $("p2_input_path").value = out.saved_path; }
    }catch(e){ alert("Phase 1 failed: " + e.message); }
  });
  $("btn_copy_p1").addEventListener("click", ()=> navigator.clipboard.writeText($("p1_saved_path").value||""));

  // -------- Phase 2 ----------
  $("btn_run_p2").addEventListener("click", async ()=>{
    try{
      const p1 = $("p2_input_path").value.trim();
      const out = await postJSON("/run_phase2", { saved_path: p1 });
      $("p2_saved_path").value = out.saved_path || "";
      $("p3_input_path").value = out.saved_path || $("p3_input_path").value;

      const fmtList = (arr, tag) => (arr||[]).map((t,i)=>`${i+1}. ${t.mains.join(", ")}${tag?("  "+tag+" "+(t.bonus??"-")):""}`).join("\n") || "—";
      $("mm_buy").textContent = fmtList(out.buy_lists?.MM, "MB");
      $("pb_buy").textContent = fmtList(out.buy_lists?.PB, "PB");
      $("il_buy").textContent = fmtList(out.buy_lists?.IL, "");

      const fmtAgg = (agg)=>Object.entries(agg||{}).map(([k,arr])=>{
        const freq = {}; (arr||[]).forEach(p=>freq[p]=(freq[p]||0)+1);
        const top = Object.entries(freq).sort((a,b)=>b[1]-a[1]||(+a[0]-(+b[0]))).slice(0,8).map(([r,c])=>`${r}(${c})`).join(", ");
        return `${k}\tcount=${(arr||[]).length}\trows: ${top||"—"}`;
      }).join("\n") || "—";
      $("mm_agg").textContent = fmtAgg(out.agg_hits?.MM);
      $("pb_agg").textContent = fmtAgg(out.agg_hits?.PB);
      const il = out.agg_hits?.IL || {};
      const lines = [];
      for (const tier of ["JP","M1","M2"]) {
        const blk = il[tier]||{};
        for (const k of Object.keys(blk)) {
          const arr = blk[k]||[];
          const freq = {}; arr.forEach(p=>freq[p]=(freq[p]||0)+1);
          const top = Object.entries(freq).sort((a,b)=>b[1]-a[1]||(+a[0]-(+b[0]))).slice(0,8).map(([r,c])=>`${r}(${c})`).join(", ");
          lines.push(`${tier} ${k}\tcount=${arr.length}\trows: ${top||"—"}`);
        }
      }
      $("il_agg").textContent = lines.join("\n") || "—";
    }catch(e){ alert("Phase 2 failed: " + e.message); }
  });

  $("btn_copy_mm").addEventListener("click", ()=>navigator.clipboard.writeText($("mm_buy").textContent.trim()));
  $("btn_copy_pb").addEventListener("click", ()=>navigator.clipboard.writeText($("pb_buy").textContent.trim()));
  $("btn_copy_il").addEventListener("click", ()=>navigator.clipboard.writeText($("il_buy").textContent.trim()));

  $("btn_recent").addEventListener("click", loadRecent);
  $("btn_recent_bottom").addEventListener("click", loadRecent);
  async function loadRecent(){
    const r = await fetch("/recent",{cache:"no-store"});
    const j = await r.json().catch(()=>null);
    $("recent_out").textContent = j ? JSON.stringify(j, null, 2) : await r.text();
  }

  // -------- Phase 3 ----------
  $("btn_run_p3").addEventListener("click", async ()=>{
    try{
      const p2 = $("p3_input_path").value.trim();

      // Build NWJ JSON from Phase-3 five boxes
      const toPair = (txt) => (txt && txt.trim()) ? eval(txt.trim()) : null;
      const NWJ = {
        LATEST_MM   : toPair($("mm_latest_p3").value),
        LATEST_PB   : toPair($("pb_latest_p3").value),
        LATEST_IL_JP: toPair($("il_jp_latest_p3").value),
        LATEST_IL_M1: toPair($("il_m1_latest_p3").value),
        LATEST_IL_M2: toPair($("il_m2_latest_p3").value)
      };

      const out = await postJSON("/confirm_json", { saved_path: p2, NWJ });
      const fmtHits=(obj)=>Object.entries(obj||{}).map(([k,v])=>`${k}\t${(v||[]).join(", ")||"—"}`).join("\n") || "—";
      $("mm_c_hits").textContent = fmtHits(out.MM||{});
      $("pb_c_hits").textContent = fmtHits(out.PB||{});
      const ilLines=[];
      if(out.IL){
        for(const k of ["JP","M1","M2"]){
          const block = out.IL[k]||{};
          const row = Object.entries(block).map(([t,arr])=>`${k} ${t}: ${(arr||[]).join(", ")||"—"}`).join("\n");
          if(row) ilLines.push(row);
        }
      }
      $("il_c_hits").textContent = ilLines.join("\n") || "—";
    }catch(e){ alert("Confirm failed: " + e.message); }
  });

})();
