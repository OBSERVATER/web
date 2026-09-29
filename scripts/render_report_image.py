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
LEFT_W = 255
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
    pct_rows = [r for r in rows if r.get("reported_percentile") is not None]
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
    if pts:
        draw.line(pts, fill="#D89A27", width=3)

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

    metric_rows = [r for r in rows if r.get("value") is not None and float(r.get("value") or 0) > 0]
    if len(metric_rows) < 3:
        draw_percentile_chart(draw, box, rows, f)
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
    relevant = [
        r for r in history
        if r["instrument_id"] == spec["id"] and r["metric"] == metric
    ]
    raw_history_count = sum(1 for r in relevant if r.get("value") is not None and float(r.get("value") or 0) > 0)
    pct_history_count = sum(1 for r in relevant if r.get("reported_percentile") is not None)
    percentile_mode = raw_history_count < 3 and pct_history_count >= 3

    # header bar, mirroring the reference's data header
    draw.rectangle((0, 0, WIDTH, 70), fill="#E9E9E9")
    txt(draw, (24, 22), name, f["head"])
    txt(draw, (180, 27), code, f["head_code"], TEXT)
    if point is not None:
        txt(draw, (330, 26), f"{float(point):,.2f}", f["head_code"], RED)
    txt(draw, (WIDTH - 24, 29), f"{report_day} · 历史估值", f["head_code"], MUTED, anchor="ra")

    draw.rounded_rectangle(
        (PANEL_X, PANEL_Y, PANEL_X + PANEL_W, PANEL_Y + PANEL_H),
        radius=10,
        fill=PANEL,
    )

    txt(draw, (PANEL_X + 18, PANEL_Y + 16), metric_label(metric), f["metric_title"])

    # Wind-style data-view tabs shown inside the valuation panel.
    tab_y1 = PANEL_Y + 13
    tab_y2 = PANEL_Y + 49
    tab_w = 118
    tab_x3 = PANEL_X + PANEL_W - 18
    tab_x2 = tab_x3 - tab_w
    tab_x1 = tab_x2 - tab_w
    tab_x0 = tab_x1 - tab_w
    tabs = [
        (tab_x0, tab_x1, metric_label(metric), not percentile_mode),
        (tab_x1, tab_x2, "分位点", percentile_mode),
        (tab_x2, tab_x3, "标准差", False),
    ]
    for left, right, label, active in tabs:
        fill = "#4EAFC3" if active else "#FFFFFF"
        color = "#FFFFFF" if active else TEXT
        draw.rectangle((left, tab_y1, right, tab_y2), fill=fill, outline="#BFC4C9", width=1)
        txt(draw, ((left + right) / 2, (tab_y1 + tab_y2) / 2), label, f["small"], color, anchor="mm")

    left_x = PANEL_X + 20
    value_x = PANEL_X + LEFT_W - 14
    y = PANEL_Y + 76

    stats = item.get("stats") if item else None
    reported = item.get("reported_percentile") if item else None
    percentile = stats.get("percentile") if stats else reported

    draw_stat(draw, left_x, value_x, y, "当前值", fmt(metric, current), f)
    y += 42
    draw_stat(draw, left_x, value_x, y, "分位点", "—" if percentile is None else f"{float(percentile) * 100:.2f}%", f)
    y += 42
    draw_stat(draw, left_x, value_x, y, "危险值", fmt(metric, stats.get("danger") if stats else None), f)
    y += 42
    draw_stat(draw, left_x, value_x, y, "中位数", fmt(metric, stats.get("median") if stats else None), f)
    y += 42
    draw_stat(draw, left_x, value_x, y, "机会值", fmt(metric, stats.get("opportunity") if stats else None), f)
    y += 42
    draw_stat(draw, left_x, value_x, y, "指数点位", "—" if point is None else f"{float(point):,.2f}", f)

    y += 52
    draw.rounded_rectangle(
        (left_x - 8, y - 18, value_x + 8, PANEL_Y + PANEL_H - 40),
        radius=8,
        fill="#F7F8FA",
    )
    draw_stat(draw, left_x, value_x, y, "最大值", fmt(metric, stats.get("maximum") if stats else None), f)
    y += 38
    draw_stat(draw, left_x, value_x, y, "平均值", fmt(metric, stats.get("mean") if stats else None), f)
    y += 38
    draw_stat(draw, left_x, value_x, y, "最小值", fmt(metric, stats.get("minimum") if stats else None), f)
    y += 38
    if stats:
        plus = (stats.get("mean") or 0) + (stats.get("stddev") or 0)
        minus = (stats.get("mean") or 0) - (stats.get("stddev") or 0)
    else:
        plus = minus = None
    draw_stat(draw, left_x, value_x, y, "标准差(+1)", fmt(metric, plus), f)
    y += 38
    draw_stat(draw, left_x, value_x, y, "标准差(-1)", fmt(metric, minus), f)
    y += 38
    draw_stat(draw, left_x, value_x, y, "z 分数", "—" if not stats else f"{float(stats.get('zscore', 0)):.2f}", f)

    chart_x1 = PANEL_X + LEFT_W + 28
    chart_y1 = PANEL_Y + 78
    chart_x2 = PANEL_X + PANEL_W - 68
    chart_y2 = PANEL_Y + PANEL_H - 82

    draw_chart(draw, (chart_x1, chart_y1, chart_x2, chart_y2), metric, relevant, stats, f)

    # Keep only visible chart elements in the legend; the reference screenshot's disabled
    # legend items made the mobile image unnecessarily dense.
    ly = PANEL_Y + PANEL_H - 34
    lx = chart_x1 + 6
    if percentile_mode:
        draw.line((lx, ly, lx + 24, ly), fill="#D89A27", width=3)
        txt(draw, (lx + 32, ly), "历史分位", f["small"], TEXT, anchor="lm")
        lx += 120
        draw.line((lx, ly, lx + 24, ly), fill=BLUE, width=3)
        txt(draw, (lx + 32, ly), "指数点位", f["small"], TEXT, anchor="lm")
        lx += 122
        dashed_hline(draw, ly, lx, lx + 24, GREEN, width=2, dash=6, gap=4)
        txt(draw, (lx + 32, ly), "20%", f["small"], TEXT, anchor="lm")
        lx += 78
        dashed_hline(draw, ly, lx, lx + 24, GRAY_DASH, width=2, dash=6, gap=4)
        txt(draw, (lx + 32, ly), "50%", f["small"], TEXT, anchor="lm")
        lx += 78
        dashed_hline(draw, ly, lx, lx + 24, RED, width=2, dash=6, gap=4)
        txt(draw, (lx + 32, ly), "80%", f["small"], TEXT, anchor="lm")
    else:
        draw.ellipse((lx, ly - 7, lx + 14, ly + 7), fill=CYAN)
        txt(draw, (lx + 22, ly), metric_label(metric), f["small"], TEXT, anchor="lm")
        lx += 145
        if any(r.get("point") is not None for r in relevant):
            draw.line((lx, ly, lx + 24, ly), fill=BLUE, width=3)
            txt(draw, (lx + 32, ly), "指数点位", f["small"], TEXT, anchor="lm")
            lx += 122
        if stats:
            dashed_hline(draw, ly, lx, lx + 24, RED, width=2, dash=6, gap=4)
            txt(draw, (lx + 32, ly), "危险值", f["small"], TEXT, anchor="lm")
            lx += 105
            dashed_hline(draw, ly, lx, lx + 24, GRAY_DASH, width=2, dash=6, gap=4)
            txt(draw, (lx + 32, ly), "中位数", f["small"], TEXT, anchor="lm")
            lx += 105
            dashed_hline(draw, ly, lx, lx + 24, GREEN, width=2, dash=6, gap=4)
            txt(draw, (lx + 32, ly), "机会值", f["small"], TEXT, anchor="lm")

    if not stats:
        src_pct = ""
        if reported is not None:
            src_pct = f" · 当前公开分位 {float(reported)*100:.2f}%"
        note = "已取得历史分位序列，原始估值序列仍在回填" if percentile_mode else "完整10Y原始序列仍在回填"
        txt(draw, (PANEL_X + 20, PANEL_Y + PANEL_H - 18), note + src_pct, f["small"], MUTED)

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
