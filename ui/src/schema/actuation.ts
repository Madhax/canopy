// Zod mirror of the phase-2 control-plane models (server/src/canopy_server/profiles.py,
// secretstore.py, gateway/base.py). Kept honest against the server by the shared contract
// fixtures in testdata/contracts (parsed by both pydantic and these schemas — risk AR-2).
import { z } from "zod";

export const providerSchema = z.enum(["anthropic", "gemini", "mock"]);
export type Provider = z.infer<typeof providerSchema>;

export const profileParamsSchema = z
  .object({
    maxOutputTokens: z.number().int().default(4096),
    temperature: z.number().default(0.7),
    providerOptions: z.record(z.string(), z.unknown()).default({}),
  })
  .strict();
export type ProfileParams = z.infer<typeof profileParamsSchema>;

export const agentProfileSchema = z
  .object({
    id: z.string(),
    organizationId: z.string(),
    name: z.string(),
    provider: providerSchema,
    model: z.string(),
    endpoint: z.string().nullable().default(null),
    apiKeySecretId: z.string().nullable().default(null),
    params: profileParamsSchema,
    systemPreamble: z.string().default(""),
    createdAt: z.string(),
    updatedAt: z.string(),
  })
  .strict();
export type AgentProfile = z.infer<typeof agentProfileSchema>;

export const agentBindingSchema = z
  .object({
    id: z.string(),
    organizationId: z.string(),
    agentNodeId: z.string(),
    orgPath: z.array(z.string()).default([]),
    profileId: z.string(),
  })
  .strict();
export type AgentBinding = z.infer<typeof agentBindingSchema>;

export const secretMetaSchema = z
  .object({
    id: z.string(),
    organizationId: z.string(),
    name: z.string(),
    createdAt: z.string(),
  })
  .strict();
export type SecretMeta = z.infer<typeof secretMetaSchema>;

export const validationResultSchema = z
  .object({ ok: z.boolean(), error: z.string().nullable().default(null) })
  .strict();
export type ValidationResult = z.infer<typeof validationResultSchema>;

// Gateway wire shapes — used by the contract fixtures; the editor doesn't call the gateway.
export const messageSchema = z.object({ role: z.string(), content: z.string() }).strict();

export const toolSpecSchema = z
  .object({
    name: z.string(),
    description: z.string().default(""),
    inputSchema: z.record(z.string(), z.unknown()).default({}),
  })
  .strict();

export const completionRequestSchema = z
  .object({
    system: z.string().default(""),
    messages: z.array(messageSchema).default([]),
    tools: z.array(toolSpecSchema).default([]),
    maxOutputTokens: z.number().int().default(4096),
    temperature: z.number().default(0.7),
    providerOptions: z.record(z.string(), z.unknown()).default({}),
  })
  .strict();

export const toolCallSchema = z
  .object({
    id: z.string(),
    name: z.string(),
    arguments: z.record(z.string(), z.unknown()).default({}),
  })
  .strict();

export const completionResultSchema = z
  .object({
    text: z.string().default(""),
    toolCalls: z.array(toolCallSchema).default([]),
    inputTokens: z.number().int().default(0),
    outputTokens: z.number().int().default(0),
    stopReason: z.string().default("end_turn"),
    providerRaw: z.record(z.string(), z.unknown()).default({}),
  })
  .strict();
