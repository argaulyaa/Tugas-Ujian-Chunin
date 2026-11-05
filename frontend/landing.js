"use strict";
// One attempt per document load; no retry that could double-count.
fetch("/api/visit", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ page: "/" }),
  cache: "no-store",
  signal: AbortSignal.timeout(10000),
})
  .then((response) => {
    if (!response.ok) throw new Error("Recording unavailable");
  })
  .catch(() => {
    document.getElementById("visit-status").textContent =
      "Pencatatan kunjungan tidak tersedia.";
  });
