import { Link } from "react-router-dom";
import type { ReactNode } from "react";

/** The Canopy wordmark + a leaf glyph, reused across top-level pages. */
export function AppHeader({ actions }: { actions?: ReactNode }) {
  return (
    <header className="flex items-center justify-between border-b border-border bg-surface px-6 py-3">
      <Link to="/" className="flex items-center gap-2 text-ink">
        <LeafMark />
        <span className="text-base font-semibold tracking-tight">Canopy</span>
        <span className="text-xs text-ink-muted">Org Chart Editor</span>
      </Link>
      <div className="flex items-center gap-2">{actions}</div>
    </header>
  );
}

export function LeafMark({ size = 20 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" aria-hidden>
      <path
        d="M12 21c0-6 3-10 8-12-1 6-4 9-8 10 4-9 0-15-8-16 0 9 3 15 8 18Z"
        fill="var(--color-accent)"
      />
    </svg>
  );
}
