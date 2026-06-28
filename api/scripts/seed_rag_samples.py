"""
Seed sample legal chunks into Supabase pgvector.

Requires SUPABASE_URL + SUPABASE_SERVICE_ROLE_KEY in api/.env
and migration 001_initial.sql applied.

Run: uv run python -m scripts.seed_rag_samples
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from services.rag_service import ingest_text
from services.supabase_client import is_supabase_configured


SAMPLES = [
    {
        "text": """
        Immigration Proclamation — Ethiopian passport issuance requires valid Kebele ID,
        birth certificate, biometric photographs per ICS specification, and payment receipt.
        Processing at Immigration and Citizenship Service Main Department typically
        requires 10 to 21 business days. Common rejections include incorrect photo
        background, missing Kebele stamp on supporting letters, and unpaid fees.
        """,
        "document_id": "passport",
        "service_id": "passport",
        "proclamation_number": "Immigration Proclamation",
        "issuing_body": "Immigration and Citizenship Service",
        "source_url": "https://www.ics.gov.et",
        "topic_tags": ["passport", "travel"],
    },
    {
        "text": """
        Proc. 1396/2024 — Tax Identification Number registration at ERCA requires
        notarized lease agreement, Kebele ID, and completed form IT-101.
        TIN issuance is typically within 1 to 2 business days at sub-city taxpayer
        service centres. Rejections include non-notarized lease or incomplete IT-101.
        """,
        "document_id": "tin",
        "service_id": "tin",
        "proclamation_number": "1396/2024",
        "issuing_body": "Ethiopian Revenue and Customs Authority",
        "source_url": "https://erca.gov.et",
        "topic_tags": ["TIN", "tax_registration"],
    },
    {
        "text": """
        Sub-city trade bureau trade license requires commercial registration certificate,
        TIN certificate, and business premises proof. Fees and timelines vary by sub-city.
        Premises proof must bear bureau stamp. Activity code must match commercial registration.
        """,
        "document_id": "trade_license",
        "service_id": "trade_license",
        "issuing_body": "Addis Ababa Trade Bureau",
        "topic_tags": ["trade_license", "business"],
    },
    {
        "text": """
        National Bank of Ethiopia fintech permit directive requires existing trade license,
        IT audit report, capital adequacy statement, and business plan. Licensing division
        review may take 6 to 12 weeks. Insufficient capital proof is a frequent rejection reason.
        """,
        "document_id": "nbe_fintech_permit",
        "service_id": "fintech_license",
        "issuing_body": "National Bank of Ethiopia",
        "source_url": "https://nbe.gov.et",
        "topic_tags": ["fintech", "NBE"],
        "sector_tags": ["fintech"],
    },
]


def main() -> None:
    if not is_supabase_configured():
        print("Supabase not configured. Set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY.")
        sys.exit(1)

    total = 0
    for sample in SAMPLES:
        result = ingest_text(**sample)
        n = result.get("chunks_inserted", 0)
        total += n
        print(f"  {sample['document_id']}: {n} chunks ({result.get('status')})")

    print(f"Done. {total} chunks inserted.")


if __name__ == "__main__":
    main()
