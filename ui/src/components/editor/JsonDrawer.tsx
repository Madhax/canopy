import { useState } from "react";
import type { OrganizationDoc } from "../../schema/organization";
import { Button } from "../common";

// Live view of the serialized document as you edit — the plan's serialization-focused additive.
export function JsonDrawer({
  doc,
  open,
  onClose,
}: {
  doc: OrganizationDoc;
  open: boolean;
  onClose: () => void;
}) {
  const [copied, setCopied] = useState(false);
  if (!open) return null;
  const text = JSON.stringify(doc, null, 2);

  return (
    <div className="flex w-[420px] shrink-0 flex-col border-l border-border bg-surface">
      <div className="flex items-center justify-between border-b border-border px-3 py-2">
        <span className="text-xs font-semibold uppercase tracking-wide text-ink-muted">
          Serialized document
        </span>
        <div className="flex items-center gap-1">
          <Button
            size="sm"
            variant="ghost"
            onClick={() => {
              navigator.clipboard.writeText(text);
              setCopied(true);
              setTimeout(() => setCopied(false), 1500);
            }}
          >
            {copied ? "Copied" : "Copy"}
          </Button>
          <Button size="sm" variant="ghost" onClick={onClose}>
            ✕
          </Button>
        </div>
      </div>
      <pre className="flex-1 overflow-auto p-3 text-[11px] leading-relaxed text-ink">{text}</pre>
    </div>
  );
}
