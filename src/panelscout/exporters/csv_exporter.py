"""CSV exporter for stored comic metadata."""

from __future__ import annotations

import csv
import json
from io import StringIO
from typing import Iterable

from panelscout.exporters._records import EXPORT_FIELDS, comics_to_export_records
from panelscout.storage.models import Comic


def export_comics_csv(comics: Iterable[Comic]) -> str:
    """Return stored comic metadata as CSV text."""

    output = StringIO()
    writer = csv.DictWriter(output, fieldnames=EXPORT_FIELDS, lineterminator="\n")
    writer.writeheader()

    for record in comics_to_export_records(comics):
        writer.writerow(
            {
                field: _format_csv_value(record[field])
                for field in EXPORT_FIELDS
            }
        )

    return output.getvalue()


def _format_csv_value(value: object) -> object:
    if isinstance(value, list):
        return json.dumps(value, ensure_ascii=False)
    if value is None:
        return ""
    return value
