/** Online payments for hires (Chapa, or the simulated test gateway). */

export type PaymentsMode = "off" | "simulated" | "chapa";

/** Payment state on the hire itself */
export type HirePaymentStatus = "unpaid" | "pending" | "paid" | "failed" | "refunded";

/** State of one payment attempt */
export type PaymentStatus = "pending" | "success" | "failed" | "cancelled";

export type PaymentsConfig = {
  mode: PaymentsMode;
  enabled: boolean;
  commission_percent: number;
  /** VAT rate in percent, e.g. 15 */
  vat_rate_percent?: number;
  /** Whether the platform charges VAT on its commission */
  platform_vat_registered?: boolean;
};

export type Bank = { code: string; name: string };

export type PayoutAccount = {
  ready: boolean;
  bank_name: string | null;
  account_name: string | null;
  account_last4: string | null;
  set_at: string | null;
  commission_percent: number;
  mode: PaymentsMode;
  /** The name on the provider's verified ID (Fayda), which the holder name should match */
  verified_name?: string | null;
  /** Whether the holder name matches the verified ID or company name; null when no account yet */
  name_matches?: boolean | null;
  /** A payout is on its way to this account, so it can't be changed now */
  locked?: boolean;
};

export type PayoutInput = {
  bank_code: string;
  account_number: string;
  account_name: string;
};

export type CheckoutStart = { tx_ref: string; checkout_url: string };

export type Payment = {
  tx_ref: string;
  gateway: string;
  amount: number;
  currency: string;
  commission_percent: number;
  commission_amount: number;
  provider_amount: number;
  status: PaymentStatus;
  gateway_reference: string | null;
  payment_method: string | null;
  created_at: string;
  verified_at: string | null;
  engagement_id?: string;
};

export type TestCheckout = {
  tx_ref: string;
  amount: number;
  currency: string;
  status: PaymentStatus;
  gateway: string;
  title: string;
  provider_name: string;
};

/** Why money was received but not credited: the job was already paid, or it was cancelled */
export type UnappliedReason = "duplicate" | "job_closed";

export type AdminPayment = {
  tx_ref: string;
  gateway: string;
  amount: number;
  currency: string;
  price: number | null;
  provider_vat: number;
  commission_amount: number;
  commission_vat: number;
  provider_amount: number;
  gateway_fee: number | null;
  is_test: boolean;
  unapplied_reason: UnappliedReason | null;
  refunded_amount: number;
  /** Still refundable: amount minus what was already refunded */
  refundable: number;
  refund_needed: boolean;
  hire_payment_status: HirePaymentStatus;
  /** Refunds not finished yet (processing, waiting to be sent, or needing a check) */
  refunds_open: number;
  status: PaymentStatus;
  payment_method: string | null;
  gateway_reference: string | null;
  created_at: string;
  verified_at: string | null;
  engagement_id: string;
  title: string;
  client_name: string;
  provider_name: string;
  provider_slug: string;
};

/** gross = price + provider_vat = commission + commission_vat + to_providers (credited payments only). */
export type AdminPaymentTotals = {
  paid_count: number;
  gross: number;
  price: number;
  provider_vat: number;
  commission: number;
  commission_vat: number;
  to_providers: number;
  gateway_fees: number;
  refunded: number;
  commission_refunded: number;
  provider_refunded: number;
  /** Commission plus its VAT, minus what refunds took back */
  net_commission: number;
  /** Extra payments not credited to anyone, waiting for a refund */
  unapplied: number;
  pending: number;
  failed: number;
  needs_refund: number;
};

export type AdminPayments = {
  items: AdminPayment[];
  total: number;
  totals: AdminPaymentTotals;
  mode: PaymentsMode;
  test_mode: boolean;
  /** Live mode: test payments left out of the tiles */
  test_payments: number;
  commission_percent: number;
};

export type AdminPaymentFilters = {
  status?: PaymentStatus;
  q?: string;
  from?: string;
  to?: string;
  needs_refund?: boolean;
  engagement_id?: string;
};

