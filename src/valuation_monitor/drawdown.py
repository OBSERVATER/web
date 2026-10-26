"""Independent daily index closing prices and persistent 4% drawdown alerts."""
from __future__ import annotations

import argparse
import csv
import json
import math
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import yaml

from .calendar_gate import last_closed_session
from .price_sources import PRICES, fetch_daily

HISTORY_FIELDS = ("day", "instrument_id", "name", "close", "source")
THRESHOLD = 4.0


def read_json(path: str, default: dict) -> dict:
    file = Path(path)
    return json.loads(file.read_text(encoding="utf-8")) if file.exists() else default


def load_daily_history(path: str) -> list[dict]:
    file = Path(path)
    if not file.exists():
        return []
    with file.open(encoding="utf-8", newline="") as handle:
        result = []
        for item in csv.DictReader(handle):
            try:
                price = float(item["close"])
                date.fromisoformat(item["day"])
                if math.isfinite(price) and price > 0:
                    result.append({**item, "close": price})
            except (KeyError, TypeError, ValueError):
                continue
        return result


def save_daily_history(path: str, rows: list[dict]) -> None:
    file = Path(path)
    file.parent.mkdir(parents=True, exist_ok=True)
    with file.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=HISTORY_FIELDS)
        writer.writeheader()
        for row in sorted(rows, key=lambda r: (r["instrument_id"], r["day"])):
            writer.writerow({field: row[field] for field in HISTORY_FIELDS})


def merge_prices(existing: list[dict], incoming: list[dict]) -> tuple[list[dict], list[str]]:
    """Never silently mix or overwrite different point series for the same index/day."""
    prices = {(r["instrument_id"], r["day"]): r for r in existing}
    warnings = []
    for row in incoming:
        key = (row["instrument_id"], row["day"])
        old = prices.get(key)
        if old and (old["source"] != row["source"]
                    or not math.isclose(float(old["close"]), float(row["close"]), rel_tol=1e-7)):
            warnings.append(f"{row['name']} {row['day']}: price source/value conflict; retained stored close")
            continue
        prices[key] = row
    return sorted(prices.values(), key=lambda r: (r["instrument_id"], r["day"])), warnings


def advance_cycle(state: dict | None, observations: list[dict], instrument_id: str,
                  name: str, pending: list[dict]) -> dict | None:
    """Initialise at the latest close; on subsequent runs replay strictly newer closes."""
    if not observations:
        return state
    ordered = sorted(observations, key=lambda r: r["day"])
    if state is None:
        last = ordered[-1]
        return {"peak": last["close"], "last_close": last["close"],
                "last_day": last["day"], "source": last["source"]}
    if state.get("source") != ordered[-1]["source"]:
        # Price series may not be switched mid-episode.
        return state
    for row in ordered:
        if row["day"] <= state["last_day"]:
            continue
        close = float(row["close"])
        peak = max(float(state["peak"]), close)
        fall = (peak - close) / peak * 100.0
        if fall + 1e-10 >= THRESHOLD:
            event_id = f"{instrument_id}:{row['day']}:{peak:.8f}:{close:.8f}"
            if not any(event["id"] == event_id for event in pending):
                pending.append({"id": event_id, "instrument_id": instrument_id,
                                "name": name, "day": row["day"],
                                "drop_pct": fall, "close": close})
            peak = close  # Reset only after the event has been durably added to the outbox.
        state = {"peak": peak, "last_close": close, "last_day": row["day"],
                 "source": row["source"]}
    return state


