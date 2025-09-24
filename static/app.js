// static/app.js — COMPLETE (minimal upload wiring)

(() => {
  const $ = (s) => document.querySelector(s);

  // Elements (IDs must exist in your HTML)
  const fileInput     = $("#csvFile") || document.querySelector("input[type=file]");
  const overwriteCbx  = $("#overwriteCsv") || document.querySelector("input[type=checkbox][name=overwrite]");
  const importBtn     = $("#importCsv");
  const uploadLog     = $("#uploadLog"); // <pre id="uploadLog"></pre> optional

  // Tiny logger
  function log(msg, kind = "info") {
    if (!uploadLog) return;
    uploadLog.textContent = (typeof msg === "string") ? msg : JSON.stringify(msg, null, 2);
    uploadLog.className = ""; // reset
    uploadLog.classList.add("log");
    uploadLog.classList.add(kind === "error" ? "err" : "ok");
  }

  function setBusy(btn, busy, textBusy = "Uploading…", textIdle = "Import CSV") {
    if (!btn) return;
    btn.disabled = !!busy;
    btn.dataset.labelIdle = btn.dataset.labelIdle || textIdle;
    btn.textContent = busy ? textBusy : btn.dataset.labelIdle;
    btn.classList.toggle("is-busy", !!busy);
  }

  async function importCsv() {
    try {
      if (!fileInput || !fileInput.files || !fileInput.files[0]) {
        log("Choose a CSV file first.", "error");
        return;
      }
      const fd = new FormData();
      fd.append("file", fileInput.files[0]);              // <-- key must be 'file'
      fd.append("overwrite", overwriteCbx?.checked ? "true" : "false");

      setBusy(importBtn, true);
      log("Uploading…");

      const res = await fetch("/store/import_csv", {
        method: "POST",
        body: fd, // multipart/form-data automagic
      });

      const data = await res.json().catch(() => ({}));
      if (!res.ok || !data?.ok) {
        throw new Error(data?.detail || data?.error || `HTTP ${res.status}`);
      }
      // Show stats
      log(data, "ok");
    } catch (err) {
      log(String(err), "error");
    } finally {
      setBusy(importBtn, false);
    }
  }

  // Wire button
  if (importBtn) {
    importBtn.addEventListener("click", (e) => {
      e.preventDefault();
      importCsv();
    });
  }

  // Make button clicks feel responsive visually
  document.querySelectorAll("button").forEach((b) => {
    b.addEventListener("mousedown", () => b.classList.add("pressed"));
    b.addEventListener("mouseup",   () => b.classList.remove("pressed"));
    b.addEventListener("mouseleave",() => b.classList.remove("pressed"));
  });
})();