// ---------------------------------------------------------------- refunds

export type RefundStatus = "sending" | "processing" | "refunded" | "manual_pending" | "needs_check" | "failed";

export type Refund = {
  id: string;
  payment_id: string;
  engagement_id: string | null;
  reference: string;
  amount: number;
  price_part: number;
  provider_vat: number;
  commission: number;
  commission_vat: number;
  /** Taken back from the provider's earnings */
  provider_amount: number;
  reason: string;
  method: "gateway" | "manual";
  status: RefundStatus;
  gateway: string | null;
  gateway_ref: string | null;
  is_test: boolean;
  client_bank_name: string | null;
  client_account_name: string | null;
  client_account_last4: string | null;
  /** Only for staff who can refund, only while a manual refund waits to be sent */
  client_account_number?: string | null;
  transfer_reference: string | null;
  requested_by: string | null;
  approved_by: string | null;
  confirmed_by: string | null;
  error: string | null;
  note: string | null;
  created_at: string;
  completed_at: string | null;
  tx_ref: string;
  payment_amount?: number;
  title?: string | null;
  client_name?: string | null;
  provider_name?: string | null;
};

export type RefundInput = {
  /** Leave out to refund everything not refunded yet */
  amount?: number;
  reason: string;
  method: "gateway" | "manual";
  client_bank?: { bank_name: string; account_name: string; account_number: string } | null;
};

/** What a 202 answer carries when an action waits for a second staff member. */
export type ApprovalRequestSummary = { id: string; action: string; summary: string; status: string; title?: string };

export type RefundActionInput = {
  action: "refresh" | "confirm" | "mark_failed";
  note?: string;
  transfer_reference?: string;
};


// ---------------------------------------------------------------- provider earnings and payouts

export type PayoutStatus = "requested" | "approved" | "paid" | "rejected" | "failed";

export type LedgerKind = "earning" | "payout" | "adjustment" | "refund";

export type LedgerEntry = {
  id: string;
  kind: LedgerKind;
  /** Negative for payouts */
  amount: number;
  note: string | null;
  created_at: string;
  job_title: string | null;
  client_name: string | null;
  gross: number | null;
  commission: number | null;
  payout_reference: string | null;
  /** Earnings: the payment, for the statement link */
  tx_ref?: string | null;
  /** Payouts: the payout, for the receipt link */
  payout_id?: string | null;
  /** VAT on the commission, deducted from the provider's share */
  commission_vat?: number | null;
  /** VAT the provider charged the client (VAT-registered providers only) */
  provider_vat?: number | null;
  /** From a test checkout: never withdrawable once payments are live */
  is_test?: boolean;
  /** Refunds: the refund, for the receipt link */
  refund_id?: string | null;
  refund_reference?: string | null;
};

export type Payout = {
  id: string;
  amount: number;
  status: PayoutStatus;
  bank_name: string | null;
  account_name: string | null;
  account_last4: string | null;
  reference: string | null;
  gateway_reference: string | null;
  note: string | null;
  decided_by: string | null;
  decided_at: string | null;
  paid_at: string | null;
  created_at: string;
  is_test?: boolean;
};

export type Earnings = {
  balance: number;
  available: number;
  in_payout: number;
  /** New earnings still inside the dispute window: not withdrawable yet */
  held?: number;
  /** When the oldest held earning is released (ISO date) */
  held_until?: string | null;
  hold_days?: number;
  earned_total: number;
  earned_this_month: number;
  paid_out: number;
  /** Taken back from earnings by client refunds */
  refunded?: number;
  /** Payments are live: test earnings are not counted, they are shown here instead */
  test_balance?: number;
  live?: boolean;
  min_payout: number;
  commission_percent: number;
  payout_account: PayoutAccount;
  ledger: LedgerEntry[];
  payouts: Payout[];
};

export type AdminPayout = StaffPayout & { provider_name: string; provider_slug: string | null };

