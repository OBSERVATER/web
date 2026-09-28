from __future__ import annotations

import argparse
from datetime import date

from valuation_monitor.config import load_config
from valuation_monitor.lixinger import LixingerClient


BENCHMARKS = [
    ("value100", "pe_ttm", 8.89),
    ("csi_dividend", "dyr", 4.26),
    ("sp500", "pe_ttm", 25.45),
    ("hscgsi", "pb", 2.29),
    ("pharma50", "pb", 3.91),
    ("hstech", "ps_ttm", 1.50),
]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="watchlist.yaml")
    parser.add_argument("--date", default="2026-09-28")
    args = parser.parse_args()

    target = date.fromisoformat(args.date)
    _, instruments = load_config(args.config)
    by_id = {x.id: x for x in instruments}
    client = LixingerClient()

    print("| 指数 | 指标 | 参考值 | 数据源值 | 偏差 |")
    print("|---|---|---:|---:|---:|")
    for instrument_id, metric_key, expected in BENCHMARKS:
        instrument = by_id[instrument_id]
        rows = client.fetch_on_date(instrument, target)
        actual = next((x.value for x in rows if x.metric == metric_key), None)
        if actual is None:
            print(f"| {instrument.name} | {metric_key} | {expected:.4g} | — | — |")
            continue
        delta_pct = (actual / expected - 1) * 100
        print(f"| {instrument.name} | {metric_key} | {expected:.4g} | {actual:.4g} | {delta_pct:+.2f}% |")


if __name__ == "__main__":
    main()
