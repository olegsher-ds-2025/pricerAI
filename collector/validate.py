MAX_JUMP = 5
MIN_KEPT = 0.7


def row_key(row: dict) -> tuple:
    return (row["provider"], row["model"], row["service_type"], row["unit"],
            row["direction"], row["tier"], row["context_over"])


def reconcile(new: list[dict], old: list[dict]) -> tuple[list[dict], list[str]]:
    """Return rows to publish for one provider and a list of issues.

    An implausible fetch must never overwrite the last good data: a fetch that lost too many
    rows is rejected whole, and a single row whose price moved more than MAX_JUMP keeps its old price.
    """
    issues = []
    if not new:
        return old, ["fetch returned no rows; kept previous data"]
    if old and len(new) < MIN_KEPT * len(old):
        return old, [f"fetch returned {len(new)} rows vs {len(old)} before; kept previous data"]

    old_by_key = {row_key(r): r for r in old}
    accepted = []
    for row in new:
        prev = old_by_key.get(row_key(row))
        if prev and not (prev["price_usd"] / MAX_JUMP <= row["price_usd"] <= prev["price_usd"] * MAX_JUMP):
            issues.append(f"{row['model']} {row['direction']}/{row['tier']}: {prev['price_usd']} -> {row['price_usd']}; kept old price")
            row = prev
        accepted.append(row)
    return accepted, issues
