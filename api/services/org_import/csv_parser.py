"""CSV files: the downloadable template and reading an uploaded file into rows."""

from __future__ import annotations

import csv
import io
from collections.abc import Iterator

from services.org_service import OrgError

from .rows import COLUMNS, HEADERS


def template_csv() -> str:
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(HEADERS)
    writer.writerow([c[1] for c in COLUMNS])
    writer.writerow([c[2] for c in COLUMNS])
    return out.getvalue()


def read_rows(raw: bytes) -> Iterator[tuple[int, dict]]:
    """(spreadsheet line, row) for each data row. The file and its header row are checked up front;
    the rows themselves are read as the caller goes."""
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise OrgError("Save the file as CSV with UTF-8 encoding (Excel: File, Save As, CSV UTF-8)") from None
    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames or "name" not in [f.strip() for f in reader.fieldnames]:
        raise OrgError("The first row must be the template's column names. Download the template and start from it")
    return ((line, {(k or "").strip(): v for k, v in row.items()}) for line, row in enumerate(reader, start=2))
