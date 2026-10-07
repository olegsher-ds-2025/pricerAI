export const UNIT_SCALE = { "1M": 1, "1B": 1000 };
export const DIRECTIONS = ["input", "output", "cache_read", "cache_write", "cache_write_1h"];

const DATED = /-(\d{4}-\d{2}-\d{2}|\d{8})$/;

export function isBase(row) {
  return row.tier === "standard" && row.context_over === null;
}

export function pivotLlm(rows) {
  const byKey = new Map();
  for (const r of rows) {
    if (r.service_type !== "llm") continue;
    const key = [r.provider, r.model, r.tier, r.context_over].join("|");
    if (!byKey.has(key)) {
      byKey.set(key, { provider: r.provider, model: r.model, tier: r.tier, context_over: r.context_over, url: r.url });
    }
    byKey.get(key)[r.direction] = r.price_usd;
  }
  return [...byKey.values()];
}

export function hideDatedSnapshots(models) {
  const names = new Set(models.map((m) => `${m.provider}|${m.model}`));
  return models.filter((m) => {
    const alias = m.model.replace(DATED, "");
    return alias === m.model || !names.has(`${m.provider}|${alias}`);
  });
}

export function formatPrice(value, maxDigits = 4) {
  if (value === undefined || value === null) return "–";
  return "$" + value.toLocaleString("en-US", { maximumSignificantDigits: maxDigits });
}

function priceOf(rows, task, usage) {
  return rows.find((r) => r.service_type === task.service_type && r.unit === usage.unit
    && r.direction === usage.direction && isBase(r))?.price_usd;
}

export function taskCosts(task, rows) {
  const candidates = rows.filter((r) => r.service_type === task.service_type && isBase(r));
  const models = new Map();
  for (const r of candidates) {
    const key = `${r.provider}|${r.model}`;
    if (!models.has(key)) models.set(key, { provider: r.provider, model: r.model, rows: [] });
    models.get(key).rows.push(r);
  }
  const out = [];
  for (const m of models.values()) {
    let cost = 0;
    let complete = true;
    for (const usage of task.usage) {
      const price = priceOf(m.rows, task, usage);
      if (price === undefined) { complete = false; break; }
      cost += price * (usage.unit === "1M_tokens" ? usage.amount / 1e6 : usage.amount);
    }
    if (complete && cost > 0) out.push({ provider: m.provider, model: m.model, cost });
  }
  return out.sort((a, b) => a.cost - b.cost);
}

export function historySeries(entries, model) {
  const rows = entries.filter((e) => e.model === model && isBase(e));
  const dates = [...new Set(rows.map((e) => e.observed_at.slice(0, 10)))].sort();
  const series = {};
  for (const direction of DIRECTIONS) {
    const byDate = new Map(rows.filter((e) => e.direction === direction).map((e) => [e.observed_at.slice(0, 10), e.price_usd]));
    if (!byDate.size) continue;
    let last = null;
    series[direction] = dates.map((d) => (last = byDate.get(d) ?? last));
  }
  return { dates, series };
}
