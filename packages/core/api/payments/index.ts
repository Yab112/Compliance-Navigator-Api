"use client";

import { useQueryClient } from "@tanstack/react-query";
import { useAdminMutation, useAdminQuery } from "../admin/use-admin-query";
import { withQuery } from "../catalog/with-query";
import useMutationFunc from "../../hooks/use-mutation";
import { useFetchData } from "../../hooks/use-query";
import { apiPaths } from "../../lib/constants/api-paths";
import { MTD } from "../../lib/constants/methods";
import type { APIResponse } from "../../types/global";
import type { Paged } from "../../types/guday";
import type {
  AdminPayments,
  AdminPayouts,
  PayoutReview,
  Bank,
  CheckoutStart,
  Earnings,
  LedgerEntry,
  Payment,
  PaymentReceipt,
  PaymentStatus,
  PaymentsConfig,
  Payout,
  PayoutAccount,
  PayoutDecision,
  PayoutReceipt,
  PayoutInput,
  PayoutStatus,
  TestCheckout,
} from "../../types/payments";

const pay = apiPaths.payments;

/** Birr amount for display, e.g. 1200 -> "1,200" */
export function formatBirr(amount: number | null | undefined): string {
  if (amount == null) return "";
  return Number(amount).toLocaleString("en-US", { maximumFractionDigits: 2 });
}

/** Money with two decimals and the currency, e.g. 1080 -> "1,080.00 ETB" */
export function formatETB(amount: number | null | undefined): string {
  return `${Number(amount ?? 0).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })} ETB`;
}

/** Refresh every list that shows a hire's price, payment or unread count. */
function useRefreshHires() {
  const queryClient = useQueryClient();
  return () =>
    Promise.all(
      [["hires"], ["providers", "me"], ["admin", "market"]].map((queryKey) => queryClient.invalidateQueries({ queryKey })),
    );
}

// ---------------------------------------------------------------- config and banks

/** Whether online payment is on, and the platform commission; public. */
export const usePaymentsConfig = () =>
  useFetchData<APIResponse<PaymentsConfig>>(["payments", "config"], pay.config, { staleTime: 10 * 60 * 1000, retry: false });

export const useBanks = (enabled = true) =>
  useFetchData<APIResponse<{ items: Bank[] }>>(["payments", "banks"], pay.banks, { enabled, staleTime: 60 * 60 * 1000 });

// ---------------------------------------------------------------- provider payout account

export const useMyPayout = (enabled = true) =>
  useFetchData<APIResponse<{ payout: PayoutAccount }>>(["providers", "me", "payout"], apiPaths.providers.mePayout, {
    enabled,
    staleTime: 0,
  });

export const useSavePayout = () => {
  const queryClient = useQueryClient();
  const { mutateAsync, isPending } = useMutationFunc<APIResponse<{ payout: PayoutAccount }>, PayoutInput>();
  const save = async (body: PayoutInput) => {
    const res = await mutateAsync({ url: apiPaths.providers.mePayout, method: MTD.PUT, body });
    await queryClient.invalidateQueries({ queryKey: ["providers", "me"] });
    return res.payload.payout;
  };
  return { save, isPending };
};

// ---------------------------------------------------------------- provider earnings and withdrawals

/** Balance, ledger and payout history for the signed-in provider. */
export const useMyEarnings = (enabled = true) =>
  useFetchData<APIResponse<Earnings>>(["providers", "me", "earnings"], apiPaths.providers.meEarnings, {
    enabled,
    staleTime: 0,
  });

export const MONEY_PAGE_SIZE = 20;

/** One page of the provider's money ledger (newest first). */
export const useMyLedger = (page = 0, enabled = true) =>
  useFetchData<APIResponse<Paged<LedgerEntry>>>(
    ["providers", "me", "earnings", "ledger", page],
    withQuery(apiPaths.providers.meEarningsLedger, { limit: MONEY_PAGE_SIZE, offset: page * MONEY_PAGE_SIZE }),
    { enabled, staleTime: 0 },
  );

/** One page of the provider's withdrawals (newest first). */
export const useMyPayouts = (page = 0, enabled = true) =>
  useFetchData<APIResponse<Paged<Payout>>>(
    ["providers", "me", "payouts", page],
    withQuery(apiPaths.providers.mePayouts, { limit: MONEY_PAGE_SIZE, offset: page * MONEY_PAGE_SIZE }),
    { enabled, staleTime: 0 },
  );

/** Ask for a withdrawal of `amount` ETB to the saved payout account. */
export const useRequestPayout = () => {
  const queryClient = useQueryClient();
  const { mutateAsync, isPending } = useMutationFunc<APIResponse<{ payout: Payout }>, { amount: number }>();
  const request = async (amount: number) => {
    const res = await mutateAsync({ url: apiPaths.providers.mePayouts, method: MTD.POST, body: { amount } });
    await queryClient.invalidateQueries({ queryKey: ["providers", "me"] });
    return res.payload.payout;
  };
  return { request, isPending };
};

// ---------------------------------------------------------------- provider price

export type JobPriceBody =
  | { action: "accept"; price?: number; price_note?: string }
  | { action: "set_price"; price: number; price_note?: string };

// ---------------------------------------------------------------- client pays

/** Start a checkout for a hire and send the browser to the gateway. */
export const usePayHire = () => {
  const refresh = useRefreshHires();
  const { mutateAsync, isPending } = useMutationFunc<APIResponse<CheckoutStart>, undefined>();
  const payHire = async (hireId: string) => {
    const res = await mutateAsync({ url: apiPaths.hires.pay(hireId), method: MTD.POST });
    void refresh();
    window.location.href = res.payload.checkout_url;
    return res.payload;
  };
  return { payHire, isPending };
};

