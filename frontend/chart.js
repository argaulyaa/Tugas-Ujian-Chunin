"use strict";
let chartLogs = [];
function renderChart(logs) {
  const $ = (id) => document.getElementById(id);
  const svg = (name, attrs, text) => {
    const node = document.createElementNS("http://www.w3.org/2000/svg", name);
    for (const [key, value] of Object.entries(attrs))
      node.setAttribute(key, value);
    if (text !== undefined) node.textContent = text;
    return node;
  };
  try {
    if (!$("date").value)
      throw new Error(
        "Tanggal server tidak tersedia. Muat ulang data untuk mencoba lagi.",
      );
    const points = aggregateVisits(logs, $("period").value, $("date").value);
    const total = points.reduce((sum, p) => sum + p.count, 0);
    const max = Math.max(1, ...points.map((p) => p.count));
    const x = (i) => 60 + (i * 870) / (points.length - 1);
    const y = (n) => 260 - (n / max) * 230;
    const title = svg(
      "title",
      { id: "chart-title" },
      `Grafik ${total} log tersimpan, WIB`,
    );
    const description = svg(
      "desc",
      { id: "chart-description" },
      "Garis menghubungkan jumlah tiap interval; interval kosong bernilai nol.",
    );
    const elements = [title, description];
    for (const n of [0, max]) {
      elements.push(
        svg("line", { x1: 60, y1: y(n), x2: 930, y2: y(n), stroke: "#d4ddda" }),
      );
      elements.push(
        svg(
          "text",
          { x: 45, y: y(n) + 5, "text-anchor": "end", fill: "#25312f" },
          n,
        ),
      );
    }
    elements.push(
      svg("polyline", {
        points: points.map((p, i) => `${x(i)},${y(p.count)}`).join(" "),
        fill: "none",
        stroke: "#09675f",
        "stroke-width": 3,
      }),
    );
    points.forEach((p, i) => {
      const dot = svg("circle", {
        cx: x(i),
        cy: y(p.count),
        r: 4,
        fill: "#09675f",
      });
      dot.append(svg("title", {}, `${p.label}: ${p.count}`));
      elements.push(dot);
      if (i % Math.ceil(points.length / 8) === 0 || i === points.length - 1)
        elements.push(
          svg(
            "text",
            {
              x: x(i),
              y: 290,
              "text-anchor": "middle",
              fill: "#25312f",
              "font-size": 13,
            },
            p.label,
          ),
        );
    });
    $("chart").replaceChildren(...elements);
    $("range").textContent =
      `${$("date").value} · ${points[0].label} – ${points.at(-1).label} WIB`;
    chartLogs = logs;
    $("chart-error").hidden = true;
  } catch (cause) {
    $("chart-error").textContent = cause.message;
    $("chart-error").hidden = false;
    $("chart").replaceChildren();
  }
}
document.getElementById("filters").addEventListener("submit", (event) => {
  event.preventDefault();
  renderChart(chartLogs);
});