def calculate(config: dict, history: list[dict], state_data: dict,
              published_ids: set[str], now: datetime) -> tuple[dict, dict]:
    """Pure state transition. The scheduler persists the outbox before publication."""
    new_state = {"version": 1, "cycles": dict(state_data.get("cycles") or {}),
                 "pending": [dict(x) for x in state_data.get("pending", [])
                             if x["id"] not in published_ids]}
    items = []
    for instrument in config.get("instruments", []):
        identifier, name, market = instrument["id"], instrument["name"], instrument["market"]
        entries = sorted((row for row in history if row["instrument_id"] == identifier),
                         key=lambda row: row["day"])
        state = advance_cycle(new_state["cycles"].get(identifier), entries,
                              identifier, name, new_state["pending"])
        if state:
            new_state["cycles"][identifier] = state
        latest = entries[-1] if entries else None
        previous = entries[-2] if len(entries) >= 2 else None
        last_session = last_closed_session(market, now)
        fresh = bool(latest and last_session and latest["day"] == last_session.isoformat())
        if not latest:
            status = "数据不可用"
        elif not fresh:
            status = "暂无新收盘"
        else:
            status = "正常"
        # A stale quote may be displayed, but is never represented as a new daily update.
        change = ((float(latest["close"]) / float(previous["close"]) - 1) * 100
                  if latest and previous and latest["source"] == previous["source"] else None)
        drawdown = ((float(state["peak"]) - float(state["last_close"]))
                    / float(state["peak"]) * 100 if state else None)
        items.append({"instrument_id": identifier, "name": name, "market": market,
                      "date": latest["day"] if latest else None,
                      "previous_date": previous["day"] if previous else None,
                      "close": latest["close"] if latest else None,
                      "change_pct": change, "drawdown_pct": max(0.0, drawdown) if drawdown is not None else None,
                      "peak": state["peak"] if state else None,
                      "status": status, "source": latest["source"] if latest else None})
    return new_state, {"generated_at": now.date().isoformat(),
                       "items": items, "pending": list(new_state["pending"])}


def fetch_prices(config: dict, history: list[dict], state_data: dict,
                 now: datetime) -> tuple[list[dict], list[str]]:
    incoming, warnings = [], []
    today = now.astimezone(ZoneInfo("Asia/Shanghai")).date()
    for spec in config.get("instruments", []):
        identifier = spec["id"]
        if identifier not in PRICES:
            warnings.append(f"{spec['name']}: no validated price source")
            continue
        current = [r for r in history if r["instrument_id"] == identifier]
        initial_date = PRICES[identifier][1]
        begin = (max(initial_date, date.fromisoformat(max(r["day"] for r in current))
                     - timedelta(days=7)) if current else initial_date)
        last_completed = last_closed_session(spec["market"], now)
        if last_completed is None:
            warnings.append(f"{spec['name']}: market session unavailable")
            continue
        try:
            rows = fetch_daily(identifier, begin, min(today, last_completed))
            for r in rows:
                r["name"] = spec["name"]
            incoming.extend(rows)
        except Exception as exc:
            warnings.append(f"{spec['name']}: daily history unavailable: {exc}")
    return incoming, warnings


def run(config_path: str, history_path: str, state_path: str,
        snapshot_path: str, published_path: str, now: datetime | None = None) -> dict:
    config = yaml.safe_load(Path(config_path).read_text(encoding="utf-8")) or {}
    now = now or datetime.now(ZoneInfo("Asia/Shanghai"))
    state = read_json(state_path, {"version": 1, "cycles": {}, "pending": []})
    history = load_daily_history(history_path)
    incoming, warnings = fetch_prices(config, history, state, now)
    history, conflicts = merge_prices(history, incoming)
    published = set(read_json(published_path, {}).get("published_events", []))
    state, snapshot = calculate(config, history, state, published, now)
    snapshot["warnings"] = warnings + conflicts
    save_daily_history(history_path, history)
    Path(state_path).parent.mkdir(parents=True, exist_ok=True)
    Path(state_path).write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    Path(snapshot_path).parent.mkdir(parents=True, exist_ok=True)
    Path(snapshot_path).write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")
    return snapshot


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="watchlist.yaml")
    parser.add_argument("--history", default="data/daily_prices.csv")
    parser.add_argument("--state", default="data/drawdown_state.json")
    parser.add_argument("--snapshot", default="out/price_snapshot.json")
    parser.add_argument("--published", default="out/published-issue.json")
    args = parser.parse_args()
    run(args.config, args.history, args.state, args.snapshot, args.published)