export type AdminPayoutTotals = {
  requested: number;
  requested_amount: number;
  processing: number;
  /** Approved payouts whose transfer got an error: check with Chapa */
  needs_check?: number;
  paid_amount: number;
  owed_to_providers: number;
};

export type AdminPayouts = {
  items: AdminPayout[];
  total: number;
  totals: AdminPayoutTotals;
  mode: PaymentsMode;
  /** Chapa test key or simulated: nothing real is collected or sent */
  test_mode: boolean;
};

/** hard: can't be approved at all. block: approving needs a written reason. */
export type PayoutCheck = { level: "hard" | "block" | "warn" | "info"; code: string; text: string };

export type StaffPayout = Payout & { bank_code?: string | null; needs_check?: boolean; check_note?: string | null };

/** Everything staff look at before sending a payout. */
export type PayoutReview = {
  payout: StaffPayout & { provider_id: string; gateway: string | null };
  /** Exactly the account the money goes to: the one stored with the request */
  destination: {
    bank_name: string | null;
    account_name: string | null;
    account_last4: string | null;
    stored: boolean;
    /** The name on the provider's verified national ID */
    fayda_name: string | null;
    id_verified: boolean;
  };
  provider: {
    id: string;
    slug: string;
    display_name: string;
    legal_name: string | null;
    verified_name: string | null;
    provider_type: string;
    status: string;
    national_id_verified: boolean;
    id_verification_method: string | null;
    has_tin: boolean;
    trade_license_no: string | null;
    vat_registered: boolean;
    payout_set_at: string | null;
    created_at: string;
  };
  balances: { balance: number; earned_total: number; in_payout: number; paid_out: number; available: number; refunded?: number };
  earnings: {
    amount: number;
    created_at: string;
    hire_id: string | null;
    job_title: string | null;
    tx_ref: string | null;
    gateway: string | null;
    client_paid: number | null;
    client: string | null;
  }[];
  history: { paid_count: number; paid_total: number; refused_count: number };
  checks: PayoutCheck[];
};

export type PayoutDecision = { decision: "approve" | "reject" | "refresh" | "mark_failed"; note?: string };

// ---------------------------------------------------------------- receipts

export type ReceiptIssuer = {
  legal_name: string;
  tin: string | null;
  vat_number: string | null;
  address: string | null;
  vat_registered: boolean;
};

export type ReceiptLine = { label: string; amount: number };

/** Provider (and staff) only: how the payment splits into the provider's earnings. */
export type ReceiptStatement = {
  price: number;
  provider_vat: number;
  commission_percent: number;
  commission: number;
  commission_vat: number;
  vat_rate: number;
  provider_amount: number;
};

export type PaymentReceipt = {
  receipt_no: string;
  kind: "payment";
  paid_at: string | null;
  currency: string;
  notice: string | null;
  issued_by: ReceiptIssuer;
  client: { name: string | null; email: string | null };
  provider: { name: string | null; registration_no: string | null; vat_number: string | null };
  job: { title: string | null; service: string | null; delivered: string | null };
  lines: ReceiptLine[];
  total: number;
  payment: { method: string | null; gateway: string | null; reference: string | null };
  statement?: ReceiptStatement | null;
  is_test?: boolean;
  /** Money given back later; each has its own receipt */
  refunds?: { id: string; reference: string; amount: number; status: RefundStatus; completed_at: string | null }[];
  refunded_amount?: number;
};

export type RefundReceipt = {
  receipt_no: string;
  kind: "refund";
  refunded_at: string | null;
  currency: string;
  notice: string | null;
  issued_by: ReceiptIssuer;
  original: { receipt_no: string; amount: number; paid_at: string | null };
  client: { name: string | null; email: string | null };
  provider: { name: string | null; registration_no: string | null; vat_number: string | null };
  job: { title: string | null; service: string | null };
  reason: string;
  lines: ReceiptLine[];
  total: number;
  method: "gateway" | "manual";
  to: { bank: string | null; account_name: string | null; account_last4: string | null; transfer_reference: string | null } | null;
  reference: string | null;
  /** Provider (and staff) only: what was taken back from each side */
  statement?: { commission: number; commission_vat: number; provider_amount: number; provider_vat: number } | null;
};

