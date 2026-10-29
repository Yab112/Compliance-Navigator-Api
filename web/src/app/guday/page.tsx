import { redirect } from "next/navigation";

type PageProps = { searchParams: Promise<Record<string, string | undefined>> };

/** Guday Geday is now one tab of the marketplace. */
export default async function GudayPage({ searchParams }: PageProps) {
  const { sub_city: area, service_id: serviceId } = await searchParams;
  const next = new URLSearchParams({ type: "guday_geday" });
  if (area) next.set("area", area);
  if (serviceId) next.set("service_id", serviceId);
  redirect(`/hire?${next.toString()}`);
}
