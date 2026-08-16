// The what-if strip (design/organizations/06 §3, C5): the operator states a goal —
// "free N points of this window before the reset" — and the strip enumerates the
// cheapest knob combinations that satisfy it, computed server-side from the SAME
// attribution math as the prediction chips. Apply is one click per suggestion;
// nothing auto-applies.
import { useState } from "react";
import {
  useUpdateSchedule,
  useWhatIf,
  type CapacityAccount,
  type WhatIfAction,
  type WhatIfResult,
  type WhatIfSuggestion,
} from "../../api/capacity";
import { ApiError } from "../../api/client";
import { Button, useToast } from "../common";

function patchFor(action: WhatIfAction): { teamId: string } & Record<string, unknown> {
  if (action.knob === "pace") {
    return { teamId: action.teamId, ...(action.value as Record<string, unknown>) };
  }
  return { teamId: action.teamId, [action.knob]: action.value };
}

function SuggestionRow({ s, onApplied }: { s: WhatIfSuggestion; onApplied: () => void }) {
  const { toast } = useToast();
  const update = useUpdateSchedule();

  async function apply() {
    try {
      for (const action of s.actions) {
        await update.mutateAsync(patchFor(action));
      }
      toast("Applied.", "success");
      onApplied();
    } catch (err) {
      toast(err instanceof ApiError ? err.message : "Apply failed.", "error");
    }
  }

  const label = s.actions
    .map((a) => `${a.label} ${a.teamName ?? a.teamId}`)
    .join(" + ");
  return (
    <li className="flex items-center gap-2 rounded-md border border-border bg-surface px-2 py-1 text-xs">
      <span className="min-w-0 flex-1 truncate text-ink" title={label}>
        {label}
      </span>
      <span className="shrink-0 tabular-nums text-ink-muted">
        −{s.freesPpHr} pp/hr · {s.freesPp} pp
      </span>
      {s.satisfies != null && (
        <span className={s.satisfies ? "shrink-0 text-ok" : "shrink-0 text-ink-subtle"}>
          {s.satisfies ? "✓" : "not enough"}
        </span>
      )}
      <Button size="sm" variant="secondary" onClick={apply} disabled={update.isPending}>
        Apply
      </Button>
    </li>
  );
}

export function WhatIfBar({ account }: { account: CapacityAccount | undefined }) {
  const { toast } = useToast();
  const whatIf = useWhatIf();
  const [needed, setNeeded] = useState("");
  const [result, setResult] = useState<WhatIfResult | null>(null);

  async function compute() {
    try {
      const res = await whatIf.mutateAsync({
        accountId: account?.id,
        neededPp: needed === "" ? undefined : Number(needed),
      });
      setResult(res);
    } catch (err) {
      toast(err instanceof ApiError ? err.message : "Computation failed.", "error");
    }
  }

  return (
    <section className="rounded-xl border border-border bg-surface p-3">
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-xs font-semibold text-ink">What if…</span>
        <label className="flex items-center gap-1 text-xs text-ink-muted">
          I need to free
          <input
            type="number"
            min={0}
            step="0.5"
            className="w-16 rounded-md border border-border bg-surface px-1.5 py-1 text-ink"
            value={needed}
            placeholder="any"
            onChange={(e) => setNeeded(e.target.value)}
          />
          pp{result?.windowKey ? ` of ${result.windowKey}` : ""}
          {result?.horizonBasis === "until-reset" ? " before the reset" : ""}
        </label>
        <Button size="sm" variant="secondary" onClick={compute} disabled={whatIf.isPending}>
          {whatIf.isPending ? "Computing…" : "Show my options"}
        </Button>
        {result?.windowKey && (
          <span className="text-[10px] text-ink-subtle" title={result.basis}>
            over {result.horizonH} h · {result.basis}
          </span>
        )}
      </div>
      {result && (
        <ul className="mt-2 flex flex-col gap-1">
          {result.suggestions.length === 0 ? (
            <li className="text-xs text-ink-subtle">
              No burn to reallocate — the pool is quiet.
            </li>
          ) : (
            result.suggestions
              .slice(0, 5)
              .map((s, i) => (
                <SuggestionRow key={i} s={s} onApplied={() => setResult(null)} />
              ))
          )}
        </ul>
      )}
    </section>
  );
}
