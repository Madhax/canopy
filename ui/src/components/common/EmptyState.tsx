import type { ReactNode } from "react";

interface Props {
  title: string;
  children?: ReactNode;
  action?: ReactNode;
  icon?: ReactNode;
}

export function EmptyState({ title, children, action, icon }: Props) {
  return (
    <div className="mx-auto flex max-w-lg flex-col items-center gap-4 py-20 text-center">
      {icon && <div className="text-ink-subtle">{icon}</div>}
      <h2 className="text-lg font-semibold text-ink">{title}</h2>
      {children && <div className="text-sm leading-relaxed text-ink-muted">{children}</div>}
      {action && <div className="pt-1">{action}</div>}
    </div>
  );
}
