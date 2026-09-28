from __future__ import annotations

import argparse

from valuation_monitor.config import load_config
from valuation_monitor.public_sources import PublicDataClient


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
    args = parser.parse_args()

    _, instruments = load_config(args.config)
    by_id = {x.id: x for x in instruments}
    client = PublicDataClient()

    print("| 指数 | 指标 | 参考值 | 公共源值 | 偏差 | 来源 |")
    print("|---|---|---:|---:|---:|---|")
    for instrument_id, metric_key, expected in BENCHMARKS:
        instrument = by_id[instrument_id]
        try:
            rows = client.fetch_latest(instrument)
            row = next((x for x in rows if x.metric == metric_key), None)
        except Exception as exc:
            print(f"| {instrument.name} | {metric_key} | {expected:.4g} | — | — | ERROR: {exc} |")
            continue

        if row is None:
            print(f"| {instrument.name} | {metric_key} | {expected:.4g} | — | — | no value |")
            continue
        delta_pct = (row.value / expected - 1) * 100
        print(
            f"| {instrument.name} | {metric_key} | {expected:.4g} | "
            f"{row.value:.4g} | {delta_pct:+.2f}% | {row.source} |"
        )


if __name__ == "__main__":
    main()
