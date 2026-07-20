"""JSON exporter for stored comic metadata."""

from __future__ import annotations

import json
from typing import Iterable

from panelscout.exporters._records import comics_to_export_records
from panelscout.storage.models import Comic


def export_comics_json(comics: Iterable[Comic], *, indent: int = 2) -> str:
    """Return stored comic metadata as a JSON array."""

    return json.dumps(
        comics_to_export_records(comics),
        ensure_ascii=False,
        indent=indent,
        sort_keys=True,
    )