/** Re-verifies with the gateway on every call. With `poll`, refetches every 3 s while the payment is pending. */
export const usePayment = (txRef: string | null, poll = false) =>
  useFetchData<APIResponse<{ payment: Payment }>>(["payments", "payment", txRef], pay.payment(txRef ?? ""), {
    enabled: !!txRef,
    staleTime: 0,
    retry: false,
    refetchInterval: poll
      ? (query) => (!query.state.data || query.state.data.payload.payment.status === "pending" ? 3000 : false)
      : false,
    refetchOnWindowFocus: false,
  });

// ---------------------------------------------------------------- receipts

/** Receipt for a paid hire; the provider (and staff) also get `statement`. 404 for anyone else or unpaid. */
export const usePaymentReceipt = (txRef: string, enabled = true) =>
  useFetchData<APIResponse<{ receipt: PaymentReceipt }>>(["payments", "receipt", txRef], pay.receipt(txRef), {
    enabled: enabled && !!txRef,
    retry: false,
  });

/** Receipt for a paid withdrawal; owner or staff. */
export const usePayoutReceipt = (id: string, enabled = true) =>
  useFetchData<APIResponse<{ receipt: PayoutReceipt }>>(["payouts", "receipt", id], pay.payoutReceipt(id), {
    enabled: enabled && !!id,
    retry: false,
  });

/** Fallback VAT rate (fraction) until GET /payments/config answers; the config value wins. */
export const VAT_RATE = 0.15;

export type PriceRules = {
  /** The provider is VAT-registered: VAT is added to the client price */
  vatRegistered: boolean;
  commissionPercent: number;
  /** From GET /payments/config `vat_rate_percent` */
  vatRatePercent?: number;
  /** From GET /payments/config `platform_vat_registered`: VAT on the commission only when true */
  platformVatRegistered?: boolean;
};

/** Price rules from GET /payments/config, so estimates match what payment_service.breakdown() charges. */
export function priceRules(config: PaymentsConfig | undefined, vatRegistered: boolean): PriceRules {
  return {
    vatRegistered,
    commissionPercent: config?.commission_percent ?? 10,
    vatRatePercent: config?.vat_rate_percent,
    platformVatRegistered: config?.platform_vat_registered,
  };
}

/** Same rules as the API: provider VAT only for VAT-registered providers, VAT on commission only when the platform is VAT-registered. */
export function priceBreakdown(price: number, rules: PriceRules) {
  const round = (n: number) => Math.round(n * 100) / 100;
  const rate = rules.vatRatePercent != null ? rules.vatRatePercent / 100 : VAT_RATE;
  const vat = rules.vatRegistered ? round(price * rate) : 0;
  const commission = round((price * rules.commissionPercent) / 100);
  const commissionVat = (rules.platformVatRegistered ?? true) ? round(commission * rate) : 0;
  return {
    price,
    vat,
    clientPays: round(price + vat),
    commission,
    commissionVat,
    providerGets: round(price + vat - commission - commissionVat),
  };
}

// ---------------------------------------------------------------- test checkout (simulated mode)

export const useTestCheckout = (txRef: string, enabled = true) =>
  useFetchData<APIResponse<{ checkout: TestCheckout }>>(["payments", "checkout", txRef], pay.checkout(txRef), {
    enabled: enabled && !!txRef,
    staleTime: 0,
    retry: false,
  });

export const useSimulatePayment = () => {
  const refresh = useRefreshHires();
  const { mutateAsync, isPending } = useMutationFunc<APIResponse<{ payment: Payment }>, { outcome: "success" | "failed" }>();
  const simulate = async (txRef: string, outcome: "success" | "failed") => {
    const res = await mutateAsync({ url: pay.simulate(txRef), method: MTD.POST, body: { outcome } });
    await refresh();
    return res.payload.payment;
  };
  return { simulate, isPending };
};

// ---------------------------------------------------------------- staff

export const ADMIN_MONEY_PAGE_SIZE = 25;

export const useAdminPayments = (status?: PaymentStatus, page = 0) =>
  useAdminQuery<AdminPayments>(
    ["market", "payments", status ?? "all", page],
    withQuery(apiPaths.admin.marketPayments, { status, limit: ADMIN_MONEY_PAGE_SIZE, offset: page * ADMIN_MONEY_PAGE_SIZE }),
  );

/** Provider withdrawal requests, filtered by status (the API defaults to "requested"). */
export const useAdminPayouts = (status: PayoutStatus, page = 0) =>
  useAdminQuery<AdminPayouts>(
    ["market", "payouts", status, page],
    withQuery(apiPaths.admin.marketPayouts, { status, limit: ADMIN_MONEY_PAGE_SIZE, offset: page * ADMIN_MONEY_PAGE_SIZE }),
  );

/** Who gets a payout, whether the account is theirs, and which payments fund it. */
export const useAdminPayoutReview = (id: string, enabled = true) =>
  useAdminQuery<PayoutReview>(["market", "payout", id], apiPaths.admin.marketPayout(id), { enabled });

/** Approve (sends the money; a blocking check needs a note), reject (needs a note) or refresh a processing payout. */
export const useDecidePayout = () => {
  const { run, isPending } = useAdminMutation<{ payout: Payout }, PayoutDecision>();
  const decide = (id: string, body: PayoutDecision) => run(apiPaths.admin.marketPayout(id), MTD.POST, body).then((p) => p.payout);
  return { decide, isPending };
};
