"use client";

import { useState } from "react";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";

/** Mirrors the server rules in auth/security.py so people see problems before submitting. */
export const PASSWORD_RULES = [
  { label: "At least 8 characters", test: (p: string) => p.length >= 8 },
  { label: "A letter and a number", test: (p: string) => /[A-Za-z]/.test(p) && /\d/.test(p) },
] as const;

export function passwordIsValid(password: string): boolean {
  return PASSWORD_RULES.every((r) => r.test(password)) && new TextEncoder().encode(password).length <= 72;
}

type PasswordInputProps = {
  id: string;
  value: string;
  onChange: (value: string) => void;
  autoComplete: "current-password" | "new-password";
  showRules?: boolean;
  /**
   * Inside a signed-in session (account settings) a password must never be revealable: someone
   * at an unlocked computer could otherwise read a browser-filled password. "locked" removes the
   * Show button and asks the browser not to fill the field.
   */
  locked?: boolean;
};

export function PasswordInput({ id, value, onChange, autoComplete, showRules, locked }: PasswordInputProps) {
  const [visible, setVisible] = useState(false);
  const show = visible && !locked;
  return (
    <div>
      <div className="relative">
        <Input
          id={id}
          type={show ? "text" : "password"}
          // "new-password" is the one value browsers respect for "don't fill a saved password here"
          autoComplete={locked ? "new-password" : autoComplete}
          data-1p-ignore={locked || undefined}
          data-lpignore={locked ? "true" : undefined}
          required
          value={value}
          onChange={(e) => onChange(e.target.value)}
          className={locked ? undefined : "pr-16"}
          aria-describedby={showRules ? `${id}-rules` : undefined}
        />
        {!locked && (
          <button
            type="button"
            onClick={() => setVisible((v) => !v)}
            className="text-primary absolute inset-y-0 right-0 px-3 text-xs font-medium"
            aria-label={visible ? "Hide password" : "Show password"}
          >
            {visible ? "Hide" : "Show"}
          </button>
        )}
      </div>
      {showRules && (
        <ul id={`${id}-rules`} className="mt-2 space-y-0.5 text-xs">
          {PASSWORD_RULES.map((rule) => {
            const ok = rule.test(value);
            return (
              <li key={rule.label} className={cn(ok ? "text-primary" : "text-muted-foreground")}>
                {ok ? "✓" : "○"} {rule.label}
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
