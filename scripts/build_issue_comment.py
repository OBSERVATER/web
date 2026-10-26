"""Human-readable Issue #1 report: one section per index plus durable alerts."""
from __future__ import annotations

import json
import os
from pathlib import Path

METRIC_NAMES = {"pe_ttm": "PE-TTM", "dyr": "股息率",
                "pb": "PB-LF", "ps_ttm": "PS-TTM"}
GROUPS = ("低估", "偏低", "偏高", "高估", "历史不足", "数据过期", "数据不可用")


def fmt(metric: str, value: float | None) -> str:
    if value is None:
        return "数据不足"
    return f"{float(value):.2f}{'%' if metric == 'dyr' else ''}"


def percent(value: float | None, signed: bool = False) -> str:
    if value is None:
        return "数据不足"
    value = float(value)
    if signed and 0 < abs(value) < 0.005:
        return f"{value:+.3f}%"
    return f"{value:+.2f}%" if signed else f"{value:.2f}%"


def instrument_section(item: dict, price: dict) -> list[str]:
    metric = item["metric"]
    lines = [f"### {item['name']}", ""]
    close = price.get("close")
    triggered = price.get("triggered_drop_pct")
    shown_drop = triggered if triggered is not None else price.get("drawdown_pct")
    lines.extend([
        f"- 最新收盘：{float(close):,.2f}（{price.get('date') or '—'}）"
        if close is not None else "- 最新收盘：数据暂不可用",
        f"- **较上次：{percent(price.get('change_pct'), True)}**"
        + (f"（对比 {price['previous_date']}）" if price.get("previous_date") else ""),
        f"- **本轮累计跌幅：{percent(shown_drop)}**"
        + ("（已触发，触发后已重置基准）" if triggered is not None else ""),
    ])
    if price.get("status") != "正常":
        lines.append(f"- 价格数据状态：{price.get('status') or '数据不可用'}")
    lines += [f"- 当前估值：{METRIC_NAMES.get(metric, metric)} {fmt(metric, item.get('current'))}",
              f"- 估值状态：{item.get('zone', '数据不可用')}"]
    percentile = item.get("rating_percentile")
    lines.append(
        f"- 历史分位：{float(percentile) * 100:.2f}%（{item.get('percentile_origin') or '历史'}）"
        if percentile is not None else "- 历史分位：数据不足")
    mean, diff = item.get("recent_4w_mean"), item.get("recent_4w_diff_pct")
    lines.append(f"- 近4周均线：{fmt(metric, mean)}"
                 + (f"（{percent(diff, True)}）" if diff is not None else ""))
    stats = item.get("stats") or {}
    median, meddiff = stats.get("median"), item.get("median_diff_pct")
    lines.append(f"- 10年中位数：{fmt(metric, median)}"
                 + (f"（{percent(meddiff, True)}）" if meddiff is not None else ""))
    if stats:
        lines.append(
            f"- 估值参考：机会 {fmt(metric, stats.get('opportunity'))}"
            f" · 危险 {fmt(metric, stats.get('danger'))}"
            f" · 均值 {fmt(metric, stats.get('mean'))}"
            f" · Z-Score {stats.get('zscore', 0):+.2f}")
    lines.append(f"- 估值来源：{item.get('source') or '未知'}（{item.get('source_date') or '—'}）")
    if item.get("reference_current") is not None:
        lines.append(
            f"- 主源核对：{fmt(metric, item['reference_current'])}"
            f"（{item.get('reference_source') or '未知源'}，{item.get('reference_date') or '—'}；独立口径）")
        if item.get("current") is not None:
            difference = float(item["current"]) - float(item["reference_current"])
            unit = "个百分点" if metric == "dyr" else "（估值单位）"
            lines.append(
                f"- 异源差异：{difference:+.2f}{unit}（仅供核对，不混合计算）")
    lines.append("")
    return lines


def build(data: dict, prices: dict, manifest: list[dict], repo: str) -> str:
    day = data["generated_at"]
    price_lookup = {p["instrument_id"]: p for p in (prices.get("items") or [])}
    rows = data.get("items") or []
    lines = ["@OBSERVATER", "", f"## 指数估值与跌幅日报 · {day}", "",
             "### 估值汇总", ""]
    for group in GROUPS:
        names = [x["name"] for x in rows if x.get("zone") == group]
        lines.append(f"- {group}：{'、'.join(names) if names else '暂无'}")
    lines += ["", "> 估值与指数收盘价独立计算；不同数据源与估值口径不混算。", "", "---", ""]
    for item in rows:
        lines += instrument_section(item, price_lookup.get(item["instrument_id"], {}))

    pending = prices.get("pending") or []
    lines += ["---", ""]
    if pending:
        alerts = "、".join(
            f"{e['name']}（{percent(e['drop_pct'])}，{e['day']}）" for e in pending)
        lines += [f"> **本次累计跌幅达到4%的指数：{alerts}**",
                  ">", "> 触发事件已持久化，下一轮以触发时的收盘价重新计算。", ""]
    else:
        lines += ["> 本次无新增4%跌幅触发。", ""]
    # Markers allow crash/retry detection after an Issue comment succeeded.
    for event in pending:
        lines.append(f"<!-- valuation-event:{event['id']} -->")
    lines.append(f"<!-- valuation-report:{day} -->")
    lines.append("")

    if manifest:
        lines += [f"<details><summary>展开详细估值图表（{len(manifest)}张）</summary>", ""]
        for card in manifest:
            url = (f"https://raw.githubusercontent.com/{repo}/main/"
                   f"reports/{day}/{card['id']}.png?v={day}")
            lines += [f"#### {card['name']}", f"![{card['name']}估值图]({url})", ""]
        lines += ["</details>", ""]
    warnings = ((data.get("errors") or []) + (data.get("source_warnings") or [])
                + (prices.get("warnings") or []))
    if warnings:
        lines += ["<details><summary>数据源提示</summary>", ""]
        lines += [f"- {warning}" for warning in warnings]
        lines += ["", "</details>", ""]
    lines += ["> 10年历史不足则标注数据不足；价格点位、有效交易日和估值日期分别显示。", ""]
    return "\n".join(lines)


def main() -> None:
    data = json.loads(Path("data/latest.json").read_text(encoding="utf-8"))
    prices = json.loads(Path("out/price_snapshot.json").read_text(encoding="utf-8"))
    manifest = json.loads(Path("out/cards/manifest.json").read_text(encoding="utf-8"))
    repo = os.getenv("GITHUB_REPOSITORY", "OBSERVATER/web")
    Path("out/issue-comment.md").write_text(build(data, prices, manifest, repo), encoding="utf-8")


if __name__ == "__main__":
    main()
