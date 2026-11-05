const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const root = path.join(__dirname, "../frontend");
const html = fs.readFileSync(path.join(root, "visitor-log.html"), "utf8");
assert.ok(
  html.indexOf('id="chart-section"') > html.indexOf('class="page-heading"'),
  "chart must follow heading",
);
assert.ok(
  html.indexOf('id="chart-section"') < html.indexOf('class="entry-section"'),
  "chart must precede manual form",
);
assert.ok(!html.includes('href="chart.html"'), "no separate chart navigation");
const app = fs.readFileSync(path.join(root, "app.js"), "utf8");
assert.match(
  app,
  /renderChart\(data\.logs\)/,
  "chart uses same GET data as table",
);
assert.match(app, /30000/, "30-second update");
const chart = fs.readFileSync(path.join(root, "chart.js"), "utf8");
assert.ok(!chart.includes("fetch("), "renderer must not fetch independently");
assert.ok(
  !chart.includes("sessionStorage"),
  "renderer must reuse dashboard auth",
);
assert.ok(!html.includes('id="values"'), "interval table removed");
assert.ok(
  !chart.includes("$('values')"),
  "renderer must not reference removed table",
);
assert.ok(
  !chart.includes("$('chart-status')"),
  "renderer must not reference removed summary",
);
assert.ok(
  html.includes('id="status" class="sr-only"'),
  "status remains accessible without visual clutter",
);
console.log(
  "PASS: dashboard placement, shared data/auth, 30-second update, no interval table or visible status",
);
