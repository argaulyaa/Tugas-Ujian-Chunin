const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");
const context = { Date };
vm.createContext(context);
const path = require("node:path").join(__dirname, "../frontend/chart-data.js");
assert.ok(fs.existsSync(path), "chart aggregation implementation is missing");
vm.runInContext(fs.readFileSync(path, "utf8"), context);
const aggregate = context.aggregateVisits;
const logs = [
  { timestamp: "2026-11-04T17:30:00+00:00" },
  { timestamp: "2026-11-05T16:59:00Z" },
  { timestamp: "2026-11-05T17:00:00Z" },
];
let result = aggregate(logs, "day", "2026-11-05");
assert.equal(result.length, 24);
assert.equal(result[0].count, 1);
assert.equal(result[23].count, 1);
assert.equal(
  result.reduce((s, x) => s + x.count, 0),
  2,
);
assert.equal(aggregate([], "month", "2024-02-01").length, 29);
assert.equal(aggregate([], "year", "2026-01-01").length, 12);
result = aggregate(logs, "week", "2026-11-05");
assert.equal(result.length, 7);
assert.equal(result[0].label, "2026-11-02");
assert.equal(
  result.reduce((s, x) => s + x.count, 0),
  3,
);
assert.throws(() => aggregate([{ timestamp: "invalid" }], "day", "2026-11-05"));
assert.throws(() => aggregate([], "day", "2026-02-30"));
console.log(
  "PASS: WIB boundaries, hourly zero-fill, Monday week, leap month, year and invalid input",
);
