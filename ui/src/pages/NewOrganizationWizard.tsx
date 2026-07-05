import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import { useCatalog } from "../api/catalog";
import { createOrganization } from "../api/organizations";
import type { OrgType, SeedSpec } from "../api/types";
import { AppHeader } from "../components/AppHeader";
import { Button, CenteredSpinner, useToast } from "../components/common";
import { TypeStep } from "../components/wizard/TypeStep";
import { SeedStep } from "../components/wizard/SeedStep";

export function NewOrganizationWizard() {
  const navigate = useNavigate();
  const { toast } = useToast();
  const qc = useQueryClient();
  const catalog = useCatalog();

  const [step, setStep] = useState<1 | 2>(1);
  const [type, setType] = useState<OrgType | null>(null);
  const [name, setName] = useState("");
  const [seed, setSeed] = useState<SeedSpec>({ kind: "blank" });
  const [busy, setBusy] = useState(false);

  if (catalog.isLoading || !catalog.data) {
    return <CenteredSpinner label="Loading catalog…" />;
  }

  function chooseType(t: OrgType) {
    setType(t);
    setName(`Untitled ${t.title}`);
    // default seed: first suggested formation, else root, else blank
    if (t.formations[0]) setSeed({ kind: "formation", formationKey: t.formations[0] });
    else setSeed({ kind: "blank" });
    setStep(2);
  }

  async function create() {
    if (!type) return;
    setBusy(true);
    try {
      const doc = await createOrganization({
        name: name.trim() || `Untitled ${type.title}`,
        organizationType: type.key,
        seed,
      });
      qc.invalidateQueries({ queryKey: ["organizations"] });
      navigate(`/organizations/${doc.id}`);
    } catch {
      toast("Could not create organization.", "error");
      setBusy(false);
    }
  }

  return (
    <div className="min-h-full">
      <AppHeader
        actions={
          <Button variant="ghost" onClick={() => navigate("/")}>
            Cancel
          </Button>
        }
      />
      <main className="mx-auto max-w-4xl px-6 py-8">
        <div className="mb-6 flex items-center gap-3 text-sm">
          <StepDot n={1} active={step === 1} done={step > 1} label="Organization type" />
          <div className="h-px flex-1 bg-border" />
          <StepDot n={2} active={step === 2} done={false} label="Name & seed" />
        </div>

        {step === 1 && (
          <TypeStep catalog={catalog.data} selectedKey={type?.key ?? null} onSelect={chooseType} />
        )}

        {step === 2 && type && (
          <>
            <SeedStep
              catalog={catalog.data}
              orgType={type}
              name={name}
              onName={setName}
              seed={seed}
              onSeed={setSeed}
            />
            <div className="mt-8 flex justify-between">
              <Button variant="ghost" onClick={() => setStep(1)}>
                ← Back
              </Button>
              <Button variant="primary" disabled={busy} onClick={create}>
                {busy ? "Creating…" : "Create organization"}
              </Button>
            </div>
          </>
        )}
      </main>
    </div>
  );
}

function StepDot({
  n,
  active,
  done,
  label,
}: {
  n: number;
  active: boolean;
  done: boolean;
  label: string;
}) {
  return (
    <div className="flex items-center gap-2">
      <span
        className={`flex size-6 items-center justify-center rounded-full text-xs font-semibold ${
          active || done ? "bg-accent text-accent-fg" : "bg-surface-2 text-ink-muted"
        }`}
      >
        {done ? "✓" : n}
      </span>
      <span className={active ? "font-medium text-ink" : "text-ink-muted"}>{label}</span>
    </div>
  );
}
