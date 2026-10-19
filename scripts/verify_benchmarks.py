from __future__ import annotations

import argparse
from valuation_monitor.config import load_config
from valuation_monitor.public_sources import PublicDataClient

# Dated historical checkpoints are comparisons, never calibration constants.
BENCHMARKS = {
    ("value100", "pe_ttm"): 8.89,
    ("csi_dividend", "dyr"): 4.26,
    ("sp500", "pe_ttm"): 25.45,
}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="watchlist.yaml")
    args = parser.parse_args()
    _, instruments = load_config(args.config)
    client = PublicDataClient()
    print("| 指数 | 指标 | 旧参考值 | 当前公开源值 | 偏差 | 来源 |")
    print("|---|---|---:|---:|---:|---|")
    for instrument in instruments:
        for metric in instrument.metrics:
            ref = BENCHMARKS.get((instrument.id, metric.key))
            try:
                rows = client.fetch_latest(instrument)
                row = next((x for x in rows if x.metric == metric.key), None)
            except Exception as exc:
                print(f"| {instrument.name} | {metric.key} | — | — | — | ERROR: {exc} |")
                continue
            if row is None:
                print(f"| {instrument.name} | {metric.key} | — | — | — | 无数据 |")
                continue
            delta = f"{(row.value / ref - 1) * 100:+.2f}%" if ref else "未设置旧参考"
            print(f"| {instrument.name} | {metric.key} | "
                  f"{f'{ref:.4g}' if ref else '—'} | {row.value:.4g} | "
                  f"{delta} | {row.source} |")


if __name__ == "__main__":
    main()
