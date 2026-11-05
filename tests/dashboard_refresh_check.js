// Executes production dashboard controller with a small DOM/API boundary double.
const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");
const elements = new Map();
const element = () => ({
  hidden: false,
  value: "/",
  handlers: {},
  children: [],
  append(...nodes) {
    this.children.push(...nodes);
  },
  replaceChildren(...nodes) {
    this.children = nodes;
  },
  setAttribute() {},
  focus() {},
  addEventListener(name, fn) {
    this.handlers[name] = fn;
  },
});
const get = (id) => {
  if (!elements.has(id)) elements.set(id, element());
  return elements.get(id);
};
get("date").value = "";
const calls = [],
  renders = [];
const logs = [
  {
    index: 2,
    page: "/login.html",
    timestamp: "2026-11-04T18:00:00Z",
    ip: "127.0.0.1",
    user_agent: "test",
  },
  {
    index: 7,
    page: "/",
    timestamp: "2026-11-04T18:00:00Z",
    ip: "127.0.0.1",
    user_agent: "test",
  },
];
let interval;
const context = {
  document: {
    body: { dataset: { view: "dashboard" }, hidden: true },
    getElementById: get,
    querySelectorAll: () => [],
    createElement: element,
    createDocumentFragment: element,
  },
  sessionStorage: { getItem: () => "test-session", removeItem() {} },
  location: {
    pathname: "/visitor-log.html",
    replace() {
      throw Error("unexpected redirect");
    },
  },
  navigator: { userAgent: "test" },
  window: { confirm: () => true },
  AbortController,
  setTimeout,
  clearTimeout,
  setInterval(fn, delay) {
    assert.equal(delay, 30000);
    interval = fn;
  },
  renderChart(logs) {
    renders.push(logs);
  },
  async fetch(url, options) {
    calls.push({ url, method: options.method, body: options.body });
    return {
      status: 200,
      ok: true,
      headers: { get: () => "Wed, 04 Nov 2026 18:00:00 GMT" },
      json: async () => ({ total_hits: logs.length, logs }),
    };
  },
};
vm.createContext(context);
vm.runInContext(
  fs.readFileSync(
    require("node:path").join(__dirname, "../frontend/app.js"),
    "utf8",
  ),
  context,
);
const tick = () => new Promise((resolve) => setImmediate(resolve));
const methods = () => calls.map((call) => call.method);
(async () => {
  await tick();
  assert.equal(context.document.body.hidden, false);
  assert.deepEqual(methods(), ["GET"]);
  assert.equal(renders.length, 1);
  assert.equal(renders[0].length, 1, "chart only includes landing visits");
  assert.equal(renders[0][0].index, 7, "filter preserves server indices");
  assert.equal(get("total").textContent, "1");
  assert.equal(
    get("logs").children[0].children[0].children[0].textContent,
    "7",
    "table preserves server indices",
  );
  assert.equal(
    get("date").value,
    "2026-11-05",
    "default uses server date converted to WIB",
  );
  get("date").value = "2026-10-01";
  calls.length = 0;
  interval();
  await tick();
  assert.deepEqual(methods(), ["GET"], "timer must only read");
  assert.equal(renders.length, 2);
  assert.equal(
    get("date").value,
    "2026-10-01",
    "refresh preserves historical selection",
  );
  calls.length = 0;
  get("entry-form").handlers.submit({ preventDefault() {} });
  await tick();
  assert.deepEqual(methods(), ["POST", "GET"]);
  assert.equal(JSON.parse(calls[0].body).page, "/");
  assert.equal(
    get("page").value,
    "/",
    "readonly landing page remains available after submit",
  );
  assert.equal(renders.length, 3, "manual add must immediately redraw");
  calls.length = 0;
  get("entry-form").handlers.submit({ preventDefault() {} });
  await tick();
  assert.deepEqual(methods(), ["POST", "GET"], "manual add can be repeated");
  calls.length = 0;
  const row = get("logs").children[0].children[0];
  row.children[5].children[0].handlers.click();
  await tick();
  assert.deepEqual(methods(), ["DELETE", "GET"]);
  assert.equal(
    calls[0].url,
    "/api/logs?index=7",
    "delete uses original server index",
  );
  console.log(
    "PASS: auth before reveal, server date WIB, GET-only timer, shared filtered table/chart, original delete index, repeat manual add",
  );
})().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
