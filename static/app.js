async function postJSON(url, data) {
  const res = await fetch(url, {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify(data),
  });
  const txt = await res.text();
  return txt;
}

function parseKV(s) {
  try { return JSON.parse(s); } catch { return s; }
}

document.getElementById("phase1-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const f = e.target;
  const payload = {
    LATEST_MM: f.LATEST_MM.value.trim(),
    LATEST_PB: f.LATEST_PB.value.trim(),
    LATEST_IL_JP: f.LATEST_IL_JP.value.trim(),
    LATEST_IL_M1: f.LATEST_IL_M1.value.trim(),
    LATEST_IL_M2: f.LATEST_IL_M2.value.trim(),
    FEED_MM: f.FEED_MM.value,
    FEED_PB: f.FEED_PB.value,
    FEED_IL: f.FEED_IL.value,
    HIST_MM_BLOB: f.HIST_MM_BLOB.value,
    HIST_PB_BLOB: f.HIST_PB_BLOB.value,
    HIST_IL_BLOB: f.HIST_IL_BLOB.value,
    phase: "phase1"
  };
  const out = document.getElementById("phase1-output");
  out.textContent = "Running Phase 1...";
  try {
    const resp = await postJSON("/run_json", payload);
    out.textContent = resp;
  } catch (err) {
    out.textContent = "Error: " + err;
  }
});

document.getElementById("phase2-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const f = e.target;
  const out = document.getElementById("phase2-output");
  out.textContent = "Running Phase 2 (100×)...";
  try {
    const resp = await postJSON("/run_json", {
      phase: "phase2",
      saved_path: f.saved_path.value.trim()
    });
    out.textContent = resp;
  } catch (err) {
    out.textContent = "Error: " + err;
  }
});

document.getElementById("phase3-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const f = e.target;
  const out = document.getElementById("phase3-output");
  out.textContent = "Confirming vs NWJ...";
  try {
    const payload = { saved_path: f.saved_path.value.trim() };
    const maybe = f.NWJ.value.trim();
    if (maybe) payload.NWJ = parseKV(maybe);
    const resp = await postJSON("/confirm_json", payload);
    out.textContent = resp;
  } catch (err) {
    out.textContent = "Error: " + err;
  }
});

document.getElementById("btn-recent").addEventListener("click", async () => {
  const out = document.getElementById("recent-output");
  out.textContent = "Loading...";
  try {
    const res = await fetch("/recent");
    out.textContent = await res.text();
  } catch (err) {
    out.textContent = "Error: " + err;
  }
});
