import uuid

from datetime import datetime, timezone



from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status



from core.deps import require_admin

from models.compliance_nodes import DocumentNode, ManualReferenceNode, ServiceNode

from models.compliance_relationships import EnrichesDocumentRel, EnrichesServiceRel

from schemas.auth_user import AuthUser

from services import graph_store

from services.rag_service import ingest_text

from services.storage_service import REFERENCE_MAX_BYTES, check_reference_file, upload_file

from services.roadmap_store import save_manual_reference



router = APIRouter(prefix="/admin/references", tags=["Admin References"])





def _extract_text_from_bytes(content: bytes, filename: str, mime_type: str | None) -> str:

    from pathlib import Path

    import tempfile



    suffix = Path(filename).suffix.lower()

    try:

        if suffix == ".pdf" or (mime_type and "pdf" in mime_type):

            import pdfplumber



            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:

                tmp.write(content)

                tmp.flush()

                parts: list[str] = []

                with pdfplumber.open(tmp.name) as pdf:

                    for page in pdf.pages[:50]:

                        t = page.extract_text()

                        if t:

                            parts.append(t)

                return "\n".join(parts)

        if suffix in (".txt", ".md"):

            return content.decode("utf-8", errors="ignore")

        if suffix == ".docx":

            import tempfile

            import docx



            with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as tmp:

                tmp.write(content)

                tmp.flush()

                doc = docx.Document(tmp.name)

                return "\n".join(p.text for p in doc.paragraphs)

    except Exception:

        return ""

    return ""





@router.post("/upload", status_code=status.HTTP_201_CREATED)

async def upload_reference(

    file: UploadFile = File(...),

    service_id: str = Form(...),

    company_name: str | None = Form(None),

    institution_id: str | None = Form(None),

    notes: str | None = Form(None),

    user: AuthUser = Depends(require_admin),

):

    service = ServiceNode.match(service_id)

    if not service:

        raise HTTPException(status_code=400, detail=f"Unknown service_id: {service_id}")



    ref_id = str(uuid.uuid4())

    # Read one byte past the limit so an oversized file is refused without holding all of it
    content = await file.read(REFERENCE_MAX_BYTES + 1)
    try:
        ext, content_type = check_reference_file(content, file.filename or "")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None
    safe_name = f"reference{ext}"

    file_url = upload_file(content, safe_name, prefix="references", content_type=content_type)

    raw_text = _extract_text_from_bytes(content, safe_name, content_type)

    title = notes or f"{service.name}" + (f", {company_name}" if company_name else "")



    ref = ManualReferenceNode(

        id=ref_id,

        title=title,

        file_url=file_url,

        mime_type=file.content_type,

        uploaded_by=user.email,

        uploaded_at=datetime.now(timezone.utc),

        extraction_status="extracted" if raw_text else "pending",

        raw_text=raw_text or notes,

        verified=False,

        service_id=service_id,

        company_name=company_name,

    )

    ref.create()

    EnrichesServiceRel(source=ref, target=service).merge()



    target_doc_id = None

    targets = [n["id"] for n in graph_store.neighbors("Service", service_id, "TARGETS") if n["label"] == "Document"]

    if targets:

        target_doc_id = targets[0]

        doc = DocumentNode.match(target_doc_id)

        if doc:

            EnrichesDocumentRel(source=ref, target=doc).merge()

            if raw_text and len(raw_text) > 20:

                doc.source_url = doc.source_url or file_url

                doc.merge()



    save_manual_reference(

        ref_id=ref_id,

        title=title,

        service_id=service_id,

        company_name=company_name,

        file_path=file_url,

        mime_type=file.content_type,

        raw_text=raw_text or notes,

        extraction_status=ref.extraction_status,

        user_id=user.id,

        institution_id=institution_id,

    )



    rag_result = None

    if raw_text and len(raw_text) > 20:

        rag_result = ingest_text(

            raw_text,

            document_id=target_doc_id,

            service_id=service_id,

            issuing_body=institution_id or service.name,

            source_url=file_url,

        )



    return {

        "message": "success",

        "payload": {

            "reference_id": ref_id,

            "service_id": service_id,

            "company_name": company_name,

            "file_url": file_url,

            "institution_id": institution_id,

            "extraction_status": ref.extraction_status,

            "text_length": len(raw_text or ""),

            "linked_document": target_doc_id,

            "rag_ingest": rag_result,

        },

    }


