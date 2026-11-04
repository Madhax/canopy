import { describe, expect, it } from "vitest";
import type { AgentBinding, AgentProfile } from "../schema/actuation";
import { modelInvalid, modelLabel, resolveNodeModel } from "./nodeModel";

const profile = (id: string, model: string): AgentProfile => ({
  id,
  teamId: "t1",
  name: id,
  provider: "mock",
  model,
  endpoint: null,
  apiKeySecretId: null,
  params: { maxOutputTokens: 4096, temperature: 0.7, providerOptions: {} },
  systemPreamble: "",
  createdAt: "",
  updatedAt: "",
});
const bind = (node: string, profileId: string, teamPath: string[] = []): AgentBinding => ({
  id: `b_${node}`,
  teamId: "t1",
  agentNodeId: node,
  teamPath,
  profileId,
});

describe("resolveNodeModel (UX-35)", () => {
  const profiles = [profile("def", "mock-1"), profile("own", "mock-2")];

  it("prefers the node's own binding over the team default", () => {
    const info = resolveNodeModel("a", [], [bind("a", "own")], profiles, "def");
    expect(info.source).toBe("node");
    expect(info.profile?.model).toBe("mock-2");
  });

  it("falls back to the team default, path-aware", () => {
    const info = resolveNodeModel("a", ["child"], [bind("a", "own")], profiles, "def");
    expect(info.source).toBe("team-default");
    expect(modelLabel(info)).toBe("mock · mock-1");
    expect(modelInvalid(info)).toBe(false);
  });

  it("is unspecified with neither — and flags it invalid", () => {
    const info = resolveNodeModel("a", [], [], profiles, null);
    expect(info.source).toBe("unspecified");
    expect(modelInvalid(info)).toBe(true);
    expect(modelLabel(info)).toBe("model unspecified");
  });

  it("flags a binding to a deleted profile as dangling", () => {
    const info = resolveNodeModel("a", [], [bind("a", "gone")], profiles, "def");
    expect(info.source).toBe("dangling");
    expect(modelInvalid(info)).toBe(true);
  });
});
