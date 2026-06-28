import Link from "next/link";
import { cn } from "@/lib/utils";
import { aboutProduct } from "@/content/about";

type LogoProps = {
  showName?: boolean;
  className?: string;
  size?: "sm" | "md";
};

/** Replace the CN monogram with /brand/logo.svg via next/image when your asset is ready. */
export function Logo({ showName = true, className, size = "md" }: LogoProps) {
  const box = size === "sm" ? "size-8 text-xs" : "size-10 text-sm";

  return (
    <Link
      href="/"
      className={cn("flex items-center gap-2.5 font-semibold tracking-tight", className)}
    >
      <span
        className={cn(
          "bg-primary text-primary-foreground flex shrink-0 items-center justify-center font-bold",
          box,
        )}
        aria-hidden
      >
        CN
      </span>
      {showName && (
        <span
          className={cn(
            "hidden sm:inline",
            size === "sm" ? "text-sm" : "text-base",
          )}
        >
          {aboutProduct.name}
        </span>
      )}
    </Link>
  );
}
