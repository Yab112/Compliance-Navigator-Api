"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Button } from "@cn/ui/button";
import { getErrorMessage } from "@cn/core/lib/errors";
import { cn } from "@cn/core/lib/utils";
import type { EntityType } from "@cn/core/types/provider";
import { ProviderAvatar, type VerifiedLevel } from "@cn/ui/marketplace/provider-avatar";

const TYPES = ["image/jpeg", "image/png", "image/webp"];
const MAX_BYTES = 5 * 1024 * 1024;
const VIEW = 240; // crop preview size in CSS pixels
const OUT = 512; // uploaded image size

type Crop = { zoom: number; x: number; y: number };

function draw(canvas: HTMLCanvasElement, img: HTMLImageElement, crop: Crop, size: number, round: boolean) {
  const ctx = canvas.getContext("2d");
  if (!ctx) return;
  canvas.width = size;
  canvas.height = size;
  const base = Math.max(size / img.naturalWidth, size / img.naturalHeight);
  const scale = base * crop.zoom;
  const k = size / VIEW;
  ctx.clearRect(0, 0, size, size);
  ctx.save();
  if (round) {
    ctx.beginPath();
    ctx.arc(size / 2, size / 2, size / 2, 0, Math.PI * 2);
    ctx.clip();
  }
  ctx.drawImage(
    img,
    size / 2 - (img.naturalWidth * scale) / 2 + crop.x * k,
    size / 2 - (img.naturalHeight * scale) / 2 + crop.y * k,
    img.naturalWidth * scale,
    img.naturalHeight * scale,
  );
  ctx.restore();
}

/** Keep the image covering the square at the current zoom. */
function clamp(img: HTMLImageElement, crop: Crop): Crop {
  const base = Math.max(VIEW / img.naturalWidth, VIEW / img.naturalHeight);
  const w = img.naturalWidth * base * crop.zoom;
  const h = img.naturalHeight * base * crop.zoom;
  const mx = Math.max(0, (w - VIEW) / 2);
  const my = Math.max(0, (h - VIEW) / 2);
  return { zoom: crop.zoom, x: Math.min(mx, Math.max(-mx, crop.x)), y: Math.min(my, Math.max(-my, crop.y)) };
}

type PhotoUploaderProps = {
  name: string;
  entity: EntityType;
  verified?: VerifiedLevel;
  currentUrl?: string | null;
  /** Called with the cropped 512x512 image */
  onSave: (file: File) => Promise<void> | void;
  onRemove?: () => Promise<void> | void;
  /** Local preview when nothing is uploaded yet (join flow) */
  previewUrl?: string | null;
};

