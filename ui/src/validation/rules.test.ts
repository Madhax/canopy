// The TS validator must reproduce every golden vector exactly — the same fixtures pytest uses
// (docs/org-chart-editor.md §5.4). If this drifts from the Python side, the vectors fail here.
import { readdirSync, readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import { describe, expect, it } from "vitest";
import { validateOrganization } from "./rules";
import { CODE_MESSAGES, type ValidationIssue } from "./codes";
import type { Catalog } from "../schema/catalog";

const here = dirname(fileURLToPath(import.meta.url));
const repoRoot = join(here, "..", "..", "..");
const vectorDir = join(repoRoot, "testdata", "validation");
const catalog = JSON.parse(
  readFileSync(join(repoRoot, "catalog", "catalog.json"), "utf-8"),
) as Catalog;

interface Vector {
  name: string;
  mode: "draft" | "export";
  document: any;
  expectedIssues: any[];
}

function normalize(issue: Partial<ValidationIssue>) {
  const out: Record<string, unknown> = { severity: issue.severity, code: issue.code };
  if (issue.agentIds && issue.agentIds.length) out.agentIds = [...issue.agentIds].sort();
  if (issue.dependencyIds && issue.dependencyIds.length)
    out.dependencyIds = [...issue.dependencyIds].sort();
  if (issue.orgPath && issue.orgPath.length) out.orgPath = issue.orgPath;
  return out;
}

function sortKey(issue: Record<string, unknown>): string {
  return `${issue.code}|${JSON.stringify(issue)}`;
}

const vectors: Vector[] = readdirSync(vectorDir)
  .filter((f) => f.endsWith(".json"))
  .sort()
  .map((f) => JSON.parse(readFileSync(join(vectorDir, f), "utf-8")));

describe("golden validation vectors", () => {
  it("has vectors", () => {
    expect(vectors.length).toBeGreaterThan(0);
  });

  for (const v of vectors) {
    it(v.name, () => {
      const issues = validateOrganization(v.document, v.mode, catalog);
      const actual = issues.map(normalize).sort((a, b) => sortKey(a).localeCompare(sortKey(b)));
      const expected = v.expectedIssues
        .map(normalize)
        .sort((a, b) => sortKey(a).localeCompare(sortKey(b)));
      expect(actual).toEqual(expected);
    });
  }

  it("every rule code is covered by a vector", () => {
    const seen = new Set<string>();
    for (const v of vectors) for (const i of v.expectedIssues) seen.add(i.code);
    const missing = Object.keys(CODE_MESSAGES).filter((c) => !seen.has(c));
    expect(missing).toEqual([]);
  });
});
