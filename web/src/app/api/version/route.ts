export const dynamic = "force-dynamic";

/**
 * The build this server process is running (inlined at build time), so open pages can tell they
 * are out of date. Not read from disk: a rebuild in progress must not count as a new version.
 */
export function GET() {
  return Response.json({ buildId: process.env.NEXT_PUBLIC_BUILD_ID ?? null }, { headers: { "Cache-Control": "no-store" } });
}
