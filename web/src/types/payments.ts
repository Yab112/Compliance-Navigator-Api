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

export type AdminPayment = {
  tx_ref: string;
  gateway: string;
  amount: number;
  currency: string;
  commission_amount: number;
  provider_amount: number;
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

export type AdminPaymentTotals = {
  paid_count: number;
  gross: number;
  commission: number;
  to_providers: number;
  pending: number;
  failed: number;
};

export type AdminPayments = {
  items: AdminPayment[];
  total: number;
  totals: AdminPaymentTotals;
  mode: PaymentsMode;
  commission_percent: number;
};


// ---------------------------------------------------------------- provider earnings and payouts

export type PayoutStatus = "requested" | "approved" | "paid" | "rejected" | "failed";

export type LedgerKind = "earning" | "payout" | "adjustment";

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
};

export type Earnings = {
  balance: number;
  available: number;
  in_payout: number;
  earned_total: number;
  earned_this_month: number;
  paid_out: number;
  min_payout: number;
  commission_percent: number;
  payout_account: PayoutAccount;
  ledger: LedgerEntry[];
  payouts: Payout[];
};

export type AdminPayout = Payout & { provider_name: string; provider_slug: string | null };

export type AdminPayoutTotals = {
  requested: number;
  requested_amount: number;
  processing: number;
  paid_amount: number;
  owed_to_providers: number;
};

export type AdminPayouts = {
  items: AdminPayout[];
  total: number;
  totals: AdminPayoutTotals;
  mode: PaymentsMode;
};

export type PayoutDecision = { decision: "approve" | "reject" | "refresh"; note?: string };

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
