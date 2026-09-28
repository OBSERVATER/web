from __future__ import annotations

import json
from pathlib import Path


def main() -> None:
    data = json.loads(Path("data/latest.json").read_text(encoding="utf-8"))
    lines = [
        "@OBSERVATER",
        "",
        f"## 指数估值日报 · {data['generated_at']}",
        "",
        "![指数估值日报](out/report.png)",
    ]

    errors = data.get("errors") or []
    if errors:
        lines += ["", "<details><summary>数据源提示</summary>", ""]
        lines += [f"- {error}" for error in errors]
        lines += ["", "</details>"]

    lines += [
        "",
        "> 手机优先：完整估值信息已合并到上图；历史不足的指标不会伪造 10Y 统计。",
    ]
    Path("out/issue-comment.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
