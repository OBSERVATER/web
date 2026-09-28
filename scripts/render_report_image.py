from __future__ import annotations

import json
import math
from pathlib import Path

import yaml
from PIL import Image, ImageDraw, ImageFont


WIDTH = 1080
MARGIN = 48
HEADER_H = 170
CARD_H = 300
GAP = 20
BG = "#F3F4F6"
CARD = "#FFFFFF"
TEXT = "#111827"
MUTED = "#6B7280"
LIGHT = "#E5E7EB"
ACCENT = "#111827"
GREEN = "#16825D"
RED = "#C2413B"
AMBER = "#B7791F"


def find_font(bold: bool = False) -> str:
    candidates = [
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc" if bold else "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJKsc-Bold.otf" if bold else "/usr/share/fonts/opentype/noto/NotoSansCJKsc-Regular.otf",
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc" if bold else "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
    ]
    for path in candidates:
        if Path(path).exists():
            return path

    root = Path("/usr/share/fonts")
    patterns = ["**/*NotoSansCJK*Bold*", "**/*NotoSansCJK*Regular*"] if bold else ["**/*NotoSansCJK*Regular*", "**/*NotoSansCJK*"]
    for pattern in patterns:
        for path in root.glob(pattern):
            if path.suffix.lower() in {".ttf", ".otf", ".ttc"}:
                return str(path)
    raise RuntimeError("No Noto CJK font found; install fonts-noto-cjk")


def fonts():
    regular = find_font(False)
    bold = find_font(True)
    return {
        "title": ImageFont.truetype(bold, 48),
        "subtitle": ImageFont.truetype(regular, 25),
        "name": ImageFont.truetype(bold, 34),
        "code": ImageFont.truetype(regular, 22),
        "metric": ImageFont.truetype(regular, 23),
        "value": ImageFont.truetype(bold, 54),
        "percentile": ImageFont.truetype(bold, 32),
        "label": ImageFont.truetype(regular, 20),
        "small": ImageFont.truetype(regular, 18),
        "badge": ImageFont.truetype(bold, 20),
    }


def text(draw, xy, content, font, fill=TEXT, anchor=None):
    draw.text(xy, str(content), font=font, fill=fill, anchor=anchor)


def rounded(draw, box, radius, fill, outline=None, width=1):
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


def fmt(metric: str, value):
    if value is None:
        return "—"
    if metric == "dyr":
        return f"{float(value):.2f}%"
    return f"{float(value):.2f}"


def status_color(status: str):
    if status == "机会区":
        return GREEN
    if status == "危险区":
        return RED
    if status == "历史不足":
        return AMBER
    return MUTED


def source_short(source: str) -> str:
    if source.startswith("csindex"):
        return "中证指数官方"
    if source.startswith("cnindex"):
        return "国证指数官方"
    if source.startswith("danjuan"):
        return "蛋卷公开数据"
    if "getstockcheck" in source:
        return "公开估值页"
    if "baifenwei" in source:
        return "百分位公开页"
    return source[:28]


def load_watchlist(path: Path):
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    return raw.get("instruments", [])


def draw_gauge(draw, x1, y, x2, percentile, font):
    draw.line((x1, y, x2, y), fill=LIGHT, width=12)
    for p, label in [(0.2, "20"), (0.5, "50"), (0.8, "80")]:
        px = x1 + (x2 - x1) * p
        draw.line((px, y - 11, px, y + 11), fill="#9CA3AF", width=2)
        text(draw, (px, y + 22), label, font, MUTED, anchor="ma")

    if percentile is not None:
        p = min(1.0, max(0.0, percentile))
        px = x1 + (x2 - x1) * p
        draw.ellipse((px - 10, y - 10, px + 10, y + 10), fill=ACCENT)
        text(draw, (px, y - 22), f"{p * 100:.1f}%", font, TEXT, anchor="ms")


