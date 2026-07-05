import { clsx } from "clsx";

export function Spinner({ className }: { className?: string }) {
  return (
    <span
      className={clsx(
        "inline-block size-4 animate-spin rounded-full border-2 border-ink-subtle border-t-accent",
        className,
      )}
      role="status"
      aria-label="Loading"
    />
  );
}

export function CenteredSpinner({ label }: { label?: string }) {
  return (
    <div className="flex h-full w-full flex-col items-center justify-center gap-3 text-ink-muted">
      <Spinner className="size-6" />
      {label && <p className="text-sm">{label}</p>}
    </div>
  );
}
