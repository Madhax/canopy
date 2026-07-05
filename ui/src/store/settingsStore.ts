// Global UI preferences: color theme and org-chart layout direction. Persisted to localStorage
// and applied to <html> so CSS + React Flow pick them up. Not part of the document (view state).
import { create } from "zustand";

export type Theme = "sage" | "light" | "dark";
export type LayoutDirection = "BT" | "TB"; // BT = bottom-up (trunk at bottom, canopy up)

export const THEMES: { key: Theme; label: string }[] = [
  { key: "sage", label: "Sage" },
  { key: "light", label: "Light" },
  { key: "dark", label: "Dark" },
];

const THEME_KEY = "canopy:theme";
const DIR_KEY = "canopy:layoutDirection";

function readTheme(): Theme {
  const v = localStorage.getItem(THEME_KEY);
  return v === "light" || v === "dark" || v === "sage" ? v : "sage";
}

function readDirection(): LayoutDirection {
  return localStorage.getItem(DIR_KEY) === "TB" ? "TB" : "BT";
}

function applyTheme(theme: Theme) {
  document.documentElement.dataset.theme = theme;
}

interface SettingsStore {
  theme: Theme;
  layoutDirection: LayoutDirection;
  setTheme: (theme: Theme) => void;
  setLayoutDirection: (dir: LayoutDirection) => void;
  toggleLayoutDirection: () => void;
}

export const useSettingsStore = create<SettingsStore>((set, get) => ({
  theme: readTheme(),
  layoutDirection: readDirection(),
  setTheme: (theme) => {
    localStorage.setItem(THEME_KEY, theme);
    applyTheme(theme);
    set({ theme });
  },
  setLayoutDirection: (layoutDirection) => {
    localStorage.setItem(DIR_KEY, layoutDirection);
    set({ layoutDirection });
  },
  toggleLayoutDirection: () => get().setLayoutDirection(get().layoutDirection === "BT" ? "TB" : "BT"),
}));

/** Apply the persisted theme immediately at startup (before React renders). */
export function initTheme() {
  applyTheme(readTheme());
}
