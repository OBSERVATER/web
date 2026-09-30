from __future__ import annotations

import csv
import json
import math
from datetime import date
from pathlib import Path

import yaml
from PIL import Image, ImageDraw, ImageFont


WIDTH = 1080
HEIGHT = 720
PANEL_X = 20
PANEL_Y = 88
PANEL_W = 1040
PANEL_H = 602

BG = "#F1F1F1"
PANEL = "#FFFFFF"
TEXT = "#202124"
MUTED = "#73777C"
GRID = "#D9DDE2"
CYAN = "#7FC7D2"
BLUE = "#2C6599"
RED = "#B6372D"
GREEN = "#3C9C69"
GRAY_DASH = "#858B91"
LIGHT_DASH = "#BCC2C7"


def find_font(bold: bool = False) -> str:
    candidates = [
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc" if bold else "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJKsc-Bold.otf" if bold else "/usr/share/fonts/opentype/noto/NotoSansCJKsc-Regular.otf",
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc" if bold else "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
    ]
    for path in candidates:
        if Path(path).exists():
            return path
    for path in Path("/usr/share/fonts").rglob("*NotoSansCJK*"):
        if path.suffix.lower() in {".ttf", ".otf", ".ttc"}:
            if bold and "Bold" in path.name:
                return str(path)
            if not bold and ("Regular" in path.name or "Medium" not in path.name):
                return str(path)
    raise RuntimeError("No Noto CJK font found")


def fonts():
    r = find_font(False)
    b = find_font(True)
    return {
        "head": ImageFont.truetype(b, 32),
        "head_code": ImageFont.truetype(r, 23),
        "metric_title": ImageFont.truetype(b, 26),
        "label": ImageFont.truetype(r, 22),
        "value": ImageFont.truetype(b, 22),
        "axis": ImageFont.truetype(r, 16),
        "legend": ImageFont.truetype(b, 16),
        "small": ImageFont.truetype(r, 15),
        "empty": ImageFont.truetype(r, 24),
    }


def txt(draw, xy, value, font, fill=TEXT, anchor=None):
    draw.text(xy, str(value), font=font, fill=fill, anchor=anchor)


def load_watchlist(path: Path):
    return (yaml.safe_load(path.read_text(encoding="utf-8")) or {}).get("instruments", [])


