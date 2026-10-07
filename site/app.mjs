import { UNIT_SCALE, pivotLlm, hideDatedSnapshots, formatPrice, taskCosts, historySeries, isBase } from "./lib.mjs";

const $ = (id) => document.getElementById(id);
const STALE_DAYS = 3;
const state = { unit: "1M", sort: {}, snapshot: null, tasks: null, chart: null };

const UNIT_LABEL = { "1M_tokens": "1M tokens", "1M_characters": "1M characters", image: "image", minute: "minute", second: "second", page: "page" };

async function getJson(path) {
  const res = await fetch(path);
  if (!res.ok) throw new Error(`${path}: ${res.status}`);
  return res.json();
}

function el(tag, attrs = {}, text) {
  const node = document.createElement(tag);
  Object.assign(node, attrs);
  if (text !== undefined) node.textContent = text;
  return node;
}

function fillSelect(select, options, selected) {
  select.replaceChildren(...options.map(([value, label]) => el("option", { value }, label)));
  if (selected !== undefined) select.value = selected;
}

function renderTable(table, columns, rows, sortKey) {
  const sort = state.sort[sortKey] ?? { key: columns[0].key, dir: 1 };
  const sorted = [...rows].sort((a, b) => {
    const x = a[sort.key], y = b[sort.key];
    if (x === undefined || x === null) return 1;
    if (y === undefined || y === null) return -1;
    return (x < y ? -1 : x > y ? 1 : 0) * sort.dir;
  });
  const head = el("tr");
  for (const col of columns) {
    const th = el("th", { scope: "col" }, col.label);
    if (col.key === sort.key) th.setAttribute("aria-sort", sort.dir === 1 ? "ascending" : "descending");
    th.addEventListener("click", () => {
      state.sort[sortKey] = { key: col.key, dir: sort.key === col.key ? -sort.dir : 1 };
      renderTable(table, columns, rows, sortKey);
    });
    head.append(th);
  }
  const body = sorted.map((row) => {
    const tr = el("tr");
    for (const col of columns) {
      const td = el("td");
      const content = col.render ? col.render(row) : row[col.key];
      content instanceof Node ? td.append(content) : (td.textContent = content ?? "–");
      tr.append(td);
    }
    return tr;
  });
  table.replaceChildren(el("thead", {}, undefined), el("tbody"));
  table.tHead.append(head);
  table.tBodies[0].append(...body);
}

const scaled = (row, key) => (row[key] === undefined ? undefined : row[key] * UNIT_SCALE[state.unit]);

function renderPrices() {
  const q = $("q").value.trim().toLowerCase();
  const provider = $("provider").value, tier = $("tier").value, ctx = $("context").value;
  let models = pivotLlm(state.snapshot.rows).filter((m) => m.tier === tier);
  if ($("dated").checked) models = hideDatedSnapshots(models);
  models = models.filter((m) => (!provider || m.provider === provider) && m.model.toLowerCase().includes(q)
    && (ctx === "all" || (ctx === "base" ? m.context_over === null : m.context_over !== null)));
  $("prices-count").textContent = `${models.length} model prices, USD per ${state.unit === "1B" ? "1B" : "1M"} tokens`;
  const price = (key, label) => ({ key, label, render: (r) => formatPrice(scaled(r, key)) });
  renderTable($("prices-table"), [
    { key: "provider", label: "Provider" },
    { key: "model", label: "Model", render: (r) => el("a", { href: r.url, target: "_blank", rel: "noopener" }, r.model) },
    { key: "context_over", label: "Context", render: (r) => (r.context_over ? `> ${r.context_over / 1000}k` : "base") },
    price("input", "Input"), price("output", "Output"), price("cache_read", "Cache read"),
    price("cache_write", "Cache write"), price("cache_write_1h", "Cache write 1h"),
  ], models, "prices");
}

function renderServices() {
  const type = $("s-type").value, q = $("s-q").value.trim().toLowerCase();
  const rows = state.snapshot.rows.filter((r) => r.service_type === type && r.tier === "standard" && r.context_over === null
    && r.model.toLowerCase().includes(q));
  $("services-count").textContent = `${rows.length} prices`;
  renderTable($("services-table"), [
    { key: "provider", label: "Provider" },
    { key: "model", label: "Model", render: (r) => el("a", { href: r.url, target: "_blank", rel: "noopener" }, r.model) },
    { key: "direction", label: "Applies to" },
    { key: "price_usd", label: "Price", render: (r) => `${formatPrice(r.price_usd)} / ${UNIT_LABEL[r.unit]}` },
  ], rows, "services");
}

