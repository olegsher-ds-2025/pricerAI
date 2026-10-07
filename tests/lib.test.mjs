import test from "node:test";
import assert from "node:assert/strict";
import { pivotLlm, hideDatedSnapshots, taskCosts, historySeries, formatPrice } from "../site/lib.mjs";

const row = (model, direction, price, extra = {}) => ({
  provider: "P", model, service_type: "llm", unit: "1M_tokens", direction, tier: "standard",
  context_over: null, price_usd: price, url: "u", ...extra,
});

test("pivotLlm groups directions into one row per tier and context band", () => {
  const out = pivotLlm([row("m", "input", 1), row("m", "output", 4), row("m", "input", 2, { context_over: 200000 })]);
  assert.equal(out.length, 2);
  assert.deepEqual([out[0].input, out[0].output, out[1].input], [1, 4, 2]);
});

test("hideDatedSnapshots drops a dated model only when its alias exists", () => {
  const models = [{ provider: "P", model: "a" }, { provider: "P", model: "a-20250101" }, { provider: "P", model: "b-2025-01-01" }];
  assert.deepEqual(hideDatedSnapshots(models).map((m) => m.model), ["a", "b-2025-01-01"]);
});

test("taskCosts scales token amounts and sorts cheapest first", () => {
  const task = { service_type: "llm", usage: [
    { unit: "1M_tokens", direction: "input", amount: 1_000_000 },
    { unit: "1M_tokens", direction: "output", amount: 500_000 }] };
  const rows = [row("big", "input", 3), row("big", "output", 15), row("small", "input", 1), row("small", "output", 2),
    row("noout", "input", 0.1), row("big", "input", 6, { context_over: 200000 })];
  const out = taskCosts(task, rows);
  assert.deepEqual(out.map((o) => [o.model, o.cost]), [["small", 2], ["big", 10.5]]);
});

test("taskCosts handles per-unit services", () => {
  const task = { service_type: "image", usage: [{ unit: "image", direction: "output", amount: 3 }] };
  const rows = [{ ...row("img", "output", 0.04), service_type: "image", unit: "image" }];
  assert.equal(taskCosts(task, rows)[0].cost, 0.12);
});

test("historySeries carries the last price forward across dates", () => {
  const e = (d, direction, price) => ({ ...row("m", direction, price), observed_at: `${d}T00:00:00+00:00` });
  const { dates, series } = historySeries([e("2026-01-01", "input", 1), e("2026-01-01", "output", 4), e("2026-01-03", "input", 2)], "m");
  assert.deepEqual(dates, ["2026-01-01", "2026-01-03"]);
  assert.deepEqual(series.input, [1, 2]);
  assert.deepEqual(series.output, [4, 4]);
});

test("formatPrice", () => {
  assert.equal(formatPrice(0.15), "$0.15");
  assert.equal(formatPrice(undefined), "–");
});
