// Contract fixtures parsed by the Zod side (risk AR-2). The same files are validated by pydantic
// in server/tests/test_contracts.py — if a field drifts on one side, one of the two suites fails.
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";
import {
  agentBindingSchema,
  agentProfileSchema,
  completionRequestSchema,
  completionResultSchema,
  secretMetaSchema,
} from "./actuation";

const here = path.dirname(fileURLToPath(import.meta.url));
const dir = path.resolve(here, "../../../testdata/contracts");

function load(name: string): unknown {
  return JSON.parse(fs.readFileSync(path.join(dir, name), "utf-8"));
}

describe("contract fixtures parse identically on the Zod side (AR-2)", () => {
  it("agent_profile.json", () => {
    const p = agentProfileSchema.parse(load("agent_profile.json"));
    expect(p.provider).toBe("anthropic");
    expect(p.params.maxOutputTokens).toBe(8192);
  });

  it("agent_binding.json", () => {
    const b = agentBindingSchema.parse(load("agent_binding.json"));
    expect(b.agentNodeId).toBe("a_k7mp2x9q");
    expect(b.orgPath).toEqual([]);
  });

  it("secret_meta.json", () => {
    const s = secretMetaSchema.parse(load("secret_meta.json"));
    expect(s.name).toBe("anthropic-key");
    expect("value" in s).toBe(false);
  });

  it("completion_request.json", () => {
    const r = completionRequestSchema.parse(load("completion_request.json"));
    expect(r.messages[0].role).toBe("user");
    expect(r.tools[0].name).toBe("write_file");
  });

  it("completion_result.json", () => {
    const r = completionResultSchema.parse(load("completion_result.json"));
    expect(r.toolCalls[0].name).toBe("produce_artifact");
    expect(r.outputTokens).toBe(340);
  });
});
