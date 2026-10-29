"""
Data sources staff add from the admin app: an official web page (HTML or PDF) or document
text pasted in. A run reads the text and replaces that source's passages in the AI knowledge base.
"""

from __future__ import annotations

import ipaddress
import re
import socket
from urllib.parse import urljoin, urlsplit

import httpx

from services import rag_service
from services.db import fetch_all, fetch_one

KINDS = ("web_page", "pasted_text")
SCHEDULES = ("manual", "daily", "weekly")
MAX_DOWNLOAD_BYTES = 2 * 1024 * 1024
MAX_TEXT_CHARS = 200_000
MIN_TEXT_CHARS = 50
FETCH_TIMEOUT_S = 20
MAX_REDIRECTS = 5
USER_AGENT = "ComplianceNavigator/1.0 (+data source refresh)"

_COLUMNS = """
    id::text, name, description, kind, url, issuing_body, language, tags, schedule, enabled,
    paused_by, paused_at, created_by, created_at, updated_by, updated_at,
    coalesce(length(body), 0) as text_length
"""


class UnsafeURL(ValueError):
    """The address is not a public http(s) page."""


def source_key(source_id: str) -> str:
    return f"custom:{source_id}"


def chunk_service_id(source_id: str) -> str:
    return f"custom-{source_id}"


# ---------------------------------------------------------------- validation


