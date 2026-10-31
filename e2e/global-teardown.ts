import { cleanup } from "./lib/backend";

/** A safety net: every spec cleans up after itself, this catches what a failed one left. */
export default async function globalTeardown() {
  await cleanup();
}
