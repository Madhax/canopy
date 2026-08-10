// Schema-level contract for `resolveOn` (docs/org-chart-editor.md §3.2): omitted defaults to
// "accepted", "delivered" round-trips, anything else fails parse. The Python side asserts the
// same in server/tests/test_validation.py against the shared golden vector.
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import { describe, expect, it } from "vitest";
import { teamSchema } from "./team";

const here = dirname(fileURLToPath(import.meta.url));
const vectorPath = join(here, "..", "..", "..", "testdata", "validation", "dep-resolve-on-delivered.json");
const vector = JSON.parse(readFileSync(vectorPath, "utf-8"));

describe("dependency resolveOn schema", () => {
  it("round-trips delivered and defaults omitted to accepted", () => {
    const doc = teamSchema.parse(vector.document);
    expect(doc.dependencies[0].resolveOn).toBe("delivered");
    expect(doc.dependencies[1].resolveOn).toBe("accepted"); // omitted in the fixture
  });

  it("rejects unknown values", () => {
    const broken = structuredClone(vector.document);
    broken.dependencies[0].resolveOn = "on-a-tuesday";
    expect(() => teamSchema.parse(broken)).toThrow();
  });
});
