/** "Chat on Telegram" for a username stored without the @ (shared once a job is accepted). */
export function TelegramLink({ username, className }: { username?: string | null; className?: string }) {
  if (!username) return null;
  return (
    <a
      href={`https://t.me/${encodeURIComponent(username)}`}
      target="_blank"
      rel="noopener noreferrer"
      className={
        className ??
        "inline-flex items-center gap-1 rounded-md bg-[#229ED9] px-3 py-1.5 text-xs font-semibold text-white hover:brightness-95"
      }
    >
      Chat on Telegram · @{username}
    </a>
  );
}

const BUTTON = "border-primary text-primary hover:bg-secondary inline-flex items-center rounded-md border px-3 py-1.5 text-xs font-semibold";

/**
 * How the two sides reach each other once a job is accepted: call, SMS, Telegram.
 * Before acceptance nothing is shared, and the panel says when contact will appear.
 */
export function ContactActions({
  name,
  phone,
  telegram,
  shared,
  pendingText,
}: {
  name: string;
  phone?: string | null;
  telegram?: string | null;
  shared?: boolean;
  pendingText: string;
}) {
  const first = name.split(" ")[0];
  if (!shared) return <p className="text-muted-foreground text-xs">{pendingText}</p>;
  return (
    <div className="bg-secondary/40 rounded-md p-3">
      <p className="mb-2 text-xs font-semibold">Contact {first} · ያግኙ</p>
      <div className="flex flex-wrap items-center gap-2">
        {telegram && <TelegramLink username={telegram} />}
        {phone && (
          <>
            <a href={`tel:${phone}`} className={BUTTON}>Call {phone}</a>
            <a href={`sms:${phone}`} className={BUTTON}>SMS</a>
          </>
        )}
      </div>
      {!telegram && <p className="text-muted-foreground mt-2 text-[11px]">{first} hasn&apos;t added a Telegram username yet. Call or text for now.</p>}
    </div>
  );
}
