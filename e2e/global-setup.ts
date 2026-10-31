import { API } from "./lib/env";
import { cleanup } from "./lib/backend";

/** Checks the stack is up and clears anything a crashed earlier run left behind. */
export default async function globalSetup() {
  const res = await fetch(`${API}/legal/documents`).catch((e) => {
    throw new Error(`The API at ${API} is not reachable (${e.message}). Start the stack first.`);
  });
  if (!res.ok) throw new Error(`The API at ${API} answered ${res.status}`);
  await cleanup();
}
