"use client";

import Link from "next/link";
import { useState } from "react";
import { useMarketAction } from "@cn/core/api/providers";
import { Button } from "@cn/ui/button";
import { Input } from "@cn/ui/input";
import { apiPaths } from "@cn/core/lib/constants/api-paths";
import { MTD } from "@cn/core/lib/constants/methods";
import { getErrorMessage } from "@cn/core/lib/errors";
import { cn } from "@cn/core/lib/utils";
import type { MyProvider } from "@cn/core/types/provider";
import { ProviderAvatar } from "@cn/ui/marketplace/provider-avatar";
import { Card } from "@/modules/marketplace/components/my-provider/shared";

export function Team({ p }: { p: MyProvider }) {
  const { run, isPending } = useMarketAction<Record<string, string>>();
  const [slug, setSlug] = useState("");
  const [role, setRole] = useState("");
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);
  const call = async (url: string, body: Record<string, string>, ok: string) => {
    setMsg(null);
    try {
      await run(url, MTD.POST, body);
      setMsg({ ok: true, text: ok });
      setSlug("");
    } catch (err) {
      setMsg({ ok: false, text: getErrorMessage(err) });
    }
  };
  const membership = (id: string, action: string) => call(apiPaths.providers.membership(id), { action }, "Updated.");

  if (p.provider_type === "agency") {
    return (
      <div className="space-y-4">
        <Card title="Team members">
          {!p.team?.length ? (
            <p className="text-muted-foreground text-sm">No members yet. Invite individual Guday Geday agents by their profile link.</p>
          ) : (
            <ul className="divide-border divide-y">
              {p.team.map((m) => (
                <li key={m.membership_id} className="flex flex-wrap items-center gap-3 py-3">
                  <ProviderAvatar name={m.display_name} photoUrl={m.photo_url} verified={m.id_verified ? "id" : null} size="sm" />
                  <span className="min-w-0 flex-1 text-sm">
                    <Link href={`/providers/${m.slug}`} className="font-medium hover:underline">{m.display_name}</Link>
                    <span className="text-muted-foreground block text-xs">
                      {m.status === "pending" ? (m.initiated_by === "member" ? "Asked to join" : "Invited, waiting for them") : m.role_title ?? "Member"}
                    </span>
                  </span>
                  {m.status === "pending" && m.initiated_by === "member" && (
                    <>
                      <Button size="sm" loading={isPending} onClick={() => membership(m.membership_id, "accept")}>Accept</Button>
                      <Button size="sm" variant="outline" onClick={() => membership(m.membership_id, "decline")}>Decline</Button>
                    </>
                  )}
                  <Button size="sm" variant="ghost" onClick={() => membership(m.membership_id, "remove")}>Remove</Button>
                </li>
              ))}
            </ul>
          )}
        </Card>
        <Card title="Invite a member">
          <div className="flex flex-col gap-2 sm:flex-row">
            <Input placeholder="Their profile link name, e.g. meron-tadesse" value={slug} onChange={(e) => setSlug(e.target.value.replace(/^.*\/providers\//, ""))} />
            <Input placeholder="Role (optional)" value={role} onChange={(e) => setRole(e.target.value)} />
            <Button disabled={slug.trim().length < 3} loading={isPending}
              onClick={() => call(apiPaths.providers.invite, { member: slug.trim(), ...(role ? { role_title: role } : {}) }, "Invitation sent.")}>
              Invite
            </Button>
          </div>
          {msg && <p role={msg.ok ? "status" : "alert"} className={cn("mt-2 text-xs", msg.ok ? "text-primary" : "text-destructive")}>{msg.text}</p>}
        </Card>
      </div>
    );
  }

  return (
    <Card title="Agency">
      {p.agency ? (
        <div className="flex flex-wrap items-center gap-3 text-sm">
          <span>
            {p.agency.status === "active" ? "Member of " : p.agency.initiated_by === "agency" ? "Invitation from " : "Request sent to "}
            <Link href={`/providers/${p.agency.slug}`} className="text-primary font-medium hover:underline">{p.agency.display_name}</Link>
          </span>
          {p.agency.status === "pending" && p.agency.initiated_by === "agency" && (
            <>
              <Button size="sm" loading={isPending} onClick={() => membership(p.agency!.membership_id, "accept")}>Accept</Button>
              <Button size="sm" variant="outline" onClick={() => membership(p.agency!.membership_id, "decline")}>Decline</Button>
            </>
          )}
          <Button size="sm" variant="ghost" onClick={() => membership(p.agency!.membership_id, "remove")}>
            {p.agency.status === "active" ? "Leave agency" : "Withdraw"}
          </Button>
        </div>
      ) : p.entity_type === "individual" ? (
        <>
          <p className="text-muted-foreground mb-3 text-sm">Work for an agency? Ask to join it. Your jobs and reviews will count towards the agency too.</p>
          <div className="flex flex-col gap-2 sm:flex-row">
            <Input placeholder="Agency profile link name, e.g. abay-clearing-forwarding-plc" value={slug} onChange={(e) => setSlug(e.target.value.replace(/^.*\/providers\//, ""))} />
            <Button disabled={slug.trim().length < 3} loading={isPending}
              onClick={() => call(apiPaths.providers.joinAgency, { agency: slug.trim() }, "Request sent. The agency will confirm.")}>
              Ask to join
            </Button>
          </div>
        </>
      ) : (
        <p className="text-muted-foreground text-sm">Companies list their own team as an agency.</p>
      )}
      {msg && <p role={msg.ok ? "status" : "alert"} className={cn("mt-2 text-xs", msg.ok ? "text-primary" : "text-destructive")}>{msg.text}</p>}
    </Card>
  );
}
