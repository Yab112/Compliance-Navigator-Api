import Link from "next/link";
import { PageShell } from "@/components/layout/page-shell";

const FACTORS = [
  {
    title: "Client ratings",
    points: "up to 50",
    body: "Only clients who hired the provider here and finished the job can rate them. We use an adjusted average that starts every provider at 3.5 stars, so one perfect review can't beat a long, steady record.",
  },
  {
    title: "Verification",
    points: "up to 25",
    body: "Fayda national ID verified (8), phone (2), a current police clearance checked by our staff (5), an education certificate checked by our staff (3, individuals), TIN (3), or TIN and trade licence for companies (6), and a sector licence checked by our staff with the issuing office (4), such as a customs clearing permit or an employment agency licence.",
  },
  {
    title: "Reliability",
    points: "up to 15",
    body: "How often accepted work gets finished. Declining or dropping jobs after accepting them lowers it.",
  },
  {
    title: "Track record",
    points: "up to 10",
    body: "Completed jobs on the platform (up to 20) and months since approval (up to 24).",
  },
  {
    title: "Penalties",
    points: "down to minus 30",
    body: "Complaints that our staff upheld cost 10 points each, and suspensions 5 each. Reviews hidden for abuse don't count either way.",
  },
];

export function HowScoresWork() {
  return (
    <PageShell
      title="How trust scores work · የእምነት ነጥብ"
      description="Every provider has a score from 0 to 100, calculated the same way for everyone and shown with its breakdown on their profile. Nobody can pay to change it."
      maxWidth="lg"
    >
      <ol className="space-y-4">
        {FACTORS.map((f, i) => (
          <li key={f.title} className="border-border bg-card rounded-md border p-5">
            <p className="flex flex-wrap items-baseline justify-between gap-2">
              <span className="font-semibold">{i + 1}. {f.title}</span>
              <span className="text-primary text-sm font-semibold">{f.points}</span>
            </p>
            <p className="text-muted-foreground mt-1 text-sm leading-relaxed">{f.body}</p>
          </li>
        ))}
      </ol>
      <section aria-labelledby="job-success" className="border-border bg-card mt-6 rounded-md border p-5 text-sm leading-relaxed">
        <h2 id="job-success" className="font-semibold">Job Success</h2>
        <p className="text-muted-foreground mt-1">
          Shown next to the trust score as a percent: successful jobs divided by successful plus failed jobs, over jobs closed in the
          last 24 months.
        </p>
        <ul className="text-muted-foreground mt-2 list-disc space-y-1 pl-5">
          <li><strong className="text-foreground">Success:</strong> the job closed with no upheld complaint and a 4 or 5 star rating, or no rating.</li>
          <li><strong className="text-foreground">Failure:</strong> a complaint our staff upheld, or a 1 or 2 star rating.</li>
          <li>3 star ratings and requests cancelled before payment don&apos;t count either way.</li>
          <li>A job closes when the client confirms it&apos;s done, or 7 days after delivery if no problem is reported.</li>
          <li>Shown after 3 closed jobs.</li>
        </ul>
      </section>
      <section aria-labelledby="client-record" className="border-border bg-card mt-6 rounded-md border p-5 text-sm leading-relaxed">
        <h2 id="client-record" className="font-semibold">Clients have a record too</h2>
        <p className="text-muted-foreground mt-1">
          When you send a request, the provider sees your hire rate (of the requests providers accepted and that have ended, how
          many you paid), your paid jobs, cancellations after a provider accepted, and the ratings providers gave you. Your record
          is never public. You can see it on <Link href="/account/requests" className="text-primary underline">My hires</Link>.
        </p>
      </section>
      <div className="border-border bg-secondary/40 mt-6 rounded-md border p-5 text-sm leading-relaxed">
        <p className="font-semibold">Before you pay anyone</p>
        <ul className="mt-2 list-disc space-y-1 pl-5">
          <li>Agree the provider&apos;s fee in writing before work starts.</li>
          <li>Pay official government fees only at the service window or official channels, never in cash to the provider.</li>
          <li>Providers marked <strong>New</strong> have fewer than 3 reviews. Their score relies mostly on verification.</li>
          <li>If something goes wrong, use <Link href="/account/requests" className="text-primary underline">Report a problem</Link> on your hire.</li>
        </ul>
      </div>
    </PageShell>
  );
}
