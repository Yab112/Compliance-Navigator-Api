// Run: node --test packages/core/lib/safe-redirect.test.mts  (Node 22.18+ runs TypeScript directly)
import assert from "node:assert/strict";
import { test } from "node:test";
import { safeReturnTo } from "./safe-redirect.ts";

test("keeps same-site paths with their query and hash", () => {
  assert.equal(safeReturnTo("/providers/abebe?tab=reviews#top"), "/providers/abebe?tab=reviews#top");
  assert.equal(safeReturnTo("/"), "/");
  assert.equal(safeReturnTo("/org/1/services", "/x"), "/org/1/services");
});

test("refuses anything that could leave the site", () => {
  const bad = [
    null,
    undefined,
    "",
    "evil.com",
    "https://evil.com",
    "//evil.com",
    "/\\evil.com",
    "/\t/evil.com",
    "/%09/evil.com",
    "/\n/evil.com",
    "/%0a/evil.com",
    "/%2f/evil.com",
    "/%2F%2Fevil.com",
    "/%5c/evil.com",
    "/path\\..\\..\\evil",
    "/ /evil.com",
    "/\u0000/evil.com",
    "javascript:alert(1)",
    "/\u007f/evil.com",
  ];
  for (const value of bad) assert.equal(safeReturnTo(value, "/fallback"), "/fallback", String(value));
});

test("whatever comes out, a browser resolves it to this site", () => {
  const origin = "https://navigator.example";
  for (const value of ["/a", "/a/../b", "/a?next=//evil.com", "/./", "/..//evil.com"]) {
    const out = safeReturnTo(value, "/fallback");
    assert.equal(new URL(out, origin).origin, origin, value);
  }
});
