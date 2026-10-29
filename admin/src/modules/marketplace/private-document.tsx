"use client";

import { useCallback, useEffect, useState } from "react";
import useAxiosAuth from "@cn/core/hooks/use-axios-auth";
import { apiPaths } from "@cn/core/lib/constants/api-paths";
import { getErrorMessage } from "@cn/core/lib/errors";
import { Button } from "@cn/ui/button";
import { ErrorState, LoadingState } from "@cn/ui/guday/shared";

type SafeType = "image/jpeg" | "image/png" | "image/webp" | "application/pdf";

/**
 * The real type from the file's first bytes. The server's Content-Type is never trusted: a blob URL
 * runs in the admin's origin, so anything that isn't a plain image or PDF is refused.
 */
async function sniff(blob: Blob): Promise<SafeType | null> {
  const b = new Uint8Array(await blob.slice(0, 12).arrayBuffer());
  const starts = (...bytes: number[]) => bytes.every((v, i) => b[i] === v);
  if (starts(0xff, 0xd8, 0xff)) return "image/jpeg";
  if (starts(0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a)) return "image/png";
  if (starts(0x52, 0x49, 0x46, 0x46) && b[8] === 0x57 && b[9] === 0x45 && b[10] === 0x42 && b[11] === 0x50) return "image/webp";
  if (starts(0x25, 0x50, 0x44, 0x46, 0x2d)) return "application/pdf";
  return null;
}

/** Rebuild the download with a forced, allowlisted type, or throw. */
export async function safeBlob(data: Blob): Promise<{ blob: Blob; type: SafeType }> {
  const type = await sniff(data);
  if (!type) throw new Error("This file is not a JPG, PNG, WEBP or PDF, so it is not opened here.");
  return { blob: new Blob([await data.arrayBuffer()], { type }), type };
}

/** Where a private file comes from: the generic key endpoint, or a vetting document's own (logged) endpoint. */
type Source = { fileKey?: string | null; src?: string | null };

function useLoader({ fileKey, src }: Source) {
  const axiosAuth = useAxiosAuth();
  return useCallback(async () => {
    const res = src
      ? await axiosAuth.get<Blob>(`/${src}`, { responseType: "blob" })
      : await axiosAuth.get<Blob>(`/${apiPaths.admin.file}`, { params: { key: fileKey }, responseType: "blob" });
    return safeBlob(res.data);
  }, [axiosAuth, fileKey, src]);
}

/**
 * Private uploads (ID, licence and vetting copies) are fetched with the admin's token and shown from a
 * blob URL. With `revealOnClick` nothing is fetched until staff ask, because each view is logged.
 */
export function PrivateDocument({ fileKey, src, label, revealOnClick = false }: Source & { label: string; revealOnClick?: boolean }) {
  const load = useLoader({ fileKey, src });
  const [doc, setDoc] = useState<{ url: string; type: SafeType } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [requested, setRequested] = useState(!revealOnClick);
  // Remote (S3) keys on the generic endpoint are already URLs
  const remote = !src && !!fileKey && /^https?:/.test(fileKey);
  const has = !!src || !!fileKey;

  useEffect(() => {
    if (!has || remote || !requested) return;
    let objectUrl: string | null = null;
    let cancelled = false;
    load()
      .then(({ blob, type }) => {
        if (cancelled) return;
        objectUrl = URL.createObjectURL(blob);
        setDoc({ url: objectUrl, type });
      })
      .catch((err) => !cancelled && setError(getErrorMessage(err, `Could not load the ${label.toLowerCase()}`)));
    return () => {
      cancelled = true;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [load, has, remote, requested, label]);

  if (!has) return <p className="text-muted-foreground text-xs">No {label.toLowerCase()} uploaded.</p>;
  if (remote) {
    return (
      <a href={fileKey!} target="_blank" rel="noreferrer noopener" className="text-primary text-xs underline">
        Open {label.toLowerCase()}
      </a>
    );
  }
  if (!requested) {
    return (
      <Button type="button" size="sm" variant="outline" onClick={() => setRequested(true)}>
        Show {label.toLowerCase()} (your view is logged)
      </Button>
    );
  }
  if (error) return <ErrorState message={error} />;
  if (!doc) return <LoadingState label="Loading document…" />;
  if (doc.type.startsWith("image/")) {
    return (
      // eslint-disable-next-line @next/next/no-img-element
      <img src={doc.url} alt={label} className="border-border max-h-96 max-w-full border object-contain" />
    );
  }
  return (
    <a href={doc.url} target="_blank" rel="noreferrer noopener" className="text-primary text-xs underline">
      Open {label.toLowerCase()} (PDF)
    </a>
  );
}

/** A button that fetches a private file and opens it in a new tab, only when it is an image or PDF. */
export function PrivateFileButton({ fileKey, src, label }: Source & { label: string }) {
  const load = useLoader({ fileKey, src });
  const [err, setErr] = useState<string | null>(null);
  return (
    <div>
      <button
        type="button"
        className="text-primary text-xs font-medium hover:underline"
        onClick={async () => {
          setErr(null);
          try {
            const { blob } = await load();
            window.open(URL.createObjectURL(blob), "_blank", "noopener");
          } catch (e) {
            setErr(getErrorMessage(e, "Could not open the file"));
          }
        }}
      >
        {label} ↗
      </button>
      {err && <p className="text-destructive text-xs" role="alert">{err}</p>}
    </div>
  );
}
