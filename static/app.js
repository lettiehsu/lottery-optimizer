// --- tiny helpers so every click shows activity
const toast = (msg, kind="ok") => {
  const t = document.createElement("div");
  t.className = `toast ${kind}`;
  t.textContent = msg;
  document.body.appendChild(t);
  setTimeout(()=>t.remove(), 1800);
};
const busy = (btn, on, label="Working…") => {
  if (!btn) return;
  if (on) {
    btn.dataset.old = btn.textContent;
    btn.textContent = label;
    btn.disabled = true;
  } else {
    btn.textContent = btn.dataset.old || btn.textContent;
    btn.disabled = false;
  }
};

// --- normalize history payload into the printable “mm-dd-yy  a-b-c-d-e  B” lines
function formatHistoryLines(payload) {
  // server may return {blob:"...", rows:[{date:"09/12/2025", mains:[..], bonus:..}, ...]}
  if (!payload) return "";
  if (payload.blob && typeof payload.blob === "string") return payload.blob;
  if (Array.isArray(payload.rows)) {
    const lines = payload.rows.map(r => {
      const d = (r.date || r.draw_date || "").trim(); // MM/DD/YYYY
      const mm = d ? d.split("/") : [];
      const mmddyy = (mm.length === 3) ? `${mm[0].padStart(2,"0")}-${mm[1].padStart(2,"0")}-${mm[2].slice(-2)}` : d;
      const mains = (r.mains || r.n || r.n1 ? (r.mains || [r.n1,r.n2,r.n3,r.n4,r.n5]).filter(Boolean) : []);
      const bonus = (r.bonus ?? r.mb ?? r.pb ?? r.b); // allow null for IL
      const mainsStr = mains.map(n=>String(n).padStart(2,"0")).join("-");
      return bonus == null ? `${mmddyy}  ${mainsStr}` : `${mmddyy}  ${mainsStr}  ${String(bonus).padStart(2,"0")}`;
    });
    return lines.join("\n");
  }
  // worst case, stringify
  return String(payload);
}

// --- load 20 handler (works for MM / PB / IL tiers)
async function load20(btn, game, dateStr, outEl, tier="") {
  if (!dateStr) { toast("Pick a start date (3rd-newest).","warn"); return; }
  const qs = new URLSearchParams({ game, from: dateStr, limit: "20" });
  if (tier) qs.set("tier", tier);
  busy(btn, true, "Loading…");
  try {
    const res = await fetch(`/store/get_history?${qs.toString()}`);
    const data = await res.json();
    if (!data.ok) throw new Error(data.detail || data.error || "Load failed");
    outEl.value = formatHistoryLines(data);
    toast(`${game}${tier?` ${tier}`:""}: loaded 20`);
  } catch (e) {
    outEl.value = "";
    toast(String(e), "error");
  } finally {
    busy(btn, false);
  }
}
