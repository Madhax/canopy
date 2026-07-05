import { NavLink } from "react-router-dom";
import { clsx } from "clsx";
import { LeafMark } from "./AppHeader";
import { ThemeSwitcher } from "./ThemeSwitcher";

interface Phase {
  to: string;
  n: number;
  title: string;
  blurb: string;
  status: "live" | "soon";
}

const PHASES: Phase[] = [
  { to: "/", n: 1, title: "Build", blurb: "Shape the organization", status: "live" },
  { to: "/actuate", n: 2, title: "Actuate", blurb: "Spin up the agents", status: "soon" },
  { to: "/execute", n: 3, title: "Execute", blurb: "Run the work", status: "soon" },
];

// Global phase navigation (docs/phases.md). Build is live; Actuate/Execute are described-only.
export function Sidebar() {
  return (
    <aside className="flex w-60 shrink-0 flex-col border-r border-border bg-surface">
      <div className="flex items-center gap-2 border-b border-border px-4 py-3.5">
        <LeafMark />
        <span className="text-base font-semibold tracking-tight text-ink">Canopy</span>
      </div>

      <nav className="flex flex-1 flex-col gap-1 p-3">
        <div className="px-2 pb-1 text-[10px] font-semibold uppercase tracking-wider text-ink-subtle">
          Phases
        </div>
        {PHASES.map((p) => (
          <NavLink
            key={p.to}
            to={p.to}
            end={p.to === "/"}
            className={({ isActive }) =>
              clsx(
                "flex items-start gap-3 rounded-lg px-2.5 py-2 transition-colors",
                isActive ? "bg-surface-2" : "hover:bg-surface-2/60",
              )
            }
          >
            {({ isActive }) => (
              <>
                <span
                  className={clsx(
                    "mt-0.5 flex size-6 shrink-0 items-center justify-center rounded-full text-xs font-semibold",
                    isActive ? "bg-accent text-accent-fg" : "bg-surface-2 text-ink-muted",
                  )}
                >
                  {p.n}
                </span>
                <span className="min-w-0">
                  <span className="flex items-center gap-1.5">
                    <span className="text-sm font-medium text-ink">{p.title}</span>
                    {p.status === "soon" && (
                      <span className="rounded bg-surface-2 px-1 py-0.5 text-[9px] uppercase tracking-wide text-ink-subtle">
                        soon
                      </span>
                    )}
                  </span>
                  <span className="block text-xs text-ink-muted">{p.blurb}</span>
                </span>
              </>
            )}
          </NavLink>
        ))}
      </nav>

      <div className="border-t border-border p-3">
        <div className="mb-2 px-1 text-[10px] font-semibold uppercase tracking-wider text-ink-subtle">
          Theme
        </div>
        <ThemeSwitcher />
      </div>
    </aside>
  );
}
