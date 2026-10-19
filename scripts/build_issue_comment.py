from __future__ import annotations

import json
import os
from pathlib import Path


GROUPS = ("低估", "偏低", "偏高", "高估", "历史不足", "数据过期", "数据不可用")
METRIC_NAMES = {"pe_ttm": "PE-TTM", "dyr": "股息率", "pb": "PB-LF", "ps_ttm": "PS-TTM"}


def fmt(metric: str, value: float | None) -> str:
    return "—" if value is None else f"{value:.2f}{'%' if metric == 'dyr' else ''}"


def detail(item: dict) -> str:
    metric = item["metric"]
    value = fmt(metric, item.get("current"))
    parts = [f"**{item['name']}**：{METRIC_NAMES.get(metric, metric)} {value}"]
    percentile = item.get("rating_percentile")
    if percentile is not None:
        parts.append(f"{item.get('percentile_origin') or '历史'}分位 {percentile * 100:.1f}%")
    mean = item.get("recent_4w_mean")
    diff = item.get("recent_4w_diff_pct")
    parts.append(
        f"近4周均线 {fmt(metric, mean)}（{diff:+.1f}%）"
        if mean is not None and diff is not None else "近4周均线 数据不足"
    )
    stats = item.get("stats") or {}
    median = stats.get("median")
    if median is not None:
        parts.append(f"10年中位数 {fmt(metric, median)}（{item['median_diff_pct']:+.1f}%）")
    parts.append(f"截至 {item.get('source_date', '—')} · {item.get('source', '未知源')}")
    if item.get("reference_current") is not None:
        parts.append(
            f"主源核对 {fmt(metric, item['reference_current'])}"
            f"（{item.get('reference_source', '—')}，{item.get('reference_date', '—')}）"
        )
    return " · ".join(parts)


def build(data: dict, manifest: list[dict], repo: str) -> str:
    day = data["generated_at"]
    rows = data.get("items") or []
    lines = ["@OBSERVATER", "", f"## 指数估值日报 · {day}", "",
             "采用同源当前值与同口径历史评估，股息率按反向分位判断；历史不足不强行评级。", ""]
    for group in GROUPS:
        selected = [x for x in rows if x.get("zone") == group]
        lines.append(f"### {group}（{len(selected)}）")
        lines.extend([f"- {detail(item)}" for item in selected] or ["- 暂无"])
        lines.append("")

    if manifest:
        lines += [f"<details><summary>展开详细估值图表（{len(manifest)}张）</summary>", ""]
        for card in manifest:
            url = (f"https://raw.githubusercontent.com/{repo}/main/"
                   f"reports/{day}/{card['id']}.png?v={day}")
            lines += [f"#### {card['name']}", f"![{card['name']}估值图]({url})", ""]
        lines += ["</details>", ""]

    warnings = (data.get("errors") or []) + (data.get("source_warnings") or [])
    if warnings:
        lines += ["<details><summary>数据源提示</summary>", ""]
        lines.extend(f"- {warning}" for warning in warnings)
        lines += ["", "</details>", ""]
    lines += ["> 统计使用至多十年周频数据；不同数据源、权重口径不混算。"
              "近4周均线不足4个有效周样本时不计算。", ""]
    return "\n".join(lines)


def main() -> None:
    data = json.loads(Path("data/latest.json").read_text(encoding="utf-8"))
    manifest = json.loads(Path("out/cards/manifest.json").read_text(encoding="utf-8"))
    repo = os.getenv("GITHUB_REPOSITORY", "OBSERVATER/web")
    Path("out/issue-comment.md").write_text(build(data, manifest, repo), encoding="utf-8")


if __name__ == "__main__":
    main()
