"""Receipts for payments, payouts and refunds."""

from __future__ import annotations

from services import platform_settings
from services.db import fetch_all, fetch_one

from .earnings import PAYOUT_COLUMNS
from .gateways import PaymentError
from .refunds import REFUND_COLUMNS

# ---------------------------------------------------------------- receipts

RECEIPT_NOTICE = ("This is a payment receipt from Compliance Navigator. It is not a tax invoice registered in the "
                  "Ministry of Revenues electronic invoicing system.")


def _issuer() -> dict:
    get = platform_settings.get
    return {"legal_name": get("legal_name"), "tin": get("tin") or None, "vat_number": get("vat_number") or None,
            "address": get("address"), "vat_registered": get("platform_vat_registered")}


def payment_receipt(tx_ref: str, *, user) -> dict:
    """The client's receipt; the provider (and staff) also see their statement: commission, VAT on it, their share."""
    row = fetch_one(
        """
        select p.tx_ref, p.status, p.currency, p.amount::float, p.price::float, p.vat_rate::float, p.provider_vat::float,
               p.commission_percent::float, p.commission_amount::float, p.commission_vat::float, p.provider_amount::float,
               p.provider_vat_number, p.payment_method, p.gateway, p.gateway_reference, p.verified_at, p.updated_at,
               e.title, e.service_name, e.completion_note, e.client_name, e.client_user_id::text, u.email as client_email,
               pr.display_name as provider_name, pr.registration_no as provider_registration_no,
               pr.user_id::text as provider_user_id, p.is_test, p.refunded_amount::float
        from payments p
        join engagements e on e.id = p.engagement_id
        left join users u on u.id = e.client_user_id
        left join providers pr on pr.id = e.provider_id
        where p.tx_ref = %s
        """,
        (tx_ref,),
    )
    if not row or row["status"] != "success":
        raise PaymentError("Receipt not found", 404)
    is_client = row["client_user_id"] == user.id
    is_provider = row["provider_user_id"] == user.id
    if not (is_client or is_provider or user.is_admin):
        raise PaymentError("Receipt not found", 404)
    receipt = {
        "receipt_no": row["tx_ref"], "kind": "payment", "paid_at": row["verified_at"] or row["updated_at"],
        "currency": row["currency"], "issued_by": _issuer(), "notice": RECEIPT_NOTICE,
        "client": {"name": row["client_name"], "email": row["client_email"]},
        "provider": {"name": row["provider_name"], "registration_no": row["provider_registration_no"],
                     "vat_number": row["provider_vat_number"]},
        "job": {"title": row["title"], "service": row["service_name"], "delivered": row["completion_note"]},
        "lines": [{"label": "Service by " + (row["provider_name"] or "provider"), "amount": row["price"]}]
                 + ([{"label": f"VAT {row['vat_rate']:g}% charged by the provider", "amount": row["provider_vat"]}]
                    if row["provider_vat"] else []),
        "total": row["amount"],
        "payment": {"method": row["payment_method"], "gateway": row["gateway"], "reference": row["gateway_reference"]},
        "is_test": row["is_test"],
        # Money given back later has its own receipts; the original receipt never changes
        "refunds": fetch_all(
            "select r.id::text, r.reference, r.amount::float, r.status, r.completed_at from refunds r "
            "join payments p on p.id = r.payment_id where p.tx_ref = %s and r.status <> 'failed' order by r.created_at",
            (tx_ref,)),
        "refunded_amount": row["refunded_amount"],
    }
    if is_provider or user.is_admin:
        receipt["statement"] = {
            "price": row["price"], "provider_vat": row["provider_vat"],
            "commission_percent": row["commission_percent"], "commission": row["commission_amount"],
            "commission_vat": row["commission_vat"], "vat_rate": row["vat_rate"],
            "provider_amount": row["provider_amount"],
        }
    return receipt


def payout_receipt(payout_id: str, *, user) -> dict:
    row = fetch_one(
        f"select {PAYOUT_COLUMNS}, pr.display_name as provider_name, pr.registration_no, pr.user_id::text as owner "
        "from payouts po join providers pr on pr.id = po.provider_id where po.id::text = %s",
        (payout_id,),
    )
    if not row or row["status"] != "paid" or not (row["owner"] == user.id or user.is_admin):
        raise PaymentError("Receipt not found", 404)
    return {
        "receipt_no": row["reference"], "kind": "payout", "paid_at": row["paid_at"], "currency": "ETB",
        "issued_by": _issuer(), "notice": "Withdrawal of earnings to the provider's own bank account.",
        "provider": {"name": row["provider_name"], "registration_no": row["registration_no"]},
        "amount": row["amount"],
        "to": {"bank": row["bank_name"], "account_name": row["account_name"], "account_last4": row["account_last4"]},
        "transfer_reference": row["gateway_reference"],
    }


def refund_receipt(refund_id: str, *, user) -> dict:
    """The client's refund receipt; the provider (and staff) also see what was taken back from each side."""
    try:
        row = fetch_one(
            f"""
            select {REFUND_COLUMNS}, p.tx_ref, p.currency, p.amount::float as payment_amount, p.vat_rate::float,
                   p.provider_vat_number, p.verified_at as paid_at,
                   e.title, e.service_name, e.client_name, e.client_user_id::text, u.email as client_email,
                   pr.display_name as provider_name, pr.registration_no as provider_registration_no,
                   pr.user_id::text as provider_user_id
            from refunds r
            join payments p on p.id = r.payment_id
            join engagements e on e.id = p.engagement_id
            left join users u on u.id = e.client_user_id
            left join providers pr on pr.id = e.provider_id
            where r.id = %s
            """,
            (refund_id,),
        )
    except Exception:  # noqa: BLE001 (a malformed id is simply not found)
        row = None
    if not row or row["status"] != "refunded":
        raise PaymentError("Receipt not found", 404)
    is_client = row["client_user_id"] == user.id
    is_provider = row["provider_user_id"] == user.id
    if not (is_client or is_provider or user.is_admin):
        raise PaymentError("Receipt not found", 404)
    receipt = {
        "receipt_no": row["reference"], "kind": "refund", "refunded_at": row["completed_at"],
        "currency": row["currency"], "issued_by": _issuer(),
        "notice": "Money given back to the client for the payment below. It is not a tax credit note registered in "
                  "the Ministry of Revenues electronic invoicing system.",
        "original": {"receipt_no": row["tx_ref"], "amount": row["payment_amount"], "paid_at": row["paid_at"]},
        "client": {"name": row["client_name"], "email": row["client_email"]},
        "provider": {"name": row["provider_name"], "registration_no": row["provider_registration_no"],
                     "vat_number": row["provider_vat_number"]},
        "job": {"title": row["title"], "service": row["service_name"]},
        "reason": row["reason"],
        "lines": [{"label": "Service by " + (row["provider_name"] or "provider"), "amount": row["price_part"]}]
                 + ([{"label": f"VAT {row['vat_rate']:g}% charged by the provider", "amount": row["provider_vat"]}]
                    if row["provider_vat"] else []),
        "total": row["amount"],
        "method": row["method"],
        "to": ({"bank": row["client_bank_name"], "account_name": row["client_account_name"],
                "account_last4": row["client_account_last4"], "transfer_reference": row["transfer_reference"]}
               if row["method"] == "manual" else None),
        "reference": row["gateway_ref"],
    }
    if is_provider or user.is_admin:
        receipt["statement"] = {
            "commission": row["commission"], "commission_vat": row["commission_vat"],
            "provider_amount": row["provider_amount"], "provider_vat": row["provider_vat"],
        }
    return receipt
