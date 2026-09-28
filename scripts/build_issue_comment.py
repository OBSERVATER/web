from __future__ import annotations

import json
from pathlib import Path

LABELS = {
    "pe_ttm": "PE-TTM",
    "pb": "PB-LF",
    "ps_ttm": "PS-TTM",
    "dyr": "股息率",
}


def fmt(metric: str, value):
    if value is None:
        return "—"
    if metric == "dyr":
        return f"{float(value):.2f}%"
    return f"{float(value):.2f}"


def main() -> None:
    data = json.loads(Path("data/latest.json").read_text(encoding="utf-8"))
    lines = [
        "@OBSERVATER",
        "",
        f"## 指数估值日报 · {data['generated_at']}",
        "",
        "| 指数 | 指标 | 当前值 | 10Y分位 | 机会值 | 中位数 | 危险值 | Z | 状态 | 来源 |",
        "|---|---|---:|---:|---:|---:|---:|---:|---|---|",
    ]

    for item in data.get("items", []):
        metric = item["metric"]
        current = fmt(metric, item.get("current"))
        stats = item.get("stats")
        if stats:
            percentile = f"{stats['percentile'] * 100:.2f}%"
            opportunity = fmt(metric, stats["opportunity"])
            median = fmt(metric, stats["median"])
            danger = fmt(metric, stats["danger"])
            zscore = f"{stats['zscore']:.2f}"
            state = item.get("zone", "—")
        else:
            rp = item.get("reported_percentile")
            percentile = f"{rp * 100:.2f}%*" if rp is not None else "历史不足"
            opportunity = median = danger = zscore = "—"
            state = "历史不足"

        lines.append(
            f"| {item['name']} | {LABELS.get(metric, metric)} | {current} | {percentile} | "
            f"{opportunity} | {median} | {danger} | {zscore} | {state} | {item['source']} |"
        )

    errors = data.get("errors") or []
    if errors:
        lines += ["", "### 数据源提示"]
        lines += [f"- {error}" for error in errors]

    lines += [
        "",
        "> *带星号的分位来自公开源站；只有历史样本达到阈值后，才启用本地10Y统计。*",
    ]
    Path("out/issue-comment.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
