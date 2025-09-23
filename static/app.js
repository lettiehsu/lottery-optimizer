// ---------- helpers ----------
function press(el){ el?.classList.add('pressed'); setTimeout(()=>el?.classList.remove('pressed'),90); }
function buttonBusy(btn, on=true, label){
  if(!btn) return;
  if(on){
    btn.dataset._label = btn.textContent;
    btn.disabled = true; btn.classList.add('busy');
    if(label) btn.textContent = label;
  }else{
    btn.disabled = false; btn.classList.remove('busy');
    if(btn.dataset._label) btn.textContent = btn.dataset._label;
  }
}
async function getJSON(url){
  const r = await fetch(url, {headers:{'Accept':'application/json'}});
  if(!r.ok) throw new Error(`${r.status} ${r.statusText}`);
  return r.json();
}
function latestString(game,row){
  const mains = row?.mains || [];
  const bonus = (game==='IL') ? 'null' : (row?.bonus ?? 'null');
  return `[[${mains.join(',')}],${bonus}]`;
}

// ---------- retrieve 2nd newest (per game) ----------
const doRetrieve = async (btn, game, dateStr, previewEl, tier = "") => {
  if (!dateStr) { toast("Enter a date (MM/DD/YYYY).", "warn"); return; }
  const params = new URLSearchParams({ game, date: dateStr });
  if (tier) params.set("tier", tier);

  press(btn); buttonBusy(btn, true, "Retrieving…");
  try {
    const data = await getJSON(`/store/get_by_date?${params.toString()}`);
    if (!data?.ok || !data.row) throw new Error(data?.detail || data?.error || "Retrieve failed");
    // Convert to the exact string Phase-1 expects
    const formatted = latestString(game === 'IL' ? 'IL' : game, data.row);
    previewEl.value = formatted;                         // <- NOT JSON.stringify
    toast(`${game}${tier ? " " + tier : ""} retrieved.`, "ok");
  } catch (e) {
    previewEl.value = "";
    toast(String(e && e.message || e), "error", 3200);
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

// ---------- history "Load 20" (use the 3rd-newest date you typed) ----------
async function load20({ btn, game, startInput, outTextarea, tier }) {
  const start = startInput.value.trim();
  if (!start) { toast("Enter a start date (3rd-newest).", "warn"); return; }
  const params = new URLSearchParams({ game, from: start, limit: "20" });
  if (tier) params.set("tier", tier);

  press(btn); buttonBusy(btn, true, "Loading…");
  try {
    const data = await getJSON(`/store/get_history?${params.toString()}`);
    if (!data?.ok || !Array.isArray(data.rows)) throw new Error(data?.detail || data?.error || "Load failed");

    // Render one row per line; IL has 6 mains; MM/PB have 5 + bonus at end
    const lines = data.rows.map(r=>{
      const d = r.date?.slice(2).replaceAll('/','-'); // "09/12/2025" -> "09-12-25"
      if (game === 'IL') {
        return `${d}  ${String(r.mains).padStart(2,'0').replaceAll(',','-')}`;
      } else {
        return `${d}  ${r.mains.map(n=>String(n).padStart(2,'0')).join('-')}  ${String(r.bonus).padStart(2,'0')}`;
      }
    });
    outTextarea.value = lines.join('\n');
    toast("Loaded 20.", "ok");
  } catch (e) {
    outTextarea.value = "";
    toast(String(e && e.message || e), "error");
  } finally {
    buttonBusy(btn, false);
  }
}

// Wire the three Load-20 buttons
mmLoad20?.addEventListener('click', ev => load20({
  btn: ev.currentTarget, game: 'MM',
  startInput: document.getElementById('histMMDate'),
  outTextarea: document.getElementById('histMMBlob')
}));
pbLoad20?.addEventListener('click', ev => load20({
  btn: ev.currentTarget, game: 'PB',
  startInput: document.getElementById('histPBDate'),
  outTextarea: document.getElementById('histPBBlob')
}));
ilJPLoad20?.addEventListener('click', ev => load20({
  btn: ev.currentTarget, game: 'IL', tier: 'JP',
  startInput: document.getElementById('histILJPDate'),
  outTextarea: document.getElementById('histILJPBlob')
}));
ilM1Load20?.addEventListener('click', ev => load20({
  btn: ev.currentTarget, game: 'IL', tier: 'M1',
  startInput: document.getElementById('histILM1Date'),
  outTextarea: document.getElementById('histILM1Blob')
}));
ilM2Load20?.addEventListener('click', ev => load20({
  btn: ev.currentTarget, game: 'IL', tier: 'M2',
  startInput: document.getElementById('histILM2Date'),
  outTextarea: document.getElementById('histILM2Blob')
}));
