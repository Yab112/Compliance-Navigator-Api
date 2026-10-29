/** Shared marketplace helpers and Fayda (National ID Program) verification types. */

export type AgentEvent = {
  id: number;
  action: string;
  actor?: string | null;
  note?: string | null;
  created_at: string;
};

/** Admin overview numbers for the marketplace (kept under the `guday` key) */
export type GudayStats = {
  agents: Partial<Record<"pending" | "approved" | "rejected" | "suspended", number>>;
  cases: Partial<Record<string, number>>;
  approvedBySubCity: { sub_city: string; c: number }[];
  licensesExpiringIn30Days: number;
};

export type Paged<T> = { total: number; items: T[] };

export type FaydaMode = "off" | "sandbox" | "live";

export type IdVerification = {
  id: string;
  mode: "sandbox" | "live";
  status: "verified";
  method: "fayda" | "fayda_sandbox";
  id_type: "FIN" | "FCN" | "SUB";
  id_last4: string;
  masked_id: string;
  verified_name?: string | null;
  birthdate?: string | null;
  gender?: string | null;
  verified_at: string;
};

export type FaydaStatus = { mode: FaydaMode; required: boolean; verification: IdVerification | null };
