from __future__ import annotations

import html
from dataclasses import asdict
from datetime import date

from .models import Instrument, METRIC_LABELS, Observation, StatSnapshot


def format_value(metric: str, value: float | None) -> str:
    if value is None:
        return "—"
    if metric == "dyr":
        return f"{value:.2f}%"
    return f"{value:.2f}"


def zone(snapshot: StatSnapshot) -> str:
    if snapshot.higher_is_cheaper:
        if snapshot.current >= snapshot.opportunity:
            return "机会区"
        if snapshot.current <= snapshot.danger:
            return "危险区"
    else:
        if snapshot.current <= snapshot.opportunity:
            return "机会区"
        if snapshot.current >= snapshot.danger:
            return "危险区"
    return "中性"


def build_html(
    report_day: date,
    rows: list[tuple[Instrument, str, Observation | None, StatSnapshot | None]],
    minimum_history_weeks: int = 450,
    errors: list[str] | None = None,
) -> str:
    body_rows = []
    opportunity_count = 0
    for instrument, metric, current_obs, snapshot in rows:
        label = METRIC_LABELS.get(metric, metric)
        if current_obs is None:
            body_rows.append(
                f"<tr><td>{html.escape(instrument.name)}</td><td>{html.escape(label)}</td>"
                "<td>—</td><td colspan='9'>当前数据源暂不可用</td></tr>"
            )
            continue

        current = format_value(metric, current_obs.value)
        point = "—" if current_obs.point is None else f"{current_obs.point:,.2f}"
        source = html.escape(current_obs.source)

        if snapshot is None:
            reported = (
                f"{current_obs.reported_percentile * 100:.2f}%（源站）"
                if current_obs.reported_percentile is not None else "历史不足"
            )
            body_rows.append(
                "<tr>"
                f"<td><strong>{html.escape(instrument.name)}</strong><br><small>{html.escape(instrument.code)}</small></td>"
                f"<td>{html.escape(label)}</td><td>{current}</td><td>{reported}</td>"
                f"<td colspan='6'>尚未积累满 {minimum_history_weeks} 个周样本，不伪造10Y统计</td>"
                f"<td>{point}</td><td><small>{source}</small></td>"
                "</tr>"
            )
            continue

        state = zone(snapshot)
        if state == "机会区":
            opportunity_count += 1
        badge_class = {"机会区": "good", "危险区": "bad", "中性": "neutral"}[state]
        body_rows.append(
            "<tr>"
            f"<td><strong>{html.escape(instrument.name)}</strong><br><small>{html.escape(instrument.code)}</small></td>"
            f"<td>{html.escape(label)}</td><td>{current}</td>"
            f"<td>{snapshot.percentile * 100:.2f}%</td>"
            f"<td>{format_value(metric, snapshot.opportunity)}</td>"
            f"<td>{format_value(metric, snapshot.median)}</td>"
            f"<td>{format_value(metric, snapshot.danger)}</td>"
            f"<td>{snapshot.mean:.2f}</td><td>{snapshot.zscore:.2f}</td>"
            f"<td><span class='badge {badge_class}'>{state}</span></td>"
            f"<td>{point}</td><td><small>{source}</small></td></tr>"
        )

    error_html = ""
    if errors:
        error_html = "<div class='errors'><strong>数据源提示：</strong><br>" + "<br>".join(
            html.escape(item) for item in errors
        ) + "</div>"

    return f"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<style>
body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI','PingFang SC','Microsoft YaHei',sans-serif;background:#f5f5f7;color:#1d1d1f;margin:0;padding:24px}}
.card{{max-width:1200px;margin:auto;background:#fff;border-radius:16px;padding:22px;box-shadow:0 1px 8px rgba(0,0,0,.06)}}
h1{{font-size:22px;margin:0 0 6px}}p{{color:#666;margin:4px 0 18px}}
table{{width:100%;border-collapse:collapse;font-size:14px}}th,td{{padding:10px 8px;border-bottom:1px solid #ececec;text-align:right;white-space:nowrap}}th:first-child,td:first-child,th:nth-child(2),td:nth-child(2){{text-align:left}}
th{{font-size:12px;color:#6e6e73;background:#fafafa}}small{{color:#8e8e93}}
.badge{{display:inline-block;padding:3px 8px;border-radius:999px;font-size:12px}}.good{{background:#e8f7ee;color:#16733d}}.bad{{background:#fdecec;color:#b42318}}.neutral{{background:#f0f0f2;color:#555}}
.errors{{font-size:12px;background:#fff8e6;border-radius:10px;padding:10px;margin:12px 0;color:#7a5200}}
.footer{{font-size:12px;color:#8e8e93;margin-top:16px;line-height:1.6}}
@media(max-width:800px){{.card{{padding:12px;overflow:auto}}body{{padding:8px}}}}
</style></head>
<body><div class="card">
<h1>估值监控日报 · {report_day.isoformat()}</h1>
<p>匿名公开数据源；最多10年周频统计。当前共有 <strong>{opportunity_count}</strong> 项进入机会区。</p>
{error_html}
<table><thead><tr><th>指数</th><th>指标</th><th>当前值</th><th>10Y分位</th><th>机会值</th><th>中位数</th><th>危险值</th><th>均值</th><th>Z</th><th>状态</th><th>点位</th><th>来源</th></tr></thead>
<tbody>{''.join(body_rows)}</tbody></table>
<div class="footer">不需要任何行情服务账号或 API Token。历史覆盖不足时只展示可靠的当前值/源站分位，不把短历史伪装成10年统计。</div>
</div></body></html>"""


def snapshot_to_dict(snapshot: StatSnapshot) -> dict:
    return asdict(snapshot)