def draw_card(draw, top, spec, item, f):
    left = MARGIN
    right = WIDTH - MARGIN
    rounded(draw, (left, top, right, top + CARD_H), 28, CARD)

    name = spec.get("name", item.get("name") if item else "未知")
    code = spec.get("code", item.get("code") if item else "")
    metric_key = next(iter((spec.get("metrics") or {}).keys()), item.get("metric") if item else "")
    labels = {"pe_ttm": "市盈率 TTM", "pb": "市净率 LF", "ps_ttm": "市销率 TTM", "dyr": "股息率"}

    text(draw, (left + 30, top + 28), name, f["name"])
    text(draw, (left + 30, top + 72), f"{code} · {labels.get(metric_key, metric_key)}", f["code"], MUTED)

    if not item:
        text(draw, (left + 30, top + 128), "数据源暂不可用", f["value"], RED)
        text(draw, (left + 30, top + 210), "本次未取得可靠数据", f["metric"], MUTED)
        return

    current = item.get("current")
    stats = item.get("stats")
    reported = item.get("reported_percentile")
    history_samples = int(item.get("history_samples") or 0)
    point = item.get("point")

    if stats:
        percentile = float(stats["percentile"])
        status = item.get("zone", "中性")
    elif reported is not None:
        percentile = float(reported)
        status = "历史不足"
    else:
        percentile = None
        status = "历史不足"

    text(draw, (left + 30, top + 112), fmt(metric_key, current), f["value"])
    if point is not None:
        text(draw, (left + 30, top + 176), f"指数点位  {float(point):,.2f}", f["metric"], MUTED)

    badge = status
    badge_fill = status_color(status)
    bx2 = right - 30
    bw = 112 if len(badge) <= 3 else 132
    rounded(draw, (bx2 - bw, top + 30, bx2, top + 66), 18, badge_fill)
    text(draw, (bx2 - bw / 2, top + 48), badge, f["badge"], "#FFFFFF", anchor="mm")

    pct_text = "—" if percentile is None else f"{percentile * 100:.2f}%"
    text(draw, (right - 30, top + 112), pct_text, f["percentile"], anchor="ra")
    text(draw, (right - 30, top + 151), "10Y 历史分位" if stats else "公开源分位 / 待积累", f["small"], MUTED, anchor="ra")

    gx1 = left + 30
    gx2 = right - 30
    gy = top + 218
    draw_gauge(draw, gx1, gy, gx2, percentile, f["small"])

    if stats:
        info = [
            ("机会", fmt(metric_key, stats.get("opportunity"))),
            ("中位", fmt(metric_key, stats.get("median"))),
            ("危险", fmt(metric_key, stats.get("danger"))),
            ("Z", f"{float(stats.get('zscore', 0)):.2f}"),
        ]
        xs = [left + 30, left + 250, left + 470, left + 690]
        for x, (label, val) in zip(xs, info):
            text(draw, (x, top + 262), f"{label} {val}", f["label"], TEXT)
    else:
        text(draw, (left + 30, top + 262), f"10Y 周样本积累中：{history_samples}/450", f["label"], AMBER)

    src = source_short(str(item.get("source", "")))
    source_date = item.get("source_date", "")
    text(draw, (right - 30, top + 262), f"{source_date} · {src}", f["small"], MUTED, anchor="ra")


def main():
    latest_path = Path("data/latest.json")
    watchlist_path = Path("watchlist.yaml")
    out_path = Path("out/report.png")
    out_path.parent.mkdir(parents=True, exist_ok=True)

    data = json.loads(latest_path.read_text(encoding="utf-8"))
    specs = load_watchlist(watchlist_path)
    items = {(x["instrument_id"], x["metric"]): x for x in data.get("items", [])}
    f = fonts()

    height = HEADER_H + len(specs) * CARD_H + max(0, len(specs) - 1) * GAP + 70
    image = Image.new("RGB", (WIDTH, height), BG)
    draw = ImageDraw.Draw(image)

    text(draw, (MARGIN, 44), f"指数估值日报  {data.get('generated_at', '')}", f["title"])
    text(draw, (MARGIN, 108), "10Y · 周频 · 当前估值与历史位置", f["subtitle"], MUTED)

    top = HEADER_H
    for spec in specs:
        metric_key = next(iter((spec.get("metrics") or {}).keys()), "")
        item = items.get((spec.get("id"), metric_key))
        draw_card(draw, top, spec, item, f)
        top += CARD_H + GAP

    errors = data.get("errors") or []
    if errors:
        text(draw, (MARGIN, height - 42), f"数据源提示：{len(errors)} 项异常，详见 GitHub 日报评论", f["small"], RED)
    else:
        text(draw, (MARGIN, height - 42), "数据来自无需登录的公开源；历史不足时不伪造 10Y 统计", f["small"], MUTED)

    image.save(out_path, format="PNG", optimize=True)


if __name__ == "__main__":
    main()
