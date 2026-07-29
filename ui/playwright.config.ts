// The E6 headless e2e (mvp.md): the whole demo against a REAL control plane — the webServer is
// uvicorn serving the built UI (run `pnpm build` first) over a throwaway data dir, and every
// agent is a real subprocess. CANOPY_PORT must match the serve port: booted agents dial
// `get_cp_url()` to register, so a mismatch looks like "boot timeout: agent did not register".
import { defineConfig } from "@playwright/test";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";

const PORT = 8710;
const dataDir = fs.mkdtempSync(path.join(os.tmpdir(), "canopy-e2e-"));

export default defineConfig({
  testDir: "./e2e",
  timeout: 240_000, // the pod really works the intent — loop ticks, boots, reviews
  expect: { timeout: 15_000 },
  retries: process.env.CI ? 1 : 0,
  workers: 1, // one control plane, one fleet
  reporter: process.env.CI ? [["github"], ["list"]] : "list",
  use: {
    baseURL: `http://127.0.0.1:${PORT}`,
    trace: "retain-on-failure",
  },
  webServer: {
    command:
      `uv run --project ../server uvicorn canopy_server.main:app --host 127.0.0.1 --port ${PORT}`,
    url: `http://127.0.0.1:${PORT}/api/health`,
    reuseExistingServer: false,
    timeout: 90_000,
    env: {
      ...process.env,
      CANOPY_PORT: String(PORT),
      CANOPY_DATA_DIR: dataDir,
    },
  },
});
