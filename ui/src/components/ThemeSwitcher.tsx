import { THEMES, useSettingsStore } from "../store/settingsStore";

// Segmented theme control. `compact` uses swatches only (for the editor toolbar).
export function ThemeSwitcher({ compact = false }: { compact?: boolean }) {
  const theme = useSettingsStore((s) => s.theme);
  const setTheme = useSettingsStore((s) => s.setTheme);

  return (
    <div className="flex items-center gap-1 rounded-lg border border-border bg-surface p-1">
      {THEMES.map((t) => (
        <button
          key={t.key}
          onClick={() => setTheme(t.key)}
          title={t.label}
          className={`flex items-center gap-1.5 rounded-md px-2 py-1 text-xs transition-colors ${
            theme === t.key ? "bg-surface-2 text-ink" : "text-ink-muted hover:text-ink"
          }`}
        >
          <Swatch theme={t.key} />
          {!compact && <span>{t.label}</span>}
        </button>
      ))}
    </div>
  );
}

function Swatch({ theme }: { theme: string }) {
  const fill =
    theme === "dark" ? "#23271f" : theme === "light" ? "#ffffff" : "#dfe7d2";
  const ring = theme === "dark" ? "#7fa06b" : "#4d6b40";
  return (
    <span
      className="size-3 rounded-full border"
      style={{ background: fill, borderColor: ring }}
      aria-hidden
    />
  );
}
