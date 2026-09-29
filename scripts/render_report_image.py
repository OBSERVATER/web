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


def draw_chart(draw, box, metric, rows, stats, f):
    x1, y1, x2, y2 = box
    draw.rectangle(box, fill="#FBFBFB", outline=GRID, width=1)

    metric_rows = [r for r in rows if r.get("value") is not None]
    if len(metric_rows) < 3:
        txt(draw, ((x1 + x2) / 2, (y1 + y2) / 2 - 8), "暂无完整10年原始序列", f["empty"], MUTED, anchor="mm")
        txt(draw, ((x1 + x2) / 2, (y1 + y2) / 2 + 28), "当前值与可核验分位仍正常显示", f["small"], MUTED, anchor="mm")
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
            stats.get("mean"),
            (stats.get("mean") or 0) + (stats.get("stddev") or 0),
            (stats.get("mean") or 0) - (stats.get("stddev") or 0),
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

        mean = stats.get("mean")
        std = stats.get("stddev")
        if mean is not None and lo <= mean <= hi:
            y = y2 - ((mean - lo) / (hi - lo)) * (y2 - y1)
            draw.line((x1, y, x2, y), fill="#A9AEB3", width=2)
        if mean is not None and std is not None:
            for val in (mean + std, mean - std):
                if lo <= val <= hi:
                    y = y2 - ((val - lo) / (hi - lo)) * (y2 - y1)
                    dashed_hline(draw, y, x1, x2, LIGHT_DASH, width=2, dash=8, gap=8)

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
    draw.rounded_rectangle((tab_x0, tab_y1, tab_x1, tab_y2), radius=4, fill="#4EAFC3")
    txt(draw, ((tab_x0 + tab_x1) / 2, (tab_y1 + tab_y2) / 2), metric_label(metric), f["small"], "#FFFFFF", anchor="mm")
    draw.rectangle((tab_x1, tab_y1, tab_x2, tab_y2), fill="#FFFFFF", outline="#BFC4C9", width=1)
    txt(draw, (tab_x1 + tab_w / 2, (tab_y1 + tab_y2) / 2), "分位点", f["small"], TEXT, anchor="mm")
    draw.rectangle((tab_x2, tab_y1, tab_x3, tab_y2), fill="#FFFFFF", outline="#BFC4C9", width=1)
    txt(draw, (tab_x2 + tab_w / 2, (tab_y1 + tab_y2) / 2), "标准差", f["small"], TEXT, anchor="mm")

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
    chart_y2 = PANEL_Y + PANEL_H - 112

    relevant = [
        r for r in history
        if r["instrument_id"] == spec["id"] and r["metric"] == metric
    ]
    draw_chart(draw, (chart_x1, chart_y1, chart_x2, chart_y2), metric, relevant, stats, f)

    # Two-line legend mirrors Wind's historical valuation data panel.
    ly1 = PANEL_Y + PANEL_H - 68
    lx = chart_x1 + 4
    draw.ellipse((lx, ly1 - 7, lx + 14, ly1 + 7), fill=CYAN)
    txt(draw, (lx + 22, ly1), metric_label(metric), f["small"], TEXT, anchor="lm")
    lx += 150
    draw.line((lx, ly1, lx + 22, ly1), fill=BLUE, width=3)
    txt(draw, (lx + 30, ly1), "指数点位", f["small"], TEXT, anchor="lm")
    lx += 128
    draw.polygon([(lx + 7, ly1 - 7), (lx, ly1 + 6), (lx + 14, ly1 + 6)], fill="#B8BDC2")
    txt(draw, (lx + 23, ly1), "调仓标志", f["small"], "#A0A5AA", anchor="lm")
    lx += 126
    draw.ellipse((lx + 2, ly1 - 5, lx + 12, ly1 + 5), fill="#D0D3D6")
    txt(draw, (lx + 22, ly1), "分位点", f["small"], "#A0A5AA", anchor="lm")
    lx += 100
    dashed_hline(draw, ly1, lx, lx + 22, RED, width=2, dash=6, gap=4)
    txt(draw, (lx + 30, ly1), "危险值", f["small"], TEXT, anchor="lm")
    lx += 104
    dashed_hline(draw, ly1, lx, lx + 22, GRAY_DASH, width=2, dash=6, gap=4)
    txt(draw, (lx + 30, ly1), "中位数", f["small"], TEXT, anchor="lm")

    ly2 = PANEL_Y + PANEL_H - 34
    lx = chart_x1 + 4
    dashed_hline(draw, ly2, lx, lx + 22, GREEN, width=2, dash=6, gap=4)
    txt(draw, (lx + 30, ly2), "机会值", f["small"], TEXT, anchor="lm")
    lx += 112
    dashed_hline(draw, ly2, lx, lx + 22, LIGHT_DASH, width=2, dash=6, gap=4)
    txt(draw, (lx + 30, ly2), "标准差(+1)", f["small"], MUTED, anchor="lm")
    lx += 142
    draw.line((lx, ly2, lx + 22, ly2), fill="#A9AEB3", width=2)
    txt(draw, (lx + 30, ly2), "平均值", f["small"], MUTED, anchor="lm")
    lx += 105
    dashed_hline(draw, ly2, lx, lx + 22, LIGHT_DASH, width=2, dash=6, gap=4)
    txt(draw, (lx + 30, ly2), "标准差(-1)", f["small"], MUTED, anchor="lm")

    if not stats:
        src_pct = ""
        if reported is not None:
            src_pct = f"；公开源10Y分位 {float(reported)*100:.2f}%"
        txt(
            draw,
            (PANEL_X + 20, PANEL_Y + PANEL_H - 18),
            f"完整10Y原始序列仍在回填{src_pct}",
            f["small"],
            MUTED,
        )

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
