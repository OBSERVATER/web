from __future__ import annotations

import json
import os
from pathlib import Path


def main() -> None:
    data = json.loads(Path("data/latest.json").read_text(encoding="utf-8"))
    manifest = json.loads(Path("out/cards/manifest.json").read_text(encoding="utf-8"))
    report_day = data["generated_at"]
    repo = os.getenv("GITHUB_REPOSITORY", "OBSERVATER/web")

    lines = [
        "@OBSERVATER",
        "",
        f"## 指数估值日报 · {report_day}",
        "",
    ]

    for card in manifest:
        url = (
            f"https://raw.githubusercontent.com/{repo}/main/"
            f"reports/{report_day}/{card['id']}.png?v={report_day}"
        )
        lines += [
            f"### {card['name']}",
            f"![{card['name']}估值数据]({url})",
            "",
        ]

    errors = data.get("errors") or []
    if errors:
        lines += ["<details><summary>数据源提示</summary>", ""]
        lines += [f"- {error}" for error in errors]
        lines += ["", "</details>", ""]

    lines += [
        "> 图片布局按你给的参考图的数据区重做：当前值、分位点、危险/中位/机会值、最大/平均/最小、±1σ、Z 分数和走势图。",
    ]
    Path("out/issue-comment.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