function renderTasks() {
  const task = state.tasks.find((t) => t.id === $("t-task").value);
  const limit = Number($("t-limit").value);
  $("t-desc").textContent = `${task.description} Assumes: ${task.usage.map((u) => `${u.amount.toLocaleString("en-US")} ${u.unit === "1M_tokens" ? "tokens" : u.unit + "(s)"} ${u.direction}`).join(", ")}.`;
  const costs = taskCosts(task, state.snapshot.rows);
  renderTable($("tasks-table"), [
    { key: "cost", label: "Cost (USD)", render: (r) => formatPrice(r.cost, 3) },
    { key: "provider", label: "Provider" }, { key: "model", label: "Model" },
  ], limit ? costs.slice(0, limit) : costs, "tasks");
}

async function renderHistory() {
  const provider = $("h-provider").value, model = $("h-model").value;
  if (!model) return;
  const text = await fetch(`data/history/${provider.toLowerCase()}.jsonl`).then((r) => (r.ok ? r.text() : ""));
  const entries = text.split("\n").filter(Boolean).map((l) => JSON.parse(l));
  const { dates, series } = historySeries(entries, model);
  $("h-note").textContent = `${dates.length} snapshot date(s) recorded; USD per ${state.unit} tokens, standard tier, base prompt.`;
  state.chart?.destroy();
  const css = getComputedStyle(document.documentElement);
  const colors = ["#0d9488", "#d97706", "#7c3aed", "#db2777", "#2563eb"];
  state.chart = new Chart($("h-chart"), {
    type: "line",
    data: { labels: dates, datasets: Object.entries(series).map(([direction, values], i) => ({
      label: direction, data: values.map((v) => (v === null ? null : v * UNIT_SCALE[state.unit])),
      borderColor: colors[i % colors.length], backgroundColor: colors[i % colors.length], stepped: true, pointRadius: 4,
    })) },
    options: { maintainAspectRatio: false, scales: { y: { beginAtZero: true, ticks: { color: css.getPropertyValue("--muted") } },
      x: { ticks: { color: css.getPropertyValue("--muted") } } }, plugins: { legend: { labels: { color: css.getPropertyValue("--fg") } } } },
  });
}

function fillHistoryModels() {
  const provider = $("h-provider").value;
  const models = [...new Set(state.snapshot.rows.filter((r) => r.provider === provider && r.service_type === "llm" && isBase(r))
    .map((r) => r.model))].sort();
  fillSelect($("h-model"), models.map((m) => [m, m]));
  return renderHistory();
}

function showTab(name) {
  for (const btn of document.querySelectorAll("#tabs button")) btn.setAttribute("aria-selected", btn.dataset.tab === name);
  for (const panel of document.querySelectorAll(".panel")) panel.hidden = panel.id !== name;
  if (name === "history") renderHistory();
}

function init() {
  const { rows, generated_at } = state.snapshot;
  const age = (Date.now() - Date.parse(generated_at)) / 86_400_000;
  $("updated").textContent = `Last update: ${generated_at.slice(0, 10)}.`;
  if (age > STALE_DAYS) {
    $("stale").hidden = false;
    $("stale").textContent = `Data is ${Math.floor(age)} days old — the daily collector may have stopped.`;
  }
  const providers = [...new Set(rows.map((r) => r.provider))].sort();
  fillSelect($("provider"), [["", "All providers"], ...providers.map((p) => [p, p])]);
  fillSelect($("h-provider"), providers.map((p) => [p, p]));
  const types = [...new Set(rows.filter((r) => r.service_type !== "llm").map((r) => r.service_type))].sort();
  fillSelect($("s-type"), types.map((t) => [t, t]));
  fillSelect($("t-task"), state.tasks.map((t) => [t.id, t.name]));

  for (const id of ["q", "provider", "tier", "context", "dated"]) $(id).addEventListener("input", renderPrices);
  for (const id of ["s-type", "s-q"]) $(id).addEventListener("input", renderServices);
  for (const id of ["t-task", "t-limit"]) $(id).addEventListener("input", renderTasks);
  $("h-provider").addEventListener("input", fillHistoryModels);
  $("h-model").addEventListener("input", renderHistory);
  for (const btn of document.querySelectorAll("[data-unit]")) {
    btn.addEventListener("click", () => {
      state.unit = btn.dataset.unit;
      for (const b of document.querySelectorAll("[data-unit]")) b.setAttribute("aria-pressed", b === btn);
      renderPrices();
      if (!$("history").hidden) renderHistory();
    });
  }
  for (const btn of document.querySelectorAll("#tabs button")) btn.addEventListener("click", () => showTab(btn.dataset.tab));

  fillHistoryModels();
  renderPrices(); renderServices(); renderTasks();
}

try {
  [state.snapshot, { tasks: state.tasks }] = await Promise.all([getJson("data/current.json"), getJson("data/tasks.json")]);
  init();
} catch (err) {
  const banner = $("stale");
  banner.hidden = false;
  banner.textContent = `Could not load price data (${err.message}).`;
}