def load_history(path: Path):
    if not path.exists():
        return []
    rows = []
    with path.open("r", encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            try:
                rows.append({
                    "day": date.fromisoformat(row["day"]),
                    "instrument_id": row["instrument_id"],
                    "metric": row["metric"],
                    "value": float(row["value"]),
                    "point": float(row["point"]) if row.get("point") else None,
                    "reported_percentile": float(row["reported_percentile"]) if row.get("reported_percentile") else None,
                })
            except Exception:
                pass
    return rows


def metric_label(metric):
    return {
        "pe_ttm": "市盈率TTM",
        "pb": "市净率LF",
        "ps_ttm": "市销率TTM",
        "dyr": "股息率",
    }.get(metric, metric)


def fmt(metric, value):
    if value is None:
        return "—"
    if metric == "dyr":
        return f"{float(value):.2f}%"
    return f"{float(value):.2f}"


def nice_range(values, padding=0.08):
    vals = [float(v) for v in values if v is not None and math.isfinite(float(v))]
    if not vals:
        return 0.0, 1.0
    lo, hi = min(vals), max(vals)
    if lo == hi:
        pad = abs(lo) * 0.1 or 1.0
        return lo - pad, hi + pad
    span = hi - lo
    return lo - span * padding, hi + span * padding


def dashed_hline(draw, y, x1, x2, fill, width=3, dash=12, gap=8):
    x = x1
    while x < x2:
        xe = min(x + dash, x2)
        draw.line((x, y, xe, y), fill=fill, width=width)
        x = xe + gap


def draw_stat(draw, x_label, x_value, y, label, value, f, muted=False):
    txt(draw, (x_label, y), label, f["label"], MUTED if muted else TEXT)
    txt(draw, (x_value, y), value, f["value"], TEXT, anchor="ra")


def draw_summary_card(draw, box, label, value, f, accent=TEXT):
    x1, y1, x2, y2 = box
    draw.rounded_rectangle(box, radius=8, fill="#F7F8FA")
    txt(draw, (x1 + 14, y1 + 12), label, f["small"], MUTED)
    txt(draw, (x1 + 14, y2 - 13), value, f["value"], accent, anchor="ls")


def line_points(series, x1, y1, x2, y2, min_day, max_day, lo, hi, key):
    total_days = max(1, (max_day - min_day).days)
    pts = []
    for row in series:
        value = row.get(key)
        if value is None:
            continue
        x = x1 + ((row["day"] - min_day).days / total_days) * (x2 - x1)
        y = y2 - ((float(value) - lo) / max(1e-12, hi - lo)) * (y2 - y1)
        pts.append((x, y))
    return pts


def draw_percentile_chart(draw, box, rows, f):
    x1, y1, x2, y2 = box
    draw.rectangle(box, fill="#FBFBFB", outline=GRID, width=1)
    pct_rows = sorted([r for r in rows if r.get("reported_percentile") is not None], key=lambda r: r["day"])
    if len(pct_rows) < 3:
        txt(draw, ((x1 + x2) / 2, (y1 + y2) / 2), "暂无可用历史序列", f["empty"], MUTED, anchor="mm")
        return

    min_day = min(r["day"] for r in pct_rows)
    max_day = max(r["day"] for r in pct_rows)
    total_days = max(1, (max_day - min_day).days)

    for pct in (0, 25, 50, 75, 100):
        y = y2 - pct / 100 * (y2 - y1)
        draw.line((x1, y, x2, y), fill=GRID, width=1)
        txt(draw, (x1 - 12, y), f"{pct}%", f["axis"], MUTED, anchor="rm")

    for pct, color, width in ((20, GREEN, 3), (50, GRAY_DASH, 3), (80, RED, 3)):
        y = y2 - pct / 100 * (y2 - y1)
        dashed_hline(draw, y, x1, x2, color, width=width)

    years = list(range(min_day.year, max_day.year + 1))
    if len(years) > 7:
        step = max(1, math.ceil(len(years) / 6))
        years = years[::step]
        if years[-1] != max_day.year:
            years.append(max_day.year)
    for year in years:
        d = date(year, 1, 1)
        d = min(max(d, min_day), max_day)
        x = x1 + ((d - min_day).days / total_days) * (x2 - x1)
        txt(draw, (x, y2 + 22), str(year)[2:], f["axis"], MUTED, anchor="ma")

    pts = []
    for row in pct_rows:
        x = x1 + ((row["day"] - min_day).days / total_days) * (x2 - x1)
        y = y2 - float(row["reported_percentile"]) * (y2 - y1)
        pts.append((x, y))
    if len(pts) >= 2:
        # Percentile history is also rendered as an area chart. This is a
        # 0-100% percentile series, NOT a fabricated raw PS/PE/PB series.
        polygon = [(pts[0][0], y2), *pts, (pts[-1][0], y2)]
        draw.polygon(polygon, fill=CYAN)
        draw.line(pts, fill="#58B5C2", width=3)

    point_rows = [r for r in pct_rows if r.get("point") is not None]
    if len(point_rows) >= 3:
        p_lo, p_hi = nice_range([r["point"] for r in point_rows], 0.06)
        p_pts = line_points(point_rows, x1, y1, x2, y2, min_day, max_day, p_lo, p_hi, "point")
        if p_pts:
            draw.line(p_pts, fill=BLUE, width=3)
        for i in range(5):
            frac = i / 4
            y = y2 - frac * (y2 - y1)
            value = p_lo + frac * (p_hi - p_lo)
            txt(draw, (x2 + 12, y), f"{value:,.0f}", f["axis"], MUTED, anchor="lm")


def draw_chart(draw, box, metric, rows, stats, f):
    x1, y1, x2, y2 = box
    draw.rectangle(box, fill="#FBFBFB", outline=GRID, width=1)

    metric_rows = sorted(
        [r for r in rows if r.get("value") is not None and float(r.get("value") or 0) > 0],
        key=lambda r: r["day"],
    )
    pct_rows = [r for r in rows if r.get("reported_percentile") is not None]
    if len(metric_rows) < 12:
        if len(pct_rows) >= 12:
            draw_percentile_chart(draw, box, rows, f)
        else:
            txt(draw, ((x1 + x2) / 2, (y1 + y2) / 2 - 22),
                "历史原始估值不足，暂不绘制曲线", f["empty"], MUTED, anchor="mm")
            txt(draw, ((x1 + x2) / 2, (y1 + y2) / 2 + 18),
                f"当前已收集 {len(metric_rows)} 个有效周样本 / 目标 450 周",
                f["label"], MUTED, anchor="mm")
        return

    min_day = min(r["day"] for r in metric_rows)
    max_day = max(r["day"] for r in metric_rows)
    metric_values = [r["value"] for r in metric_rows]

    overlays = []
    if stats:
        overlays.extend([
            stats.get("minimum"),
            stats.get("maximum"),
            stats.get("opportunity"),
            stats.get("median"),
            stats.get("danger"),
        ])
    lo, hi = nice_range(metric_values + overlays, 0.06)

    # horizontal grid + left labels
    for i in range(5):
        frac = i / 4
        y = y2 - frac * (y2 - y1)
        draw.line((x1, y, x2, y), fill=GRID, width=1)
        value = lo + frac * (hi - lo)
        label = f"{value:.2f}" if metric != "dyr" else f"{value:.2f}%"
        txt(draw, (x1 - 12, y), label, f["axis"], MUTED, anchor="rm")

    # x-axis year labels
    start_y = min_day.year
    end_y = max_day.year
    years = list(range(start_y, end_y + 1))
    if len(years) > 7:
        step = max(1, math.ceil(len(years) / 6))
        years = years[::step]
        if years[-1] != end_y:
            years.append(end_y)
    total_days = max(1, (max_day - min_day).days)
    for year in years:
        d = date(year, 1, 1)
        if d < min_day:
            d = min_day
        if d > max_day:
            d = max_day
        x = x1 + ((d - min_day).days / total_days) * (x2 - x1)
        txt(draw, (x, y2 + 22), str(year)[2:], f["axis"], MUTED, anchor="ma")

    metric_pts = line_points(metric_rows, x1, y1, x2, y2, min_day, max_day, lo, hi, "value")
    if metric_pts:
        polygon = [(metric_pts[0][0], y2), *metric_pts, (metric_pts[-1][0], y2)]
        draw.polygon(polygon, fill=CYAN)
        draw.line(metric_pts, fill="#58B5C2", width=2)

    if stats:
        guides = [
            ("danger", RED, 4),
            ("median", GRAY_DASH, 3),
            ("opportunity", GREEN, 4),
        ]
        for key, color, width in guides:
            val = stats.get(key)
            if val is None or not (lo <= val <= hi):
                continue
            y = y2 - ((val - lo) / (hi - lo)) * (y2 - y1)
            dashed_hline(draw, y, x1, x2, color, width=width)

    point_rows = [r for r in rows if r.get("point") is not None]
    if len(point_rows) >= 3:
        p_lo, p_hi = nice_range([r["point"] for r in point_rows], 0.06)
        p_pts = line_points(point_rows, x1, y1, x2, y2, min_day, max_day, p_lo, p_hi, "point")
        if p_pts:
            draw.line(p_pts, fill=BLUE, width=3)
        for i in range(5):
            frac = i / 4
            y = y2 - frac * (y2 - y1)
            value = p_lo + frac * (p_hi - p_lo)
            txt(draw, (x2 + 12, y), f"{value:,.0f}", f["axis"], MUTED, anchor="lm")


def render_one(out_path: Path, report_day: str, spec, item, history, f):
    image = Image.new("RGB", (WIDTH, HEIGHT), BG)
    draw = ImageDraw.Draw(image)

    name = spec["name"]
    code = spec["code"]
    metric = next(iter((spec.get("metrics") or {}).keys()), item.get("metric") if item else "")
    current = item.get("current") if item else None
    point = item.get("point") if item else None
    as_of = date.fromisoformat(report_day)
    relevant = [
        r for r in history
        if r["instrument_id"] == spec["id"] and r["metric"] == metric
        and r["day"] <= as_of
    ]
    relevant.sort(key=lambda r: r["day"])
    raw_history_count = sum(
        1 for r in relevant
        if r.get("value") is not None and float(r.get("value") or 0) > 0
    )
    pct_history_count = sum(1 for r in relevant if r.get("reported_percentile") is not None)
    percentile_mode = raw_history_count < 12 and pct_history_count >= 12
    insufficient_mode = raw_history_count < 12 and not percentile_mode

    draw.rectangle((0, 0, WIDTH, 70), fill="#E9E9E9")
    txt(draw, (24, 22), name, f["head"])
    name_width = draw.textbbox((0, 0), name, font=f["head"])[2]
    txt(draw, (36 + name_width, 28), code, f["head_code"], MUTED)
    chart_caption = "分位历史（非估值原值）" if percentile_mode else (
        "有效历史不足" if insufficient_mode else "历史估值"
    )
    txt(draw, (WIDTH - 24, 29), f"{report_day} · {chart_caption}", f["head_code"], MUTED, anchor="ra")

    draw.rounded_rectangle(
        (PANEL_X, PANEL_Y, PANEL_X + PANEL_W, PANEL_Y + PANEL_H),
        radius=10,
        fill=PANEL,
    )

    stats = item.get("stats") if item else None
    reported = item.get("reported_percentile") if item else None
    percentile = stats.get("percentile") if stats else reported
    percentile_label = "10Y分位" if stats else "源站分位"
    if current is not None and item and item.get("source_date"):
        txt(draw, (PANEL_X + PANEL_W - 20, PANEL_Y + PANEL_H - 18),
            f"当前值交易日 {item['source_date']}", f["small"], MUTED, anchor="ra")

    top = PANEL_Y + 18
    gap = 10
    inner_x = PANEL_X + 18
    inner_w = PANEL_W - 36
    card_w = (inner_w - gap * 4) / 5
    summary = [
        ("当前值", fmt(metric, current), TEXT),
        (percentile_label, "—" if percentile is None else f"{float(percentile) * 100:.1f}%", TEXT),
        ("机会值", fmt(metric, stats.get("opportunity") if stats else None), GREEN),
        ("中位数", fmt(metric, stats.get("median") if stats else None), TEXT),
        ("危险值", fmt(metric, stats.get("danger") if stats else None), RED),
    ]
    for i, (label, value, accent) in enumerate(summary):
        x1 = inner_x + i * (card_w + gap)
        draw_summary_card(draw, (x1, top, x1 + card_w, top + 72), label, value, f, accent)

    chart_x1 = PANEL_X + 72
    chart_y1 = PANEL_Y + 112
    chart_x2 = PANEL_X + PANEL_W - 70
    chart_y2 = PANEL_Y + PANEL_H - 116

    # Keep the visual focus on valuation history. Index point remains in the footer
    # instead of sharing a second y-axis with the valuation line.
    chart_rows = [{**r, "point": None} for r in relevant]
    draw_chart(draw, (chart_x1, chart_y1, chart_x2, chart_y2), metric, chart_rows, stats, f)

    footer_y = PANEL_Y + PANEL_H - 88
    draw.line((PANEL_X + 18, footer_y - 14, PANEL_X + PANEL_W - 18, footer_y - 14), fill=GRID, width=1)

    if stats:
        footer = [
            ("10Y最低", fmt(metric, stats.get("minimum"))),
            ("10Y平均", fmt(metric, stats.get("mean"))),
            ("10Y最高", fmt(metric, stats.get("maximum"))),
            ("样本", str(stats.get("sample_count", raw_history_count))),
            ("指数点位", "—" if point is None else f"{float(point):,.2f}"),
        ]
    else:
        footer = [
            ("历史样本", str(raw_history_count)),
            ("分位样本", str(pct_history_count)),
            ("指数点位", "—" if point is None else f"{float(point):,.2f}"),
            ("数据状态", "仅分位历史" if percentile_mode else "原值不足"),
            ("目标", "10Y / 450周"),
        ]

    col_w = (PANEL_W - 36) / 5
    for i, (label, value) in enumerate(footer):
        x = PANEL_X + 18 + i * col_w
        txt(draw, (x, footer_y), label, f["small"], MUTED)
        txt(draw, (x, footer_y + 28), value, f["legend"], TEXT)

    ly = PANEL_Y + PANEL_H - 18
    lx = PANEL_X + 22
    if insufficient_mode:
        txt(draw, (lx, ly), "仅展示真实已采样值；不足12周不绘制历史曲线", f["small"], MUTED, anchor="lm")
    elif percentile_mode:
        draw.ellipse((lx, ly - 6, lx + 12, ly + 6), fill=CYAN)
        txt(draw, (lx + 20, ly), "历史分位（非PS原值）", f["small"], TEXT, anchor="lm")
    else:
        draw.ellipse((lx, ly - 6, lx + 12, ly + 6), fill=CYAN)
        txt(draw, (lx + 20, ly), metric_label(metric), f["small"], TEXT, anchor="lm")
        lx += 150
        if stats:
            for label, color in (("机会", GREEN), ("中位", GRAY_DASH), ("危险", RED)):
                dashed_hline(draw, ly, lx, lx + 20, color, width=2, dash=5, gap=4)
                txt(draw, (lx + 27, ly), label, f["small"], MUTED, anchor="lm")
                lx += 86

    out_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(out_path, format="PNG", optimize=True)


def main():
    latest_path = Path("data/latest.json")
    history_path = Path("data/history.csv")
    watchlist_path = Path("watchlist.yaml")
    data = json.loads(latest_path.read_text(encoding="utf-8"))
    specs = load_watchlist(watchlist_path)
    history = load_history(history_path)
    items = {(x["instrument_id"], x["metric"]): x for x in data.get("items", [])}
    f = fonts()
    report_day = data["generated_at"]

    manifest = []
    for spec in specs:
        metric = next(iter((spec.get("metrics") or {}).keys()), "")
        item = items.get((spec["id"], metric))
        out = Path("out/cards") / f"{spec['id']}.png"
        render_one(out, report_day, spec, item, history, f)
        manifest.append({
            "id": spec["id"],
            "name": spec["name"],
            "metric": metric,
            "file": str(out),
        })

    Path("out/cards/manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
