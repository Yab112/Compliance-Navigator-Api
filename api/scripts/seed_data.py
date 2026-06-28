"""Static seed data — mirrors web/src/constants/addis-locations.ts and process-graph.ts."""

from datetime import date

SEED_DATE = date(2025, 5, 1)

SUB_CITIES = [
    {"id": "addis_ketema", "label": "Addis Ketema", "aliases": ["merkato", "autobus tera"]},
    {"id": "akaki", "label": "Akaki Kaliti", "aliases": ["akaki", "kaliti", "kality"]},
    {"id": "arada", "label": "Arada", "aliases": ["piassa", "piazza", "casanchis"]},
    {"id": "bole", "label": "Bole", "aliases": ["mexico", "summit", "gerji"]},
    {"id": "gulele", "label": "Gulele", "aliases": ["shiromeda", "entoto"]},
    {"id": "kirkos", "label": "Kirkos", "aliases": ["leghar", "old airport"]},
    {"id": "kolfe", "label": "Kolfe Keranio", "aliases": ["saris"]},
    {"id": "lideta", "label": "Lideta", "aliases": ["tekle haymanot"]},
    {"id": "nifas_silk", "label": "Nifas Silk-Lafto", "aliases": ["lafto", "bulbula"]},
    {"id": "yeka", "label": "Yeka", "aliases": ["ferensay", "ayat"]},
]

SERVICES = [
    {"id": "passport", "name": "Passport", "category": "travel", "description": "New or renewal passport through Immigration and Citizenship Service.", "sort_order": 1},
    {"id": "kebele_id", "name": "Kebele ID", "category": "identity", "description": "Local resident identification at your Kebele office.", "sort_order": 2},
    {"id": "tin", "name": "TIN certificate", "category": "tax", "description": "Tax identification number from ERCA.", "sort_order": 3},
    {"id": "commercial_registration", "name": "Commercial registration", "category": "business", "description": "Register your company with MoTRI.", "sort_order": 4},
    {"id": "trade_license", "name": "Trade license", "category": "business", "description": "Sub-city trade bureau license for operating a business.", "sort_order": 5},
    {"id": "fintech_license", "name": "Fintech license", "category": "business", "description": "Full path including NBE fintech permit.", "sort_order": 6},
]

SECTORS = [
    {"id": "fintech", "name": "Fintech", "regulatory_body": "National Bank of Ethiopia"},
    {"id": "banking", "name": "Banking", "regulatory_body": "National Bank of Ethiopia"},
    {"id": "manufacturing", "name": "Manufacturing", "regulatory_body": "Ministry of Trade and Regional Integration"},
]

ENTITY_TYPES = [
    {"id": "PLC", "label": "Private Limited Company"},
    {"id": "sole_prop", "label": "Sole proprietorship"},
]

INSTITUTIONS = [
    {"id": "kebele", "name": "Kebele Office", "portal_url": "https://addisababa.gov.et", "scrape_method": "playwright", "refresh_frequency": "bi-weekly"},
    {"id": "erca", "name": "Ethiopian Revenue and Customs Authority", "portal_url": "https://erca.gov.et", "scrape_method": "beautifulsoup", "refresh_frequency": "weekly"},
    {"id": "motri", "name": "Ministry of Trade and Regional Integration", "portal_url": "https://motrade.gov.et", "scrape_method": "playwright", "refresh_frequency": "weekly"},
    {"id": "nbe", "name": "National Bank of Ethiopia", "portal_url": "https://nbe.gov.et", "scrape_method": "pdf", "refresh_frequency": "monthly"},
    {"id": "ics", "name": "Immigration and Citizenship Service", "portal_url": "https://www.ics.gov.et", "scrape_method": "manual", "refresh_frequency": "monthly"},
]

