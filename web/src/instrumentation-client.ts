// This file configures the initialization of Sentry on the client.
// The added config here will be used whenever a users loads a page in their browser.
// https://docs.sentry.io/platforms/javascript/guides/nextjs/

import * as Sentry from "@sentry/nextjs";
import { beforeBreadcrumb, beforeSend, beforeSendTransaction, tracesSampleRate } from "@/lib/sentry-scrub";

Sentry.init({
  dsn: process.env.NEXT_PUBLIC_SENTRY_DSN,
  // Share of page loads traced (NEXT_PUBLIC_SENTRY_TRACES_SAMPLE_RATE, 0 to 1, default 0.1); errors are always sent
  tracesSampleRate: tracesSampleRate(process.env.NEXT_PUBLIC_SENTRY_TRACES_SAMPLE_RATE),
  // No IP addresses or cookies; beforeSend also removes emails, phones and tokens (reset links carry one)
  sendDefaultPii: false,
  beforeSend,
  beforeSendTransaction,
  beforeBreadcrumb,
});

export const onRouterTransitionStart = Sentry.captureRouterTransitionStart;
