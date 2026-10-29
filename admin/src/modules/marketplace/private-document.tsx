"use client";

import { useEffect, useState } from "react";
import useAxiosAuth from "@cn/core/hooks/use-axios-auth";
import { apiPaths } from "@cn/core/lib/constants/api-paths";
import { getErrorMessage } from "@cn/core/lib/errors";
import { ErrorState, LoadingState } from "@cn/ui/guday/shared";

/** Private uploads (ID and licence copies) are fetched with the admin's token and shown from a blob URL. */
export function PrivateDocument({ fileKey, label }: { fileKey?: string | null; label: string }) {
  const axiosAuth = useAxiosAuth();
  const [doc, setDoc] = useState<{ url: string; type: string } | null>(null);
  const [error, setError] = useState<string | null>(null);
  // Remote (S3) keys are already URLs; local keys need an authenticated fetch
  const remote = !!fileKey && /^(https?|s3):/.test(fileKey);

  useEffect(() => {
    if (!fileKey || remote) return;
    let objectUrl: string | null = null;
    let cancelled = false;
    axiosAuth
      .get<Blob>(`/${apiPaths.admin.file}`, { params: { key: fileKey }, responseType: "blob" })
      .then((res) => {
        if (cancelled) return;
        objectUrl = URL.createObjectURL(res.data);
        setDoc({ url: objectUrl, type: res.data.type });
      })
      .catch((err) => !cancelled && setError(getErrorMessage(err, `Could not load the ${label.toLowerCase()}`)));
    return () => {
      cancelled = true;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [axiosAuth, fileKey, remote, label]);

  if (!fileKey) return <p className="text-muted-foreground text-xs">No {label.toLowerCase()} uploaded.</p>;
  if (remote) {
    return (
      <a href={fileKey} target="_blank" rel="noreferrer" className="text-primary text-xs underline">
        Open {label.toLowerCase()}
      </a>
    );
  }
  if (error) return <ErrorState message={error} />;
  if (!doc) return <LoadingState label="Loading document…" />;
  if (doc.type.startsWith("image/")) {
    return (
      // eslint-disable-next-line @next/next/no-img-element
      <img src={doc.url} alt={label} className="border-border max-h-96 border object-contain" />
    );
  }
  return (
    <a href={doc.url} target="_blank" rel="noreferrer" className="text-primary text-xs underline">
      Open {label.toLowerCase()} {doc.type === "application/pdf" ? "(PDF)" : ""}
    </a>
  );
}
