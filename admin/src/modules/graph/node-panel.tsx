"use client";

import Link from "next/link";
import { siteUrl } from "@cn/core/config/env";
import { Button } from "@cn/ui/button";
import { formatDate } from "@cn/core/lib/format";
import type { GraphNode, GraphView } from "@cn/core/types/admin";
import { StatusBadge } from "@/modules/shared/status-badge";
import { HIGHLIGHT, NODE_TYPES, formatDuration, formatFee } from "@/modules/graph/graph-style";

type Props = {
  node: GraphNode;
  byKey: Map<string, GraphNode>;
  mesob: GraphView["mesobLinks"];
  rel: { directPrereqs: string[]; directDependants: string[]; prereqs: Set<string>; dependants: Set<string> };
  onSelect: (key: string) => void;
  onEdit: (docId: string) => void;
  onClose: () => void;
};

function Fact({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="grid grid-cols-[7rem_1fr] gap-2">
      <dt className="text-muted-foreground">{label}</dt>
      <dd className="min-w-0 break-words">{children}</dd>
    </div>
  );
}

function LinkList({
  title,
  keys,
  total,
  color,
  byKey,
  onSelect,
  empty,
}: {
  title: string;
  keys: string[];
  total: number;
  color: string;
  byKey: Map<string, GraphNode>;
  onSelect: (key: string) => void;
  empty: string;
}) {
  return (
    <section>
      <h4 className="mb-1 flex items-center gap-1.5 text-[11px] font-semibold">
        <span className="inline-block h-0.5 w-4" style={{ background: color }} aria-hidden="true" />
        {title}
        {total > keys.length && <span className="text-muted-foreground font-normal">· {total} in the whole chain</span>}
      </h4>
      {keys.length ? (
        <ul className="space-y-0.5">
          {keys.map((k) => {
            const n = byKey.get(k);
            if (!n) return null;
            return (
              <li key={k}>
                <button
                  type="button"
                  onClick={() => onSelect(k)}
                  className="hover:bg-muted focus-visible:ring-ring/50 w-full px-1 py-0.5 text-left outline-none focus-visible:ring-2"
                >
                  <span className="text-muted-foreground">{NODE_TYPES[n.type].label}:</span> {n.label}
                </button>
              </li>
            );
          })}
        </ul>
      ) : (
        <p className="text-muted-foreground">{empty}</p>
      )}
    </section>
  );
}

/** What the selected item is, its facts and freshness, MESOB links, and what comes before and after it. */
export function NodePanel({ node, byKey, mesob, rel, onSelect, onEdit, onClose }: Props) {
  const type = NODE_TYPES[node.type];
  const isDoc = node.type === "Document";
  const links = isDoc ? mesob.filter((m) => m.document === node.id) : [];

  return (
    <aside aria-label={`Details: ${node.label}`} className="border-border bg-background space-y-3 border p-3 text-xs">
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="text-muted-foreground flex items-center gap-1.5 text-[11px]">
            <span className="inline-block size-2.5" style={{ background: type.color }} aria-hidden="true" />
            {type.label}
          </p>
          <h3 className="text-sm font-semibold break-words">{node.label}</h3>
          {node.label_am && <p className="text-muted-foreground break-words">{node.label_am}</p>}
        </div>
        <Button size="sm" variant="ghost" onClick={onClose} aria-label="Close details">
          Close
        </Button>
      </div>
      <p className="text-muted-foreground leading-relaxed">{node.description || type.about}</p>

      <dl className="space-y-1">
        {(isDoc || node.type === "OrgService") && <Fact label="Fee">{formatFee(node.fee)}</Fact>}
        {(isDoc || node.type === "OrgService") && <Fact label="Usual time">{formatDuration(node.days, node.minutes)}</Fact>}
        {node.office && <Fact label={node.type === "Sector" ? "Regulator" : "Issuing office"}>{node.office}</Fact>}
        {node.form_code && <Fact label="Form code">{node.form_code}</Fact>}
        {node.organization && (
          <Fact label="Organization">
            {node.organization_id ? (
              <Link href={`/organizations/${node.organization_id}`} className="text-primary underline">
                {node.organization}
              </Link>
            ) : (
              node.organization
            )}
          </Fact>
        )}
        {isDoc && (
          <Fact label="Freshness">
            <StatusBadge status={node.stale ? "stale" : "verified"} tone={node.stale ? "warning" : "good"} />
            <span className="text-muted-foreground mt-0.5 block">
              {node.last_verified ? `Checked ${formatDate(node.last_verified)}` : "Never checked"}
              {node.verified_by ? ` by ${node.verified_by}` : ""}
            </span>
          </Fact>
        )}
        {node.source_url && (
          <Fact label="Source">
            <a href={node.source_url} target="_blank" rel="noreferrer" className="text-primary break-all underline">
              {node.source_url}
            </a>
          </Fact>
        )}
      </dl>

      {isDoc && (
        <section>
          <h4 className="mb-1 text-[11px] font-semibold">At MESOB one-stop centers</h4>
          {links.length ? (
            <ul className="space-y-1">
              {links.map((m) => (
                <li key={m.id}>
                  <a href={siteUrl(`/services/${m.id}`)} target="_blank" rel="noreferrer" className="text-primary underline">
                    {m.name}
                  </a>
                  <span className="text-muted-foreground">
                    {m.institution ? ` · ${m.institution}` : ""}
                    {m.fee_text ? ` · ${m.fee_text}` : ""}
                    {m.time_text ? ` · ${m.time_text}` : ""}
                  </span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-muted-foreground">Not linked to a MESOB service yet.</p>
          )}
        </section>
      )}

      <LinkList
        title="Needed first"
        keys={rel.directPrereqs}
        total={rel.prereqs.size}
        color={HIGHLIGHT.prereq}
        byKey={byKey}
        onSelect={onSelect}
        empty="Nothing. This can be started right away."
      />
      <LinkList
        title="Depends on this"
        keys={rel.directDependants}
        total={rel.dependants.size}
        color={HIGHLIGHT.dependant}
        byKey={byKey}
        onSelect={onSelect}
        empty="Nothing depends on this yet."
      />

      {isDoc && (
        <div className="border-border border-t pt-3">
          <Button size="sm" onClick={() => onEdit(node.id)}>
            {node.stale ? "Check and update this document" : "Edit document"}
          </Button>
        </div>
      )}
    </aside>
  );
}