export type PayoutReceipt = {
  receipt_no: string;
  kind: "payout";
  paid_at: string | null;
  currency: string;
  notice: string | null;
  issued_by: ReceiptIssuer;
  provider: { name: string | null; registration_no: string | null };
  amount: number;
  to: { bank: string | null; account_name: string | null; account_last4: string | null };
  transfer_reference: string | null;
};

// ---------------------------------------------------------------- payment health

export type GatewayOperation =
  | "initialize"
  | "verify"
  | "transfer"
  | "verify_transfer"
  | "refund"
  | "verify_refund"
  | "banks"
  | "other";

export type PaymentHealthState = "no_calls" | "healthy" | "degraded" | "down";

export type PaymentHealthStatus = {
  status: PaymentHealthState;
  label: string;
  /** Why, in plain words */
  reason: string;
  mode: PaymentsMode;
  last_success_at: string | null;
  last_call_at: string | null;
  last_fault: { error: string | null; http_status: number | null; operation: GatewayOperation; created_at: string } | null;
  calls_last_hour: number;
  faults_last_hour: number;
  refusals_last_hour: number;
  p95_ms_last_hour: number | null;
};

/** failures = faults (no answer, 5xx, key refused, rate limit) + refusals (any other 4xx: Chapa said no) */
export type GatewayCallFigures = {
  calls: number;
  failures: number;
  faults: number;
  refusals: number;
  failure_rate: number;
  avg_ms: number | null;
  p95_ms: number | null;
};

export type GatewayOperationSummary = GatewayCallFigures & {
  operation: GatewayOperation;
  uncertain: number;
  last_success_at: string | null;
  last_failure_at: string | null;
  last_failure_message: string | null;
  last_failure_http_status: number | null;
};

export type PaymentHealthSummary = {
  hours: number;
  operations: GatewayOperationSummary[];
  totals: GatewayCallFigures & { test_calls: number };
};

export type PaymentAttentionItem = {
  kind: "payment" | "payout" | "refund";
  id: string;
  reference: string;
  /** The payment's tx_ref (payments and refunds) */
  tx_ref?: string;
  engagement_id?: string;
  status: string;
  /** needs_check: the money may have moved; failed: it did not; stuck: a checkout still pending */
  problem: "needs_check" | "failed" | "stuck";
  amount: number;
  since: string;
  age_seconds: number;
  is_test: boolean;
  who: string | null;
  reason: string;
};

export type PaymentHealth = {
  status: PaymentHealthStatus;
  summary: PaymentHealthSummary;
  attention: { items: PaymentAttentionItem[]; total: number };
};

export type GatewayCallError = {
  id: number;
  created_at: string;
  operation: GatewayOperation;
  method: string;
  path: string;
  reference: string | null;
  http_status: number | null;
  error: string | null;
  /** The call may have been carried out anyway (no answer or a server error) */
  uncertain: boolean;
  fault: boolean;
  is_test: boolean;
  duration_ms: number;
  belongs_to:
    | { kind: "payment"; id: string; tx_ref: string; engagement_id: string; status: string }
    | { kind: "payout"; id: string; status: string }
    | { kind: "refund"; id: string; tx_ref: string; status: string }
    | null;
};

export type GatewayCallErrors = { items: GatewayCallError[]; total: number; limit: number; offset: number };

export type GatewayLiveCheck = {
  /** null when nothing was sent (test mode or payments off) */
  ok: boolean | null;
  simulated: boolean;
  mode: PaymentsMode;
  latency_ms: number | null;
  http_status: number | null;
  uncertain?: boolean;
  error: string | null;
  message: string;
};
