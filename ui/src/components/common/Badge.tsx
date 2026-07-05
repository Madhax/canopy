import { clsx } from "clsx";
import type { ReactNode } from "react";

interface Props {
  children: ReactNode;
  color?: string; // accent hex; renders a tinted chip + dot
  className?: string;
  dot?: boolean;
}

export function Badge({ children, color, className, dot = true }: Props) {
  return (
    <span
      className={clsx(
        "inline-flex items-center gap-1.5 rounded-full border px-2 py-0.5 text-xs font-medium",
        "bg-surface-2 text-ink-muted",
        className,
      )}
      style={color ? { borderColor: `${color}40`, color } : undefined}
    >
      {color && dot && (
        <span className="size-1.5 rounded-full" style={{ background: color }} aria-hidden />
      )}
      {children}
    </span>
  );
}
