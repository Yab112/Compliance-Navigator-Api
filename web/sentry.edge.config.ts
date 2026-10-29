// This file configures the initialization of Sentry for edge features (middleware, edge routes, and so on).
// https://docs.sentry.io/platforms/javascript/guides/nextjs/

import * as Sentry from "@sentry/nextjs";
import { beforeBreadcrumb, beforeSend, beforeSendTransaction, tracesSampleRate } from "./src/lib/sentry-scrub";

Sentry.init({
  dsn: process.env.SENTRY_DSN,
  // Share of requests traced (SENTRY_TRACES_SAMPLE_RATE, 0 to 1, default 0.1); errors are always sent
  tracesSampleRate: tracesSampleRate(process.env.SENTRY_TRACES_SAMPLE_RATE),
  // No IP addresses, cookies or request bodies; beforeSend also removes emails, phones and tokens
  sendDefaultPii: false,
  beforeSend,
  beforeSendTransaction,
  beforeBreadcrumb,
});