DOCUMENTS = [
    {
        "id": "birth_certificate",
        "name": "Birth certificate (or witness affidavit)",
        "issuing_authority": "Local Kebele Office",
        "form_code": "KB-BC-01",
        "fee_etb": 50,
        "avg_processing_days": 5,
        "required_input_labels": ["Parent national IDs", "Witness with Kebele ID", "Two passport-size photographs"],
        "rejection_reasons": ["Witness not registered in same Kebele", "Incomplete parent identification"],
        "source_url": "https://addisababa.gov.et",
    },
    {
        "id": "kebele_id",
        "name": "Kebele ID / Resident registration",
        "issuing_authority": "Local Kebele Office",
        "form_code": "KB-ID-02",
        "fee_etb": 0,
        "avg_processing_days": 5,
        "required_input_labels": ["Birth certificate or witness affidavit", "Proof of address", "Two passport-size photographs"],
        "rejection_reasons": ["Address proof missing Kebele stamp", "Photographs do not meet specification"],
    },
    {
        "id": "passport",
        "name": "Ethiopian passport (new / renewal)",
        "issuing_authority": "Immigration and Citizenship Service",
        "form_code": "ICS-P-100",
        "fee_etb": 2500,
        "avg_processing_days": 15,
        "legal_basis": "Immigration Proclamation — passport issuance",
        "required_input_labels": ["Valid Kebele ID", "Birth certificate", "Application form", "Biometric photographs", "Payment receipt"],
        "rejection_reasons": ["Payment receipt not attached", "Photographs wrong background", "Kebele stamp missing"],
        "source_url": "https://www.ics.gov.et",
    },
    {
        "id": "notarized_lease",
        "name": "Notarized lease agreement",
        "issuing_authority": "Sub-city notary office",
        "fee_etb": 500,
        "avg_processing_days": 1,
        "required_input_labels": ["Original lease agreement", "Kebele ID", "Owner consent if applicable"],
        "rejection_reasons": ["Lease missing landlord signature", "Kebele stamp not applied"],
    },
    {
        "id": "tin",
        "name": "TIN certificate",
        "issuing_authority": "Ethiopian Revenue and Customs Authority",
        "form_code": "IT-101",
        "fee_etb": 0,
        "avg_processing_days": 2,
        "legal_basis": "Proc. 1396/2024",
        "required_input_labels": ["Notarized lease", "Kebele ID", "Completed IT-101 form"],
        "rejection_reasons": ["Lease not notarized", "Form IT-101 incomplete"],
        "source_url": "https://erca.gov.et",
    },
    {
        "id": "commercial_registration",
        "name": "Commercial registration",
        "issuing_authority": "Ministry of Trade and Regional Integration",
        "fee_etb": 1200,
        "avg_processing_days": 3,
        "required_input_labels": ["TIN certificate", "Memorandum of association (PLC)", "Name reservation"],
        "rejection_reasons": ["Name reservation expired", "TIN mismatch"],
        "source_url": "https://motrade.gov.et",
    },
    {
        "id": "trade_license",
        "name": "Trade license",
        "issuing_authority": "Sub-city trade bureau",
        "fee_etb": 800,
        "avg_processing_days": 4,
        "required_input_labels": ["Commercial registration certificate", "TIN certificate", "Lease / premises proof"],
        "rejection_reasons": ["Premises proof missing bureau stamp", "Activity code mismatch"],
    },
    {
        "id": "nbe_fintech_permit",
        "name": "NBE fintech permit",
        "issuing_authority": "National Bank of Ethiopia",
        "fee_etb": None,
        "avg_processing_days": 60,
        "legal_basis": "NBE payment instrument issuer directive",
        "sector_specific": True,
        "applicable_sectors": ["fintech"],
        "required_input_labels": ["Trade license", "IT audit report", "Capital adequacy statement", "Business plan"],
        "rejection_reasons": ["Insufficient capital proof", "IT audit outdated"],
        "source_url": "https://nbe.gov.et",
    },
]

# Document A must exist before Document B (A -[:REQUIRES]-> B means B requires A)
REQUIRES_EDGES = [
    ("birth_certificate", "kebele_id"),
    ("kebele_id", "passport"),
    ("birth_certificate", "passport"),
    ("kebele_id", "notarized_lease"),
    ("notarized_lease", "tin"),
    ("kebele_id", "tin"),
    ("tin", "commercial_registration"),
    ("commercial_registration", "trade_license"),
    ("tin", "trade_license"),
    ("trade_license", "nbe_fintech_permit"),
]

SERVICE_TARGETS = {
    "passport": "passport",
    "kebele_id": "kebele_id",
    "tin": "tin",
    "commercial_registration": "commercial_registration",
    "trade_license": "trade_license",
    "fintech_license": "nbe_fintech_permit",
}

SECTOR_EXTRAS = [
    ("fintech", "nbe_fintech_permit"),
]

# Which office template issues which document (office id suffix = sub_city id)
DOC_OFFICE_TEMPLATE = {
    "birth_certificate": "kebele",
    "kebele_id": "kebele",
    "notarized_lease": "notary",
    "tin": "erca",
    "trade_license": "trade",
    "passport": "ics_main",
    "commercial_registration": "motri_main",
    "nbe_fintech_permit": "nbe_main",
}

OFFICE_TEMPLATES = {
    "kebele": {
        "name": "{label} Sub-city Kebele Office",
        "parent_institution": "Addis Ababa City Administration",
        "address_detail": "{label} Sub-city Administration, Kebele services wing, Ground floor",
        "landmark": "Near sub-city administration main gate",
        "latitude": 8.98,
        "longitude": 38.78,
        "phones": ["+251 11 000 0000"],
        "documents_issued": ["birth_certificate", "kebele_id"],
    },
    "notary": {
        "name": "{label} Sub-city Notary Office",
        "parent_institution": "Addis Ababa City Administration",
        "address_detail": "{label} Sub-city justice & notary services",
        "phones": ["+251 11 000 0003"],
        "documents_issued": ["notarized_lease"],
    },
    "erca": {
        "name": "ERCA {label} Branch",
        "parent_institution": "Ethiopian Revenue and Customs Authority",
        "address_detail": "{label} Sub-city, ERCA taxpayer service centre",
        "phones": ["+251 11 000 0001"],
        "documents_issued": ["tin"],
    },
    "trade": {
        "name": "{label} Sub-city Trade Bureau",
        "parent_institution": "Addis Ababa Trade Bureau",
        "address_detail": "{label} Sub-city trade licensing desk",
        "phones": ["+251 11 000 0002"],
        "documents_issued": ["trade_license"],
    },
    "ics_main": {
        "name": "Immigration and Citizenship Service — Main Department",
        "parent_institution": "Immigration and Citizenship Service",
        "address_detail": "Addis Ababa, around Mexico Square, Main Department building",
        "landmark": "ICS Main Department",
        "latitude": 9.005,
        "longitude": 38.75,
        "phones": ["+251 11 662 7688"],
        "documents_issued": ["passport"],
    },
    "motri_main": {
        "name": "MoTRI Business Registration Office",
        "parent_institution": "Ministry of Trade and Regional Integration",
        "address_detail": "Addis Ababa, MoTRI main registration hall",
        "phones": ["+251 11 000 0004"],
        "documents_issued": ["commercial_registration"],
    },
    "nbe_main": {
        "name": "National Bank of Ethiopia — Licensing",
        "parent_institution": "National Bank of Ethiopia",
        "address_detail": "NBE headquarters, licensing division",
        "phones": ["+251 11 000 0005"],
        "documents_issued": ["nbe_fintech_permit"],
    },
}