export function PhotoUploader({ name, entity, verified, currentUrl, onSave, onRemove, previewUrl }: PhotoUploaderProps) {
  const isCompany = entity === "company";
  const noun = isCompany ? "logo" : "photo";
  const inputRef = useRef<HTMLInputElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [img, setImg] = useState<HTMLImageElement | null>(null);
  const [crop, setCrop] = useState<Crop>({ zoom: 1, x: 0, y: 0 });
  const [dragOver, setDragOver] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const drag = useRef<{ px: number; py: number; x: number; y: number } | null>(null);

  const load = useCallback((file: File | undefined) => {
    setError(null);
    if (!file) return;
    if (!TYPES.includes(file.type)) return setError("Use a JPG, PNG or WEBP image.");
    if (file.size > MAX_BYTES) return setError("The image is larger than 5 MB.");
    const url = URL.createObjectURL(file);
    const image = new Image();
    image.onload = () => {
      setImg(image);
      setCrop({ zoom: 1, x: 0, y: 0 });
    };
    image.onerror = () => setError("This image could not be read.");
    image.src = url;
  }, []);

  useEffect(() => {
    if (img && canvasRef.current) draw(canvasRef.current, img, crop, VIEW * 2, !isCompany);
  }, [img, crop, isCompany]);

  const save = async () => {
    if (!img) return;
    setBusy(true);
    setError(null);
    try {
      const out = document.createElement("canvas");
      draw(out, img, crop, OUT, false);
      const blob = await new Promise<Blob | null>((resolve) => out.toBlob(resolve, "image/jpeg", 0.9));
      if (!blob) throw new Error("Could not prepare the image");
      await onSave(new File([blob], `${noun}.jpg`, { type: "image/jpeg" }));
      URL.revokeObjectURL(img.src);
      setImg(null);
    } catch (err) {
      setError(getErrorMessage(err, "Upload failed"));
    } finally {
      setBusy(false);
    }
  };

  const remove = async () => {
    if (!onRemove) return;
    setBusy(true);
    setError(null);
    try {
      await onRemove();
    } catch (err) {
      setError(getErrorMessage(err, "Could not remove"));
    } finally {
      setBusy(false);
    }
  };

  if (img) {
    return (
      <div className="space-y-3">
        <p className="text-sm font-medium">Position your {noun} · ፎቶውን ያስተካክሉ</p>
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center">
          <canvas
            ref={canvasRef}
            style={{ width: VIEW, height: VIEW }}
            className={cn("bg-muted max-w-full cursor-grab touch-none ring-1 ring-black/10 active:cursor-grabbing", isCompany ? "rounded-xl" : "rounded-full")}
            aria-label={`Drag to reposition the ${noun}`}
            onPointerDown={(e) => {
              (e.target as HTMLElement).setPointerCapture(e.pointerId);
              drag.current = { px: e.clientX, py: e.clientY, x: crop.x, y: crop.y };
            }}
            onPointerMove={(e) => {
              if (!drag.current) return;
              setCrop(clamp(img, { zoom: crop.zoom, x: drag.current.x + e.clientX - drag.current.px, y: drag.current.y + e.clientY - drag.current.py }));
            }}
            onPointerUp={() => (drag.current = null)}
          />
          <div className="min-w-0 flex-1 space-y-3">
            <label className="block text-xs font-medium">
              Zoom
              <input
                type="range"
                min={1}
                max={3}
                step={0.01}
                value={crop.zoom}
                onChange={(e) => setCrop(clamp(img, { ...crop, zoom: Number(e.target.value) }))}
                className="accent-primary mt-1 block w-full"
              />
            </label>
            <p className="text-muted-foreground text-xs">Drag the picture to move it. It is saved as a 512 x 512 image.</p>
            <div className="flex gap-2">
              <Button type="button" onClick={save} loading={busy}>
                Save {noun}
              </Button>
              <Button type="button" variant="outline" disabled={busy} onClick={() => setImg(null)}>
                Cancel
              </Button>
            </div>
          </div>
        </div>
        {error && <p className="text-destructive text-xs">{error}</p>}
      </div>
    );
  }

  const hasPhoto = !!(currentUrl || previewUrl);
  return (
    <div
      onDragOver={(e) => {
        e.preventDefault();
        setDragOver(true);
      }}
      onDragLeave={() => setDragOver(false)}
      onDrop={(e) => {
        e.preventDefault();
        setDragOver(false);
        load(e.dataTransfer.files?.[0]);
      }}
      className={cn(
        "flex flex-col items-center gap-4 rounded-lg border-2 border-dashed p-4 sm:flex-row",
        dragOver ? "border-primary bg-secondary/60" : "border-border",
      )}
    >
      <ProviderAvatar name={name || "?"} photoUrl={currentUrl} previewUrl={previewUrl} entity={entity} verified={verified} size="lg" />
      <div className="min-w-0 flex-1 text-center sm:text-left">
        <p className="text-sm font-medium">
          {hasPhoto ? `Change your ${noun}` : `Add a ${noun}`} · {isCompany ? "አርማ" : "ፎቶ"}
        </p>
        <p className="text-muted-foreground mt-0.5 text-xs">
          {isCompany
            ? "Your company logo. Clients trust profiles with a real logo."
            : "A clear photo of your face. Profiles with a photo get more requests."}{" "}
          Drag an image here or choose one. JPG, PNG or WEBP, up to 5 MB.
        </p>
        <div className="mt-3 flex flex-wrap justify-center gap-2 sm:justify-start">
          <Button type="button" size="sm" onClick={() => inputRef.current?.click()} loading={busy}>
            {hasPhoto ? "Choose new image" : "Upload image"}
          </Button>
          {hasPhoto && onRemove && (
            <Button type="button" size="sm" variant="outline" onClick={remove} disabled={busy}>
              Remove {noun}
            </Button>
          )}
        </div>
        {error && <p className="text-destructive mt-2 text-xs">{error}</p>}
      </div>
      <input
        ref={inputRef}
        type="file"
        accept={TYPES.join(",")}
        className="sr-only"
        tabIndex={-1}
        onChange={(e) => {
          load(e.target.files?.[0]);
          e.target.value = "";
        }}
      />
    </div>
  );
}
