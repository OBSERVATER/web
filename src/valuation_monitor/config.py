from __future__ import annotations

from pathlib import Path

import yaml

from .models import Instrument, MetricSpec


def load_config(path: str | Path) -> tuple[dict, list[Instrument]]:
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    settings = raw.get("settings", {})
    instruments: list[Instrument] = []

    for item in raw.get("instruments", []):
        metrics = []
        raw_metrics = item.get("metrics", {})
        if isinstance(raw_metrics, list):
            metrics = [MetricSpec(str(key)) for key in raw_metrics]
        else:
            for key, options in raw_metrics.items():
                options = options or {}
                metrics.append(MetricSpec(key=str(key), weighting=str(options.get("weighting", "mcw"))))

        instruments.append(
            Instrument(
                id=str(item["id"]),
                name=str(item["name"]),
                market=str(item["market"]).lower(),
                code=str(item["code"]),
                metrics=tuple(metrics),
            )
        )

    return settings, instruments
