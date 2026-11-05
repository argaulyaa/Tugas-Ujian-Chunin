"use strict";

(() => {
  const key = "visitor-log-token";
  const $ = (id) => document.getElementById(id);
  const error = (message = "") => {
    $("error").textContent = message;
    $("error").hidden = !message;
  };
  const status = (message) => {
    $("status").textContent = message;
  };
  const loginPage = document.body.dataset.view === "login";
  let token;
  try {
    token = sessionStorage.getItem(key);
  } catch {
    error(
      "Penyimpanan sesi tidak tersedia. Izinkan penyimpanan browser lalu muat ulang halaman.",
    );
    document.querySelectorAll("button").forEach((button) => {
      button.disabled = true;
    });
    return;
  }
  const signOut = () => {
    sessionStorage.removeItem(key);
    token = null;
    location.replace("login.html?reason=login-required");
  };

  async function api(path, method = "GET", body) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 20000);
    try {
      const headers = { Accept: "application/json" };
      if (token) headers.Authorization = `Bearer ${token}`;
      if (body !== undefined) headers["Content-Type"] = "application/json";
      const response = await fetch(`/api/${path}`, {
        method,
        headers,
        cache: "no-store",
        signal: controller.signal,
        ...(body === undefined ? {} : { body: JSON.stringify(body) }),
      });
      if (response.status === 401 && !loginPage) {
        signOut();
        throw new Error("Sesi berakhir. Silakan masuk kembali.");
      }
      if (!response.ok) {
        if (response.status === 401)
          throw new Error("Nama pengguna atau kata sandi tidak sesuai.");
        if (response.status === 429)
          throw new Error(
            "Terlalu banyak percobaan. Tunggu sebelum mencoba lagi.",
          );
        throw new Error(
          `Permintaan gagal (HTTP ${response.status}). Coba muat ulang data sebelum mengulang tindakan.`,
        );
      }
      if (path === "logs" && method === "GET" && !$("date").value) {
        const serverTime = Date.parse(response.headers.get("Date") || "");
        if (Number.isFinite(serverTime))
          $("date").value = new Date(serverTime + 7 * 3600000)
            .toISOString()
            .slice(0, 10);
      }
      if (response.status === 204) return null;
      // ponytail: only GET/login consume JSON; mutation responses may be empty.
      if (method !== "GET" && path !== "login") return null;
      return await response.json();
    } catch (cause) {
      if (cause.name === "AbortError")
        throw new Error(
          "Server terlalu lama merespons. Muat ulang data untuk memeriksa hasil sebelum mengulangi tindakan.",
        );
      if (cause instanceof TypeError)
        throw new Error(
          "Tidak dapat menghubungi server. Periksa koneksi lalu muat ulang data.",
        );
      if (cause instanceof SyntaxError)
        throw new Error("Respons server tidak valid. Coba lagi nanti.");
      throw cause;
    } finally {
      clearTimeout(timer);
    }
  }

  if (loginPage) {
    if (
      new URLSearchParams(location.search).get("reason") === "login-required"
    ) {
      $("login-notice").hidden = false;
    }
    $("login-form").addEventListener("submit", async (event) => {
      event.preventDefault();
      const button = event.currentTarget.querySelector("button");
      button.disabled = true;
      error();
      status("Memeriksa akun…");
      try {
        const result = await api("login", "POST", {
          username: $("username").value.trim(),
          password: $("password").value,
        });
        if (!result || typeof result.token !== "string" || !result.token)
          throw new Error("Server tidak mengembalikan sesi yang valid.");
        sessionStorage.setItem(key, result.token);
        $("password").value = "";
        location.replace("visitor-log.html");
      } catch (cause) {
        error(cause.message);
        status("");
        $("password").value = "";
        $("password").focus();
      } finally {
        button.disabled = false;
      }
    });
    return;
  }

  if (!token) {
    location.replace("login.html?reason=login-required");
    return;
  }

  // Shared GET refresh; never records a visit and never overlaps a mutation.
  setInterval(() => {
    if (token && !busy && !document.body.hidden)
      void run(
        "Memperbarui data otomatis…",
        refresh,
        "Data diperbarui otomatis.",
      );
  }, 30000);

  let busy = false;
  let hasData = false;
  const tableMessage = (message) => {
    const row = document.createElement("tr");
    const cell = document.createElement("td");
    cell.colSpan = 6;
    cell.className = "table-message";
    cell.textContent = message;
    row.append(cell);
    $("logs").replaceChildren(row);
  };

  async function refresh() {
    const data = await api("logs");
    if (
      !data ||
      !Number.isInteger(data.total_hits) ||
      data.total_hits < 0 ||
      !Array.isArray(data.logs) ||
      data.total_hits !== data.logs.length ||
      !data.logs.every(
        (log) =>
          log &&
          Number.isInteger(log.index) &&
          log.index >= 0 &&
          ["page", "timestamp", "ip", "user_agent"].every(
            (field) => typeof log[field] === "string",
          ),
      )
    ) {
      throw new Error(
        "Format data log tidak valid. Data sebelumnya tidak diubah.",
      );
    }
    data.logs = data.logs.filter((log) => log.page === "/");
    data.total_hits = data.logs.length;
    const fragment = document.createDocumentFragment();
    for (const log of data.logs) {
      const row = document.createElement("tr");
      for (const field of ["index", "page", "timestamp", "ip", "user_agent"]) {
        const cell = document.createElement("td");
        cell.textContent = String(log[field]);
        row.append(cell);
      }
      const cell = document.createElement("td");
      const button = document.createElement("button");
      button.type = "button";
      button.className = "delete";
      button.textContent = "Hapus";
      button.disabled = busy;
      button.setAttribute(
        "aria-label",
        `Hapus log indeks ${log.index}, halaman ${log.page}`,
      );
      button.addEventListener("click", () => {
        if (
          busy ||
          !window.confirm(`Hapus log indeks ${log.index} untuk ${log.page}?`)
        )
          return;
        void run(
          "Menghapus log…",
          async () => {
            await api(`logs?index=${encodeURIComponent(log.index)}`, "DELETE");
            await refresh();
            $("refresh").focus();
          },
          "Log dihapus. Jumlah tersimpan diperbarui.",
        );
      });
      cell.append(button);
      row.append(cell);
      fragment.append(row);
    }
    $("logs").replaceChildren(fragment);
    if (!data.logs.length)
      tableMessage(
        "Belum ada log tersimpan. Tambahkan kunjungan melalui formulir di atas.",
      );
    $("total").textContent = String(data.total_hits);
    hasData = true;
    renderChart(data.logs);
  }

  async function run(message, action, success) {
    if (busy) return;
    busy = true;
    error();
    status(message);
    $("log-section").setAttribute("aria-busy", "true");
    document.querySelectorAll("button").forEach((button) => {
      button.disabled = true;
    });
    try {
      await action();
      status(success);
    } catch (cause) {
      error(cause.message);
      status(
        hasData
          ? "Data terakhir tetap ditampilkan; mungkin belum mutakhir."
          : "Data belum tersedia.",
      );
      if (!hasData)
        tableMessage(
          "Data gagal dimuat. Gunakan Muat ulang data untuk mencoba lagi.",
        );
    } finally {
      busy = false;
      $("log-section").setAttribute("aria-busy", "false");
      document.querySelectorAll("button").forEach((button) => {
        button.disabled = false;
      });
    }
  }

  $("refresh").addEventListener("click", () => {
    void run(
      "Memuat data…",
      refresh,
      "Data diperbarui tanpa menambah kunjungan.",
    );
  });
  $("entry-form").addEventListener("submit", (event) => {
    event.preventDefault();
    const page = $("page").value.trim();
    if (!page) {
      error("Isi halaman, bukan hanya spasi.");
      $("page").focus();
      return;
    }
    void run(
      "Menyimpan kunjungan…",
      async () => {
        await api("logs", "POST", { page, user_agent: navigator.userAgent });
        await refresh();
      },
      "Kunjungan tersimpan. Data diperbarui.",
    );
  });
  $("logout").addEventListener("click", () => {
    void run(
      "Mengakhiri sesi…",
      async () => {
        await api("logout", "POST");
        signOut();
      },
      "Sesi diakhiri.",
    );
  });

  void run(
    "Memuat data…",
    async () => {
      await refresh();
      document.body.hidden = false;
    },
    "Data diperbarui.",
  );
})();
