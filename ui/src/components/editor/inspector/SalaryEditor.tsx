import type { Salary } from "../../../schema/team";
import { formatMoney } from "../../../lib/format";

interface Props {
  salary: Salary;
  defaultSalary?: Salary;
  /** SALARY_INVALID on this node — the allowance field renders red. */
  invalid?: boolean;
  onChange: (salary: Salary) => void;
}

export function SalaryEditor({ salary, defaultSalary, invalid = false, onChange }: Props) {
  const set = (patch: Partial<Salary>) => onChange({ ...salary, ...patch });
  const step = 10000;
  const allowanceBad =
    invalid ||
    !Number.isInteger(salary.perAssignmentAllowance) ||
    salary.perAssignmentAllowance <= 0;
  const warnBad = salary.warnThresholdPct <= 0 || salary.warnThresholdPct > 100;
  const anyBad = allowanceBad || warnBad;

  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-center justify-between">
        <h4
          className={`text-xs font-semibold uppercase tracking-wide ${
            anyBad ? "text-danger" : "text-ink-muted"
          }`}
        >
          Salary
        </h4>
        {defaultSalary && (
          <button
            className="text-[11px] text-accent hover:underline"
            onClick={() => onChange({ ...defaultSalary })}
          >
            reset to role default
          </button>
        )}
      </div>

      <label className="flex flex-col gap-1">
        <span className={`text-xs ${allowanceBad ? "text-danger" : "text-ink-muted"}`}>
          Per-assignment allowance
        </span>
        <div className="flex items-center gap-1">
          <button
            className="h-8 w-8 rounded-md border border-border hover:bg-surface-2"
            onClick={() => set({ perAssignmentAllowance: Math.max(1, salary.perAssignmentAllowance - step) })}
          >
            −
          </button>
          <input
            type="number"
            aria-label="Per-assignment allowance"
            value={salary.perAssignmentAllowance}
            onChange={(e) => set({ perAssignmentAllowance: Math.max(0, Math.round(+e.target.value)) })}
            aria-invalid={allowanceBad || undefined}
            className={`h-8 flex-1 rounded-md border bg-canvas px-2 text-center text-sm outline-none ${
              allowanceBad
                ? "border-danger text-danger ring-1 ring-danger/40 focus:border-danger"
                : "border-border focus:border-accent"
            }`}
          />
          <button
            className="h-8 w-8 rounded-md border border-border hover:bg-surface-2"
            onClick={() => set({ perAssignmentAllowance: salary.perAssignmentAllowance + step })}
          >
            +
          </button>
          <span className="w-10 text-right text-xs text-ink-muted">
            {formatMoney(salary.perAssignmentAllowance)}
          </span>
        </div>
      </label>

      <label className="flex flex-col gap-1">
        <span
          className={`flex justify-between text-xs ${warnBad ? "text-danger" : "text-ink-muted"}`}
        >
          <span>Warn threshold</span>
          <span>{Math.round(salary.warnThresholdPct)}%</span>
        </span>
        <input
          type="range"
          min={1}
          max={100}
          value={salary.warnThresholdPct}
          aria-invalid={warnBad || undefined}
          onChange={(e) => set({ warnThresholdPct: +e.target.value })}
          className="accent-[var(--color-accent)]"
        />
      </label>

      <label className="flex items-center justify-between text-sm">
        <span className="text-ink">Hard stop at limit</span>
        <input
          type="checkbox"
          checked={salary.hardStop}
          onChange={(e) => set({ hardStop: e.target.checked })}
          className="size-4 accent-[var(--color-accent)]"
        />
      </label>
    </div>
  );
}
