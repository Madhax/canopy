import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import { describe, expect, it } from "vitest";
import type { Catalog } from "../schema/catalog";
import { buildSeedContent } from "./newOrg";

const here = dirname(fileURLToPath(import.meta.url));
const catalog = JSON.parse(
  readFileSync(join(here, "..", "..", "..", "catalog", "catalog.json"), "utf-8"),
) as Catalog;

describe("buildSeedContent", () => {
  it("blank -> empty", () => {
    expect(buildSeedContent(catalog, { kind: "blank" })).toEqual({ agents: [], dependencies: [] });
  });

  it("root -> single rootless agent", () => {
    const { agents, dependencies } = buildSeedContent(catalog, {
      kind: "root",
      roleKey: "engineering-lead",
    });
    expect(agents).toHaveLength(1);
    expect(agents[0].managerId).toBeNull();
    expect(dependencies).toHaveLength(0);
  });

  it("formation -> manager + members with slot-resolved deps", () => {
    const { agents, dependencies } = buildSeedContent(catalog, {
      kind: "formation",
      formationKey: "product-engineering-pod",
    });
    expect(agents).toHaveLength(4);
    expect(agents.filter((a) => a.managerId === null)).toHaveLength(1);
    expect(dependencies).toHaveLength(2); // QA depends on backend + frontend
    const ids = new Set(agents.map((a) => a.id));
    for (const d of dependencies) expect(ids.has(d.from) && ids.has(d.to)).toBe(true);
  });
});
