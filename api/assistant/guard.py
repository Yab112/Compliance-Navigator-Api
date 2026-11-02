"""The guard between the AI and our data.

The model never reads the database or calls our services itself. It can only ask the guard for one of a
fixed list of tools. The guard:
  1. refuses any tool not on the list, and any request whose arguments don't match the tool's schema
     exactly (unknown fields, wrong types, values outside the allowed set, oversized text);
  2. limits how many requests one turn may make, per tool and in total;
  3. runs our own code for the tool (which reads only public service data and the person's own
     conversation state, never other people's records);
  4. removes personal data (emails, ID-like numbers) from what goes back to the model;
  5. writes every request to assistant_guard_log, allowed or refused, with the reason.

Staff read that log in the admin (/admin/assistant/guard).
"""

from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import dataclass

log = logging.getLogger(__name__)

MAX_CALLS_PER_TURN = 10
MAX_STRING = 200
MAX_ARRAY = 20
_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")
_EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
_LONG_ID = re.compile(r"\b\d{12,}\b")  # Fayda FIN, account and card numbers


@dataclass(frozen=True)
class Rule:
    schema: dict
    max_per_turn: int
    purpose: str  # shown in the admin log


class Denied(Exception):
    pass


def _check(value, schema: dict, path: str = "") -> None:
    """A strict check for the small schemas our tools use (object/string/array/enum)."""
    kind = schema.get("type")
    if kind == "object":
        if not isinstance(value, dict):
            raise Denied(f"{path or 'input'} must be an object")
        props = schema.get("properties") or {}
        extra = set(value) - set(props)
        if extra and schema.get("additionalProperties") is False:
            raise Denied(f"unknown field(s): {', '.join(sorted(extra))}")
        for key in schema.get("required") or []:
            if key not in value or value[key] in (None, ""):
                raise Denied(f"missing {key}")
        for key, sub in props.items():
            if key in value and value[key] is not None:
                _check(value[key], sub, f"{path}{key}")
    elif kind == "string":
        if not isinstance(value, str):
            raise Denied(f"{path} must be text")
        if len(value) > MAX_STRING:
            raise Denied(f"{path} is too long")
        if _CONTROL.search(value):
            raise Denied(f"{path} has control characters")
        if "enum" in schema and value not in schema["enum"]:
            raise Denied(f"{path} must be one of {', '.join(schema['enum'])}")
    elif kind == "array":
        if not isinstance(value, list):
            raise Denied(f"{path} must be a list")
        if len(value) > MAX_ARRAY:
            raise Denied(f"{path} has too many items")
        for i, item in enumerate(value):
            _check(item, schema.get("items") or {}, f"{path}[{i}]")


def redact(text: str) -> str:
    return _LONG_ID.sub("[number removed]", _EMAIL.sub("[email removed]", text or ""))


class Guard:
    """One per turn: holds the rules, counts requests and records them."""

    def __init__(self, rules: dict[str, Rule], conversation_id: str | None) -> None:
        self.rules = rules
        self.conversation_id = conversation_id
        self.calls: dict[str, int] = {}
        self.records: list[dict] = []

    def request(self, tool: str, args: dict, run) -> str:
        """Check the request, run it through our code if allowed, and return what the model may see."""
        started = time.monotonic()
        try:
            rule = self.rules.get(tool)
            if not rule:
                raise Denied("this tool is not on the allowed list")
            _check(args, rule.schema)
            if sum(self.calls.values()) >= MAX_CALLS_PER_TURN:
                raise Denied("too many requests in one turn")
            if self.calls.get(tool, 0) >= rule.max_per_turn:
                raise Denied(f"{tool} was already asked {rule.max_per_turn} time(s) this turn")
            self.calls[tool] = self.calls.get(tool, 0) + 1
        except Denied as no:
            self._record(tool, args, "denied", str(no), started, 0)
            return json.dumps({"denied": str(no)})
        try:
            out = redact(run())
        except Exception as exc:
            self._record(tool, args, "error", type(exc).__name__, started, 0)
            raise
        self._record(tool, args, "allowed", None, started, len(out))
        return out

    def _record(self, tool: str, args: dict, decision: str, reason: str | None, started: float, size: int) -> None:
        row = {"tool": tool[:60], "args": redact(json.dumps(args, ensure_ascii=False, default=str))[:1000],
               "decision": decision, "reason": reason, "result_chars": size,
               "duration_ms": int((time.monotonic() - started) * 1000)}
        self.records.append(row)
        if decision != "allowed":
            log.info("Guard %s %s: %s", decision, tool, reason)
        try:
            from services.db import execute

            execute(
                "insert into assistant_guard_log (conversation_id, tool, args, decision, reason, result_chars, duration_ms)"
                " values (%s, %s, %s::jsonb, %s, %s, %s, %s)",
                (self.conversation_id, row["tool"], row["args"] if row["args"].startswith("{") else "{}",
                 decision, reason, size, row["duration_ms"]))
        except Exception:
            log.warning("Could not write the guard log")
