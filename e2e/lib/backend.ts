import { spawn } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import { PYTHON, PYTHON_CWD, REPO } from "./env";

const HELPER = path.join(REPO, "e2e/helpers/backend.py");

/** Splits E2E_PYTHON like a shell would for simple commands (no quoting needed in practice). */
function pythonCommand(): [string, string[]] {
  const [cmd, ...rest] = PYTHON.trim().split(/\s+/);
  return [cmd, rest];
}

/**
 * Runs the API's Python with `args`, writing `input` to stdin. Detached (a new session without a terminal),
 * so getpass in scripts.create_staff reads the password from stdin instead of prompting the person running
 * the suite.
 */
export function runPython(args: string[], input = "", timeoutMs = 120_000): Promise<string> {
  const [cmd, pre] = pythonCommand();
  return new Promise((resolve, reject) => {
    const child = spawn(cmd, [...pre, ...args], {
      cwd: PYTHON_CWD,
      detached: true,
      stdio: ["pipe", "pipe", "pipe"],
      env: { ...process.env, PYTHONUNBUFFERED: "1" },
    });
    let out = "";
    let err = "";
    const timer = setTimeout(() => {
      child.kill("SIGKILL");
      reject(new Error(`python ${args[0]} timed out`));
    }, timeoutMs);
    child.stdout.on("data", (d) => (out += d));
    child.stderr.on("data", (d) => (err += d));
    child.on("error", (e) => {
      clearTimeout(timer);
      reject(e);
    });
    child.on("close", (code) => {
      clearTimeout(timer);
      if (code === 0) resolve(out);
      else reject(new Error(`python ${args.join(" ").slice(0, 80)} exited ${code}: ${err.slice(-1500)}`));
    });
    child.stdin.end(input);
  });
}

/** One command of e2e/helpers/backend.py; returns its JSON answer. */
export async function helper<T = Record<string, unknown>>(command: string, args: object = {}): Promise<T> {
  const out = await runPython(["-", command, JSON.stringify(args)], fs.readFileSync(HELPER, "utf8"));
  const last = out.trim().split("\n").pop() ?? "{}";
  return JSON.parse(last) as T;
}

export type SampleProvider = { slug: string; provider_id: string; user_id: string; display_name: string };

/** A sample provider that is ready to work (seeds them first on an empty database). */
export async function readyProvider(): Promise<SampleProvider> {
  await runPython(["-m", "scripts.seed_providers", "--make-ready"], "", 300_000);
  let p = await helper<Partial<SampleProvider>>("provider");
  if (!p.slug) {
    await runPython(["-m", "scripts.seed_providers"], "", 300_000);
    await runPython(["-m", "scripts.seed_providers", "--make-ready"], "", 300_000);
    p = await helper<Partial<SampleProvider>>("provider");
  }
  if (!p.slug) throw new Error("No ready sample provider after seeding");
  return p as SampleProvider;
}

/** The provider side of a hire: accept (with a price), start, complete (with a note). */
export function providerAction(hire: string, action: "accept" | "start" | "complete", extra: { price?: number; note?: string } = {}) {
  return helper<{ status: string }>("provider-action", { hire, action, ...extra });
}

export function notify(email: string, title: string, body?: string) {
  return helper("notify", { email, title, body });
}

/** Deletes what these accounts made. Without emails: every e2e-suite- account (leftovers from any run). */
export function cleanup(emails?: string[]) {
  return helper("cleanup", emails ? { emails } : {});
}

/** A staff Super admin made with scripts.create_staff; the password is only ever in memory. */
export async function createStaff(email: string, fullname: string, password: string): Promise<void> {
  await runPython(["-m", "scripts.create_staff", email, fullname], `${password}\n${password}\n`);
}
