"""Bulk service import: one spreadsheet row per service, saved as drafts the organization reviews.

The template is plain CSV so it opens in Excel, LibreOffice and Google Sheets. Lists inside a
cell are separated by semicolons. Rows with errors are reported and skipped; nothing is
published by an import.

Reading a file (format to rows) is kept apart from checking and saving rows, so more formats
can be added next to CSV: csv_parser reads the file, rows checks one row, and import_services
here saves them.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable

from services import org_service
from services.org_service import OrgError

from . import csv_parser
from .csv_parser import template_csv
from .rows import COLUMNS, HEADERS, _DOC_FLAGS, _document, _money, _row_to_service, _split, _yes

__all__ = [
    "COLUMNS", "HEADERS", "MAX_ROWS", "PARSERS", "_DOC_FLAGS", "parser_for",
    "_document", "_money", "_row_to_service", "_split", "_yes", "import_services", "template_csv",
]

MAX_ROWS = 300

# Each format's reader: raw upload -> (line number, row dict) pairs, raising OrgError for an unreadable file
PARSERS: dict[str, Callable[[bytes], Iterable[tuple[int, dict]]]] = {
    "csv": csv_parser.read_rows,
}


def parser_for(filename: str | None) -> Callable[[bytes], Iterable[tuple[int, dict]]]:
    """The reader for an uploaded file, chosen by its extension (CSV when there is none)."""
    ext = (filename or "").rsplit(".", 1)[-1].lower() if "." in (filename or "") else "csv"
    if ext not in PARSERS:
        names = ", ".join(sorted(e.upper() for e in PARSERS))
        raise OrgError(f"This file type can't be imported yet. Upload one of: {names}")
    return PARSERS[ext]


def import_services(org_id: str, raw: bytes, *, actor: str, dry_run: bool, filename: str | None = None) -> dict:
    """Check every row; unless dry_run, save the valid ones as drafts."""
    rows = parser_for(filename)(raw)
    branches = {b["name"].strip().lower(): b["id"] for b in org_service.list_branches(org_id)}
    existing = {r["name"].strip().lower() for r in org_service.list_org_services(org_id)}
    report = []
    created = 0
    for line, row in rows:
        name = (row.get("name") or "").strip()
        # The template's explanation and example rows
        is_example = all((row.get(k) or "").strip() == example for k, _, example in COLUMNS)
        # Fully blank rows (often left at the end of a spreadsheet) are not services
        is_blank = not any((v or "").strip() for v in row.values() if isinstance(v, str))
        if is_blank or is_example or name.startswith("Service name in English"):
            continue
        if line > MAX_ROWS + 1:
            report.append({"row": line, "name": name, "status": "error",
                           "errors": [f"Only {MAX_ROWS} services per file"], "warnings": [], "service_id": None})
            continue
        if not name:
            report.append({"row": line, "name": "", "status": "error", "warnings": [], "service_id": None,
                           "errors": ["The name column is empty. Every service needs a name in English"]})
            continue
        service, errors, warnings = _row_to_service(row, branches)
        if name.lower() in existing:
            errors.append("A service with this name already exists. Edit it in your dashboard instead")
            service = None
        entry = {"row": line, "name": name, "errors": errors, "warnings": warnings, "service_id": None}
        if service is None:
            entry["status"] = "error"
        elif dry_run:
            entry["status"] = "ready"
        else:
            try:
                saved = org_service.save_service(org_id, None, service, actor)
                entry.update(status="created", service_id=saved["id"],
                             completeness=saved["completeness"]["score"])
                existing.add(name.lower())
                created += 1
            except OrgError as exc:
                entry.update(status="error", errors=[*errors, str(exc)])
        report.append(entry)
    return {
        "dry_run": dry_run,
        "rows": report,
        "ready": sum(1 for r in report if r["status"] in ("ready", "created")),
        "created": created,
        "errors": sum(1 for r in report if r["status"] == "error"),
    }
