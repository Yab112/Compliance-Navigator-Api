"""The assistant's learning loop: it finds what went wrong and proposes what to do; a person decides.

A run (started from the admin dashboard) reads what happened since the previous run:
  * questions it had no service for            -> "add data for X"            (missing_service)
  * people saying an answer was wrong            -> "check this fact"           (user_correction)
  * replies the grounding check rejected         -> "find the source for N"     (grounding_failed)
  * messages the intent model was unsure about   -> "label these examples"      (low_confidence)
  * requests the guard refused or tools that broke -> "review the guard / fix"  (denied_request, tool_error)

The same problem seen again raises its count instead of adding a row. Findings never change service data
or retrain the model on their own: staff approve, reject or mark them done, and the existing labelling and
retraining screens act on the approved ones.
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

from services.db import Jsonb, execute, fetch_all, fetch_one

FIRST_RUN_LOOKBACK = timedelta(days=30)
LOW_CONFIDENCE = 0.35
EXAMPLES_KEPT = 5
CORRECTION = re.compile(
    r"\b(that'?s (wrong|not (right|true|correct))|(is|was) wrong|incorrect|not correct|outdated|actually (it|the)"
    r"|they (asked|charged|told) me|the office (said|says|told)|it costs? .* not)\b|ስህተት|ትክክል አይደለም|ተሳስተሃል|ተሳስተዋል",
    re.I)
_STOP = {"i", "want", "need", "to", "get", "a", "an", "the", "my", "how", "do", "can", "please", "what", "is", "in",
         "for", "of", "and", "where", "me", "it"}


def _topic(message: str) -> str:
    words = [w for w in re.sub(r"[^\w\s]", " ", (message or "").lower()).split() if w not in _STOP]
    return " ".join(words[:5]) or (message or "")[:40]


def _upsert(run_id: int, kind: str, key: str, summary: str, next_action: str, action_type: str,
            examples: list[str], count: int, last_seen) -> str:
    existing = fetch_one("select id, examples, status from assistant_findings where dedupe_key = %s", (key,))
    if existing:
        merged = list(dict.fromkeys([*examples, *(existing["examples"] or [])]))[:EXAMPLES_KEPT]
        # A problem marked done that comes back is opened again
        status = "new" if existing["status"] == "done" else existing["status"]
        execute("update assistant_findings set seen_count = seen_count + %s, last_seen = greatest(last_seen, %s),"
                " examples = %s, status = %s, run_id = %s where id = %s",
                (count, last_seen, Jsonb(merged), status, run_id, existing["id"]))
        return "updated"
    execute("insert into assistant_findings (kind, dedupe_key, summary, next_action, action_type, examples,"
            " seen_count, first_seen, last_seen, run_id) values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
            (kind, key, summary, next_action, action_type, Jsonb(examples[:EXAMPLES_KEPT]), count, last_seen,
             last_seen, run_id))
    return "new"


def run(triggered_by: str) -> dict:
    last = fetch_one("select max(started_at) as at from assistant_learning_runs where finished_at is not null")
    since = (last or {}).get("at") or datetime.now(timezone.utc) - FIRST_RUN_LOOKBACK
    run_row = fetch_one("insert into assistant_learning_runs (triggered_by, since) values (%s, %s) returning id",
                        (triggered_by, since))
    run_id = run_row["id"]
    counts = {"new": 0, "updated": 0}
    by_kind: dict[str, int] = {}

    def add(kind, key, summary, action, action_type, examples, count, seen):
        counts[_upsert(run_id, kind, key, summary, action, action_type, examples, count, seen)] += 1
        by_kind[kind] = by_kind.get(kind, 0) + 1

    turns = fetch_all("select message_redacted as m, intent, confidence, gap, created_at from assistant_turns"
                      " where created_at > %s order by created_at desc limit 5000", (since,))

    # Questions we had no service for, grouped by what they asked about
    missing: dict[str, list] = {}
    for t in turns:
        if t["gap"] == "not_found":
            missing.setdefault(_topic(t["m"]), []).append(t)
    for topic, rows in missing.items():
        add("missing_service", f"missing:{topic}", f"People asked for \"{topic}\" and we had no service for it "
            f"({len(rows)} time(s)).", f"Add or import the service data for \"{topic}\" (offices, documents, fees "
            "with their source), or map it to a service we already hold.", "add_service_data",
            [r["m"] for r in rows], len(rows), rows[0]["created_at"])

    # People telling us an answer was wrong
    for t in turns:
        if CORRECTION.search(t["m"] or ""):
            add("user_correction", f"correction:{_topic(t['m'])}", "Someone said an answer was wrong or outdated.",
                "Check the fact with the office (call, visit or fee-board photo) and update the service data with "
                "its source and date. Do not change it from the message alone.", "verify_fact", [t["m"]], 1,
                t["created_at"])

    # Messages the intent model was unsure about, waiting for a label
    unsure = [t for t in turns if t["confidence"] is not None and t["confidence"] < LOW_CONFIDENCE and not t["gap"]]
    if unsure:
        add("low_confidence", f"unsure:{datetime.now(timezone.utc):%Y-%W}", f"{len(unsure)} message(s) the intent "
            "model was unsure about this week.", "Label them on the Assistant page, then retrain; the new model is "
            "only activated if it scores better on the held-out test.", "label_examples",
            [t["m"] for t in unsure], len(unsure), unsure[0]["created_at"])

    # The guard: refused requests, broken tools and rejected replies
    guard = fetch_all("select tool, decision, reason, count(*)::int as n, max(created_at) as at,"
                      " (array_agg(args::text order by id desc))[1:3] as samples from assistant_guard_log"
                      " where created_at > %s and decision <> 'allowed' group by tool, decision, reason", (since,))
    for g in guard:
        if g["tool"] == "grounding_check":
            add("grounding_failed", f"grounding:{g['reason']}", f"The AI tried to state numbers no tool returned "
                f"({g['reason']}), {g['n']} time(s); the template answered instead.", "Find out whether these "
                "numbers are real (a fee we should hold?) and add them with a source, or tighten the prompt.",
                "review_reply", g["samples"] or [], g["n"], g["at"])
        elif g["decision"] == "error":
            add("tool_error", f"error:{g['tool']}:{g['reason']}", f"The {g['tool']} tool failed with {g['reason']} "
                f"{g['n']} time(s).", f"Fix the {g['tool']} tool; the error is in the API log.", "fix_tool",
                g["samples"] or [], g["n"], g["at"])
        else:
            add("denied_request", f"denied:{g['tool']}:{g['reason']}", f"The guard refused {g['tool']} "
                f"({g['reason']}) {g['n']} time(s).", "Check whether the AI needs this (then widen the rule on "
                "purpose) or whether someone is probing it.", "review_guard", g["samples"] or [], g["n"], g["at"])

    summary = {"turns_read": len(turns), "by_kind": by_kind}
    execute("update assistant_learning_runs set finished_at = now(), findings_new = %s, findings_updated = %s,"
            " summary = %s where id = %s", (counts["new"], counts["updated"], Jsonb(summary), run_id))
    return {"run_id": run_id, "since": since, **counts, **summary}


def review(finding_id: int, status: str, actor: str, note: str | None) -> dict | None:
    return fetch_one("update assistant_findings set status = %s, reviewed_by = %s, reviewed_at = now(), note = %s"
                     " where id = %s returning *", (status, actor, note, finding_id))
