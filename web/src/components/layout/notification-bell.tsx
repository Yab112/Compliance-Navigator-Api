"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { Notification01Icon } from "@hugeicons/core-free-icons";
import { HugeiconsIcon } from "@hugeicons/react";
import { useMarkNotificationsRead, useNotifications } from "@/api/notifications";
import { cn } from "@cn/core/lib/utils";

function timeAgo(iso: string): string {
  const minutes = Math.round((Date.now() - new Date(iso).getTime()) / 60000);
  if (minutes < 1) return "just now";
  if (minutes < 60) return `${minutes} min ago`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${hours} h ago`;
  return `${Math.round(hours / 24)} d ago`;
}

/** Changes to services on your saved paths, and other account updates. */
export function NotificationBell() {
  const { data } = useNotifications();
  const markRead = useMarkNotificationsRead();
  const [open, setOpen] = useState(false);
  const box = useRef<HTMLDivElement>(null);
  const items = data?.payload.items ?? [];
  const unread = data?.payload.unread ?? 0;

  useEffect(() => {
    if (!open) return;
    const close = (e: MouseEvent) => {
      if (box.current && !box.current.contains(e.target as Node)) setOpen(false);
    };
    const esc = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    document.addEventListener("mousedown", close);
    document.addEventListener("keydown", esc);
    return () => {
      document.removeEventListener("mousedown", close);
      document.removeEventListener("keydown", esc);
    };
  }, [open]);

  return (
    <div ref={box} className="relative">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        aria-label={unread ? `Notifications, ${unread} unread` : "Notifications"}
        className="relative flex items-center hover:text-white"
      >
        <HugeiconsIcon icon={Notification01Icon} className="size-4" />
        {unread > 0 && (
          <span className="bg-gov-yellow text-gov-ink absolute -top-1.5 -right-2 min-w-4 rounded-full px-1 text-center text-[10px] leading-4 font-bold">
            {unread > 9 ? "9+" : unread}
          </span>
        )}
      </button>
      {/* Phones: the bell sits mid-bar, so the panel spans the screen instead of hanging off its edge */}
      {open && (
        <div className="border-border bg-card text-foreground absolute right-0 z-[60] mt-3 w-80 max-w-[calc(100vw-2rem)] rounded-md border shadow-lg max-md:fixed max-md:inset-x-3 max-md:w-auto max-md:max-w-none">
          <div className="border-border flex items-center justify-between border-b px-4 py-2.5">
            <p className="text-sm font-semibold">Notifications · ማሳወቂያዎች</p>
            {unread > 0 && (
              <button type="button" className="text-primary text-xs font-medium hover:underline" onClick={() => markRead.mutate(undefined)}>
                Mark all read
              </button>
            )}
          </div>
          {items.length === 0 ? (
            <p className="text-muted-foreground px-4 py-6 text-center text-sm">
              Nothing yet. We tell you here when a service on your saved paths changes.
            </p>
          ) : (
            <ul className="divide-border max-h-96 divide-y overflow-y-auto">
              {items.map((n) => {
                const body = (
                  <>
                    <p className={cn("text-sm", !n.read_at && "font-semibold")}>
                      {!n.read_at && <span className="bg-primary mr-1.5 inline-block size-2 rounded-full" aria-label="Unread" />}
                      {n.title}
                    </p>
                    {n.body && <p className="text-muted-foreground mt-0.5 line-clamp-2 text-xs">{n.body}</p>}
                    <p className="text-muted-foreground mt-1 text-[11px]">{timeAgo(n.created_at)}</p>
                  </>
                );
                const onClick = () => {
                  if (!n.read_at) markRead.mutate([n.id]);
                  setOpen(false);
                };
                return (
                  <li key={n.id} className="hover:bg-secondary/50 flex items-start gap-2 pr-3">
                    {n.link ? (
                      <Link href={n.link} onClick={onClick} className="block min-w-0 flex-1 py-3 pl-4">
                        {body}
                      </Link>
                    ) : (
                      <button type="button" onClick={onClick} className="block min-w-0 flex-1 py-3 pl-4 text-left">
                        {body}
                      </button>
                    )}
                    {!n.read_at && (
                      <button
                        type="button"
                        onClick={(e) => {
                          e.preventDefault();
                          e.stopPropagation();
                          markRead.mutate([n.id]);
                        }}
                        disabled={markRead.isPending}
                        aria-label={`Mark "${n.title}" as read`}
                        className="text-primary border-border bg-card mt-3 shrink-0 rounded border px-1.5 py-0.5 text-[11px] font-medium whitespace-nowrap hover:underline disabled:opacity-60"
                      >
                        Mark as read
                      </button>
                    )}
                  </li>
                );
              })}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}
