"""Clients pay the platform; providers withdraw their earnings.

Flow: the provider delivers and that requests payment -> the client pays the agreed price to our
account -> the job closes and the provider's share (price minus commission) is credited to their
earnings balance (provider_ledger) -> the provider requests a payout -> staff approve -> we send it
to the provider's own bank account (Chapa transfer; simulated in test mode) -> payout history.

Gateways sit behind one small interface, so another provider (YaGout, Telebirr) can be added:
  banks()                 banks a provider can be paid into
  initialize(...)         start a checkout, returns the URL to send the client to
  verify(tx_ref)          ask the gateway what really happened (never trust the redirect)
  transfer(...)           send a payout to a bank account
  verify_transfer(ref)    ask whether a payout arrived (or, later, whether it came back)
  refund(...)             give a client money back (all or part of a payment)
  verify_refund(ref_id)   ask whether a refund reached the client

Money safety rules (see tests/test_money_safety.py):
  - a payout is claimed with a conditional update, so only one approval ever sends it
  - a payout goes to the account it was requested with, stored encrypted on the payout row
  - a transfer or refund error that does not prove the money stayed is marked "needs checking",
    and nothing is released until the gateway confirms it failed
  - money from test checkouts never counts as withdrawable once payments are live
  - a second successful payment for the same job is never credited; it is flagged for a refund
  - a paid transfer that comes back is flagged by a daily check; it goes back into the provider's balance only
    once Chapa says it failed or was returned and a second staff member approves, and is credited once

PAYMENTS_MODE: off | simulated (a local test checkout, no money moves) | chapa
"""

# Submodules import each other directly. gateway, gateway_named, get and confirm are read through this
# package (payment_service.gateway()) so a monkeypatch on the package (tests/test_money_safety.py fakes
# the gateway) reaches every caller, as it did when this was one module.

from config.config import settings  # noqa: F401  (re-exported)

from .calls import prune as prune_gateway_calls  # noqa: F401
from .checkout import (  # noqa: F401
    breakdown,
    check_pending_payments,
    checkout_view,
    confirm,
    get,
    simulate,
    start,
)
from .earnings import (  # noqa: F401
    admin_payouts,
    earnings,
    ledger_page,
    payouts_page,
    request_payout,
)
from .gateways import (  # noqa: F401
    ChapaGateway,
    PaymentError,
    SimulatedGateway,
    enabled,
    gateway,
    gateway_named,
    mode,
    webhook_signature_ok,
)
from .health import (  # noqa: F401
    attention,
    live_check,
    recent_errors,
)
from .health import overview as health_overview  # noqa: F401
from .health import status as health_status  # noqa: F401
from .health import summary as health_summary  # noqa: F401
from .payout_account import (  # noqa: F401
    banks,
    names_match,
    payout_view,
    set_payout,
)
from .payouts import (  # noqa: F401
    check_paid_payouts,
    check_processing_payouts,
    decide_payout,
    execute_payout_return,
    payout_review,
)
from .receipts import (  # noqa: F401
    payment_receipt,
    payout_receipt,
    refund_receipt,
)
from .refunds import (  # noqa: F401
    admin_refunds,
    check_sending_refunds,
    execute_refund,
    refund_action,
    refund_figures,
    refund_plan,
)
from .staff import (  # noqa: F401
    admin_csv,
    admin_list,
    admin_verify,
)
