import { apiAssetUrl } from "@cn/core/lib/api";
import { cn } from "@cn/core/lib/utils";
import type { EntityType, PublicProvider } from "@cn/core/types/provider";

export type AvatarSize = "xs" | "sm" | "md" | "lg" | "xl";
export type VerifiedLevel = "id" | "company" | null;

const SIZES: Record<AvatarSize, { box: string; text: string; badge: string }> = {
  xs: { box: "size-7", text: "text-[10px]", badge: "size-3" },
  sm: { box: "size-10", text: "text-xs", badge: "size-4" },
  md: { box: "size-14", text: "text-base", badge: "size-5" },
  lg: { box: "size-20", text: "text-2xl", badge: "size-6" },
  xl: { box: "size-32", text: "text-4xl", badge: "size-9" },
};

// Muted, readable on white text; picked per name so a provider always gets the same color
const PALETTE = ["#0b6b3a", "#1d4e89", "#7a3e9d", "#a1432a", "#2f6f73", "#8a6d00", "#4b5d16", "#9c2f5b"];

function colorFor(name: string): string {
  let h = 0;
  for (const ch of name) h = (h * 31 + ch.charCodeAt(0)) >>> 0;
  return PALETTE[h % PALETTE.length];
}

function initials(name: string): string {
  return (
    name
      .split(/\s+/)
      .filter(Boolean)
      .slice(0, 2)
      .map((p) => p[0]?.toUpperCase())
      .join("") || "?"
  );
}

/** Which badge a provider earns: companies with checked TIN and licence, or a Fayda-verified person. */
export function verifiedLevel(p: Pick<PublicProvider, "entity_type" | "id_verified" | "registered_business"> & { id_test?: boolean }): VerifiedLevel {
  if (p.entity_type === "company" && p.registered_business) return "company";
  // A Fayda sandbox (test) check never earns the seal
  if (p.id_verified && !p.id_test) return "id";
  return null;
}

const BADGE_LABEL = {
  id: "Identity verified with Fayda, the national ID",
  company: "Registered company: TIN and trade licence checked",
} as const;

export function VerifiedSeal({ level, className }: { level: Exclude<VerifiedLevel, null>; className?: string }) {
  return (
    <svg viewBox="0 0 24 24" className={className} role="img" aria-label={BADGE_LABEL[level]}>
      <title>{BADGE_LABEL[level]}</title>
      {level === "company" ? (
        <rect x="1.5" y="1.5" width="21" height="21" rx="5" fill="#1d4e89" stroke="#fff" strokeWidth="2" />
      ) : (
        <path
          d="M12 1.5l2.6 1.9 3.2-.2 1 3 2.6 1.9-1 3 1 3-2.6 1.9-1 3-3.2-.2L12 22.5l-2.6-1.9-3.2.2-1-3L2.6 16l1-3-1-3 2.6-1.9 1-3 3.2.2z"
          fill="#078930"
          stroke="#fff"
          strokeWidth="1.5"
        />
      )}
      <path d="M7.5 12.3l3 3 6-6.3" fill="none" stroke="#fff" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

type ProviderAvatarProps = {
  name: string;
  photoUrl?: string | null;
  entity?: EntityType;
  verified?: VerifiedLevel;
  size?: AvatarSize;
  className?: string;
  /** Show a local preview (blob URL) instead of an API path */
  previewUrl?: string | null;
};

/** Circle photo for people, rounded square logo for companies, with the verified seal on the corner. */
export function ProviderAvatar({ name, photoUrl, entity = "individual", verified = null, size = "md", className, previewUrl }: ProviderAvatarProps) {
  const s = SIZES[size];
  const src = previewUrl ?? apiAssetUrl(photoUrl);
  const shape = entity === "company" ? "rounded-xl" : "rounded-full";
  return (
    <span className={cn("relative inline-flex shrink-0", s.box, className)}>
      {src ? (
        // Uploaded by providers and served by the API origin, so a plain img avoids next/image domain config
        // eslint-disable-next-line @next/next/no-img-element
        <img
          src={src}
          alt={entity === "company" ? `${name} logo` : name}
          className={cn("bg-muted size-full object-cover ring-2 ring-white", shape)}
        />
      ) : (
        <span
          className={cn("flex size-full items-center justify-center font-semibold text-white ring-2 ring-white", shape, s.text)}
          style={{ background: colorFor(name) }}
          aria-label={name}
          role="img"
        >
          {initials(name)}
        </span>
      )}
      {verified && <VerifiedSeal level={verified} className={cn("absolute -right-0.5 -bottom-0.5 drop-shadow-sm", s.badge)} />}
    </span>
  );
}