def _blocked_ip(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped:
        ip = ip.ipv4_mapped
    return not ip.is_global or ip.is_multicast


def check_url_shape(url: str) -> str:
    """Checks that need no network: http(s), a host name, not this server or a private address."""
    url = url.strip()
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https"):
        raise UnsafeURL("The address must start with http:// or https://")
    host = (parts.hostname or "").strip(".").lower()
    if not host:
        raise UnsafeURL("The address is missing a website name")
    if parts.username or parts.password:
        raise UnsafeURL("Addresses with a user name or password are not allowed")
    if host == "localhost" or host.endswith((".localhost", ".local", ".internal")):
        raise UnsafeURL("That address points to this server or a private network, which is not allowed")
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return url
    if _blocked_ip(ip):
        raise UnsafeURL("That address points to this server or a private network, which is not allowed")
    return url


def _check_resolved(url: str) -> None:
    """Every address the host name resolves to must be public (stops DNS tricks to reach internal services)."""
    parts = urlsplit(url)
    port = parts.port or (443 if parts.scheme == "https" else 80)
    try:
        infos = socket.getaddrinfo(parts.hostname, port, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise UnsafeURL(f"Couldn't find the website {parts.hostname}") from exc
    for info in infos:
        if _blocked_ip(ipaddress.ip_address(info[4][0])):
            raise UnsafeURL("That address points to this server or a private network, which is not allowed")


def _clean_tags(tags: list[str]) -> list[str]:
    out: list[str] = []
    for tag in tags:
        tag = re.sub(r"\s+", "-", tag.strip().lower())
        if tag and tag not in out:
            out.append(tag[:40])
    return out[:10]


def validate(data: dict) -> dict:
    """Cross-field rules; raises ValueError with a message staff can act on."""
    data = dict(data)
    data["name"] = data["name"].strip()
    data["description"] = (data.get("description") or "").strip()
    data["issuing_body"] = (data.get("issuing_body") or "").strip() or None
    data["tags"] = _clean_tags(data.get("tags") or [])
    url = (data.get("url") or "").strip() or None
    text = (data.get("text") or "").strip() or None
    if len(data["name"]) < 3:
        raise ValueError("Give the source a name of at least 3 characters")
    if data["kind"] == "web_page":
        if not url:
            raise ValueError("Enter the address (URL) of the page to read")
        text = None
    else:
        if not text or len(text) < MIN_TEXT_CHARS:
            raise ValueError(f"Paste the document text (at least {MIN_TEXT_CHARS} characters)")
        if data.get("schedule") != "manual":
            # Pasted text never changes on its own, so re-reading it on a timer does nothing useful
            data["schedule"] = "manual"
    if url:
        url = check_url_shape(url)
    data["url"], data["text"] = url, text
    return data


# ---------------------------------------------------------------- storage


def list_custom() -> list[dict]:
    return fetch_all(f"select {_COLUMNS} from custom_data_sources order by created_at")


def get_custom(source_id: str, *, with_text: bool = False) -> dict | None:
    row = fetch_one(
        f"select {_COLUMNS}, body from custom_data_sources where id = %s", (source_id,)
    )
    if row and not with_text:
        row.pop("body", None)
    return row


def create_custom(data: dict, by: str | None) -> dict:
    data = validate(data)
    row = fetch_one(
        """
        insert into custom_data_sources (name, description, kind, url, body, issuing_body, language,
          tags, schedule, enabled, paused_by, paused_at, created_by, updated_by)
        values (%(name)s, %(description)s, %(kind)s, %(url)s, %(text)s, %(issuing_body)s, %(language)s,
          %(tags)s, %(schedule)s, %(enabled)s,
          case when %(enabled)s then null else %(by)s end,
          case when %(enabled)s then null else now() end, %(by)s, %(by)s)
        returning id::text
        """,
        {**data, "by": by},
    )
    return get_custom(row["id"])


def update_custom(source_id: str, data: dict, by: str | None) -> dict | None:
    data = validate(data)
    row = fetch_one(
        """
        update custom_data_sources set
          name = %(name)s, description = %(description)s, kind = %(kind)s, url = %(url)s,
          body = %(text)s, issuing_body = %(issuing_body)s, language = %(language)s, tags = %(tags)s,
          schedule = %(schedule)s,
          paused_by = case when %(enabled)s then null when enabled then %(by)s else paused_by end,
          paused_at = case when %(enabled)s then null when enabled then now() else paused_at end,
          enabled = %(enabled)s,
          updated_by = %(by)s, updated_at = now()
        where id = %(id)s
        returning id::text
        """,
        {**data, "by": by, "id": source_id},
    )
    return get_custom(row["id"]) if row else None


def delete_custom(source_id: str) -> dict | None:
    """Removes the source and its passages from the AI knowledge base. Its run history is kept."""
    row = fetch_one("delete from custom_data_sources where id = %s returning id::text, name", (source_id,))
    if not row:
        return None
    row["chunks_removed"] = rag_service.delete_chunks(service_id=chunk_service_id(source_id))
    return row


def set_enabled(source_id: str, enabled: bool, by: str | None) -> dict | None:
    row = fetch_one(
        """
        update custom_data_sources set enabled = %(on)s,
          paused_by = case when %(on)s then null else %(by)s end,
          paused_at = case when %(on)s then null else now() end
        where id = %(id)s returning id::text
        """,
        {"on": enabled, "by": by, "id": source_id},
    )
    return get_custom(source_id) if row else None


def due_for_schedule() -> list[str]:
    """Enabled daily/weekly sources whose last successful run is older than their schedule."""
    rows = fetch_all(
        """
        select c.id::text
        from custom_data_sources c
        where c.enabled and c.schedule <> 'manual'
          and coalesce(
                (select max(r.started_at) from data_source_runs r
                  where r.source = 'custom:' || c.id::text and r.status = 'success'),
                '-infinity'::timestamptz
              ) < now() - case c.schedule when 'daily' then interval '23 hours' else interval '6 days 23 hours' end
        order by c.created_at
        """
    )
    return [r["id"] for r in rows]


# ---------------------------------------------------------------- reading a page


def fetch_url(url: str) -> tuple[bytes, str]:
    """GET a public page with a size cap; every redirect hop is checked again. Returns (body, content type)."""
    with httpx.Client(timeout=FETCH_TIMEOUT_S, follow_redirects=False, headers={"User-Agent": USER_AGENT}) as client:
        for _ in range(MAX_REDIRECTS + 1):
            check_url_shape(url)
            _check_resolved(url)
            with client.stream("GET", url) as resp:
                if resp.is_redirect:
                    url = urljoin(url, resp.headers.get("location", ""))
                    continue
                if resp.status_code >= 400:
                    raise RuntimeError(f"The website answered with error {resp.status_code}")
                declared = int(resp.headers.get("content-length") or 0)
                if declared > MAX_DOWNLOAD_BYTES:
                    raise RuntimeError("The page is larger than 2 MB, which is the limit")
                body = bytearray()
                for chunk in resp.iter_bytes():
                    body.extend(chunk)
                    if len(body) > MAX_DOWNLOAD_BYTES:
                        raise RuntimeError("The page is larger than 2 MB, which is the limit")
                return bytes(body), resp.headers.get("content-type", "")
    raise RuntimeError("The address redirected too many times")


def _decode(raw: bytes, content_type: str) -> str:
    """Charset from the header or the page's meta tag, else UTF-8 (most Ethiopian government sites, and Amharic)."""
    declared = re.search(r"charset=[\"']?([\w-]+)", content_type, re.I) or re.search(
        rb"<meta[^>]+charset=[\"']?([\w-]+)", raw[:4096], re.I
    )
    name = declared.group(1) if declared else None
    candidates = [name.decode() if isinstance(name, bytes) else name] if name else []
    for encoding in [*candidates, "utf-8"]:
        try:
            return raw.decode(encoding)
        except (LookupError, UnicodeDecodeError):
            continue
    return raw.decode("utf-8", errors="replace")


def _html_to_text(raw: bytes, content_type: str = "") -> str:
    import lxml.html

    html = re.sub(r"^\s*<\?xml[^>]*\?>", "", _decode(raw, content_type))
    doc = lxml.html.document_fromstring(html)
    for bad in doc.xpath("//script|//style|//noscript|//nav|//header|//footer|//form|//iframe|//svg"):
        bad.drop_tree()
    main = doc.xpath("//main|//article")
    root = main[0] if main else doc
    for br in root.xpath(".//br|.//p|.//li|.//h1|.//h2|.//h3|.//h4|.//tr|.//div"):
        br.tail = "\n" + (br.tail or "")
    return root.text_content()


def _pdf_to_text(raw: bytes) -> tuple[str, int]:
    import pypdfium2 as pdfium

    pdf = pdfium.PdfDocument(raw)
    try:
        pages = [page.get_textpage().get_text_range() for page in pdf]
    finally:
        pdf.close()
    return "\n".join(pages), len(pages)


def extract_text(raw: bytes, content_type: str, url: str = "") -> tuple[str, dict]:
    """Readable text plus a few facts about the document for the run stats."""
    is_pdf = "pdf" in content_type.lower() or raw[:5] == b"%PDF-" or url.lower().endswith(".pdf")
    facts: dict = {"format": "pdf" if is_pdf else "html", "downloaded_kb": round(len(raw) / 1024)}
    if is_pdf:
        text, pages = _pdf_to_text(raw)
        facts["pdf_pages"] = pages
    elif "html" in content_type.lower() or raw.lstrip()[:1] == b"<":
        text = _html_to_text(raw, content_type)
    elif content_type.lower().startswith("text/"):
        text = _decode(raw, content_type)
    else:
        raise RuntimeError(f"Can't read this kind of file ({content_type or 'unknown type'}); use a web page or a PDF")
    text = re.sub(r"[ \t\r\f\v]+", " ", text)
    text = re.sub(r"\n\s*\n+", "\n\n", text).strip()
    return text[:MAX_TEXT_CHARS], facts


def run_source(source_id: str) -> dict:
    """Read the source and replace its passages in the AI knowledge base."""
    src = get_custom(source_id, with_text=True)
    if not src:
        raise RuntimeError("This data source was deleted")
    facts: dict = {}
    if src["kind"] == "web_page":
        raw, content_type = fetch_url(src["url"])
        text, facts = extract_text(raw, content_type, src["url"])
    else:
        text = src["body"] or ""
    if len(text) < MIN_TEXT_CHARS:
        raise RuntimeError("No readable text was found (the page may be empty, a scanned image, or need a login)")
    sid = chunk_service_id(source_id)
    removed = rag_service.delete_chunks(service_id=sid)
    result = rag_service.ingest_text(
        text,
        service_id=sid,
        issuing_body=src["issuing_body"],
        source_url=src["url"],
        language=src["language"],
        topic_tags=[*src["tags"], "custom"],
    )
    return {
        **facts,
        "characters_read": len(text),
        "chunks_removed": removed,
        "chunks_inserted": result.get("chunks_inserted", 0),
    }


def count_chunks(source_ids: list[str]) -> dict[str, int]:
    if not source_ids:
        return {}
    rows = fetch_all(
        "select service_id, count(*) as c from legal_chunks where service_id = any(%s) group by service_id",
        ([chunk_service_id(i) for i in source_ids],),
    )
    by_sid = {r["service_id"]: r["c"] for r in rows}
    return {i: by_sid.get(chunk_service_id(i), 0) for i in source_ids}

