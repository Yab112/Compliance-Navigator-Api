import type { LegalDoc } from "./types";

export const refundPolicy: LegalDoc = {
  key: "refund_policy",
  slug: "refunds",
  title: "Refund and Dispute Policy",
  titleAm: "የገንዘብ ተመላሽ እና የክርክር ፖሊሲ",
  version: "1.0",
  effective: "2026-10-29",
  summary:
    "When a client can cancel or get money back, how to report a problem with a job, and how our staff decide. This policy is part of the Terms of Service.",
  sections: [
    {
      id: "before-delivery",
      title: "1. Before the work is delivered",
      body: [
        "Clients pay only after the provider marks the work delivered, so there is nothing to refund before then. A client can cancel a request at any time before delivery, free of charge. Frequent cancellations after a provider has accepted show on the client's record, which providers can see.",
      ],
    },
    {
      id: "report",
      title: "2. Reporting a problem after delivery",
      body: [
        "If the work was not done, was done badly, or is not what was agreed, use \"Report a problem\" on the hire instead of paying. Explain what went wrong and add evidence, such as receipts, photos or messages. Report within [7 days] of delivery.",
        "A report pauses payment. Our staff contact both sides, look at the evidence, and decide, normally within [10 working days].",
      ],
    },
    {
      id: "outcomes",
      title: "3. What staff can decide",
      body: [
        {
          list: [
            "The client pays the full agreed price (the problem is not upheld).",
            "The client pays a lower amount for partial work.",
            "The client pays nothing, or gets a full or partial refund if already paid, and the provider gets nothing for that part.",
            "The provider finishes or corrects the work first.",
          ],
        },
        "An upheld complaint counts against the provider's Job Success score. We tell both sides the decision and the reason in writing.",
      ],
    },
    {
      id: "refunds",
      title: "4. How refunds are paid",
      body: [
        "Refunds go back through Chapa to the way you paid, where possible, within [14 days] of the decision. Fees charged by banks or mobile money services may not be refundable. Government office fees paid to an office are refunded only if that office refunds them.",
      ],
    },
    {
      id: "not-covered",
      title: "5. What we cannot help with",
      body: [
        "We cannot refund or recover money paid outside the platform, because we have no record of it and it breaks the Marketplace Rules. We also cannot change an office's decision on an application.",
        { see: ["marketplace_rules"] },
      ],
    },
    {
      id: "review",
      title: "6. If you disagree",
      body: [
        "Either side can ask for a second review by a different staff member through the support page within [14 days] of the decision. After that you keep your rights to complain to the Ethiopian Trade Competition and Consumers Protection Authority or to go to court, as set out in the Terms of Service.",
        { see: ["terms"] },
      ],
    },
  ],
};
