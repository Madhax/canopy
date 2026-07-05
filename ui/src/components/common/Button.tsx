import { clsx } from "clsx";
import type { ButtonHTMLAttributes } from "react";

type Variant = "primary" | "secondary" | "ghost" | "danger";
type Size = "sm" | "md";

interface Props extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  size?: Size;
}

const VARIANTS: Record<Variant, string> = {
  primary: "bg-accent text-accent-fg hover:bg-accent-hover border-transparent",
  secondary: "bg-surface text-ink border-border-strong hover:bg-surface-2",
  ghost: "bg-transparent text-ink-muted border-transparent hover:bg-surface-2 hover:text-ink",
  danger: "bg-transparent text-danger border-transparent hover:bg-danger/10",
};

const SIZES: Record<Size, string> = {
  sm: "h-7 px-2.5 text-xs gap-1.5",
  md: "h-9 px-3.5 text-sm gap-2",
};

export function Button({ variant = "secondary", size = "md", className, ...rest }: Props) {
  return (
    <button
      className={clsx(
        "inline-flex items-center justify-center rounded-md border font-medium",
        "transition-colors disabled:opacity-50 disabled:pointer-events-none select-none",
        "focus-visible:outline-2 focus-visible:outline-accent focus-visible:outline-offset-1",
        VARIANTS[variant],
        SIZES[size],
        className,
      )}
      {...rest}
    />
  );
}
