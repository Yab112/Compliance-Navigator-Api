"use client";

import { useState } from "react";
import { useAcceptLegal } from "@cn/core/api/legal";
import { LEGAL_BY_KEY } from "@/content/legal";
import { LegalCheckbox, LegalLink } from "@/modules/legal/components/legal-checkbox";

const DOC = LEGAL_BY_KEY.provider_agreement;

/**
 * Drop-in for the "Become a provider" form. Keep the state with this hook, render the box, and
 * call `recordAcceptance()` right before submitting the join request:
 *
 *   const agreement = useProviderAgreement();
 *   ...
 *   <ProviderAgreementCheckbox {...agreement.props} />
 *   ...
 *   if (!agreement.checked) return setError("Please accept the Provider Agreement.");
 *   await agreement.recordAcceptance();   // POST /legal/accept, saves version, time, IP
 *   await join(...);                      // the server checks it with legal.require_accepted
 */
export function useProviderAgreement() {
  const [checked, setChecked] = useState(false);
  const { accept, isAccepting } = useAcceptLegal();
  return {
    checked,
    isAccepting,
    recordAcceptance: () => accept({ [DOC.key]: DOC.version }),
    props: { checked, onChange: setChecked },
  };
}

export function ProviderAgreementCheckbox({
  checked,
  onChange,
  invalid,
}: {
  checked: boolean;
  onChange: (checked: boolean) => void;
  invalid?: boolean;
}) {
  return (
    <LegalCheckbox id="accept-provider-agreement" checked={checked} onChange={onChange} invalid={invalid}>
      I have read and agree to the <LegalLink doc="provider_agreement" /> (version {DOC.version}), including the identity and
      police clearance checks, the platform commission, and that I accept payment for jobs only through Compliance Navigator.
    </LegalCheckbox>
  );
}
