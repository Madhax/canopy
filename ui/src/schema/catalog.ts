// Zod mirror of the catalog models (server/src/canopy_server/models.py).
import { z } from "zod";

export const ROLE_GROUPS = [
  "leadership-coordination",
  "software-engineering",
  "infra-security-reliability",
  "data-ai",
  "product-design",
  "marketing-growth-content",
  "sales-customer",
  "people-recruiting",
  "finance-legal",
  "physical-operations",
  "healthcare",
  "research-education",
  "media-events",
  "professional-services",
  "nonprofit-community",
  "custom",
] as const;

export const ORG_SECTIONS = [
  "tech-enterprise",
  "physical-world",
  "knowledge-community",
  "professional-services",
  "corporate-chassis",
] as const;

export const deliverableSchema = z
  .object({
    kind: z.enum(["artifact", "attestation"]),
    type: z.string(),
  })
  .strict();

export const responsibilitySchema = z
  .object({
    duty: z.string(),
    deliverable: deliverableSchema,
  })
  .strict();

export const salarySchema = z
  .object({
    perAssignmentAllowance: z.number(),
    warnThresholdPct: z.number().default(80),
    hardStop: z.boolean().default(true),
  })
  .strict();

export const catalogRoleSchema = z
  .object({
    key: z.string(),
    version: z.number().default(1),
    title: z.string(),
    group: z.string(),
    purpose: z.string(),
    responsibilities: z.array(responsibilitySchema).default([]),
    isManager: z.boolean().default(false),
    defaultSalary: salarySchema,
    toolGrants: z.array(z.string()).default([]), // grant keys (agent-envelope.md §3.2)
    defaultRuntime: z.string().default("loop"), // runtime kind (envelope §4)
  })
  .strict();

// One capability the platform can hand to an agent (agent-envelope.md §3.1).
export const toolGrantSchema = z
  .object({
    key: z.string(),
    title: z.string(),
    riskClass: z.enum(["inert", "read", "write", "execute", "consequential"]),
    minSandboxTier: z.number().default(0),
    executor: z.string().default(""),
    credentialKind: z.string().nullable().optional(),
    governedActions: z.array(z.string()).default([]),
    params: z.record(z.unknown()).default({}),
  })
  .strict();

export const formationSlotSchema = z.object({ slot: z.string(), roleKey: z.string() }).strict();

export const formationDepSchema = z
  .object({
    from: z.string(),
    to: z.string(),
    // Verify edges (`delivered`) unlock at submission; consume (`accepted`, default) at sign-off.
    resolveOn: z.enum(["accepted", "delivered"]).default("accepted"),
  })
  .strict();

export const formationSchema = z
  .object({
    key: z.string(),
    title: z.string(),
    purpose: z.string(),
    manager: formationSlotSchema,
    members: z.array(formationSlotSchema).default([]),
    dependencies: z.array(formationDepSchema).default([]),
    artifactFlow: z.string().default(""),
  })
  .strict();

export const orgTypeSchema = z
  .object({
    key: z.string(),
    title: z.string(),
    section: z.string(),
    description: z.string(),
    exampleIntent: z.string().default(""),
    rolePalette: z.array(z.string()).default([]),
    formations: z.array(z.string()).default([]),
  })
  .strict();

export const catalogSchema = z
  .object({
    kind: z.literal("canopy.catalog").default("canopy.catalog"),
    catalogVersion: z.number().default(1),
    organizationTypes: z.array(orgTypeSchema).default([]),
    roles: z.array(catalogRoleSchema).default([]),
    formations: z.array(formationSchema).default([]),
    toolGrants: z.array(toolGrantSchema).default([]),
  })
  .strict();

export type Deliverable = z.infer<typeof deliverableSchema>;
export type Responsibility = z.infer<typeof responsibilitySchema>;
export type Salary = z.infer<typeof salarySchema>;
export type CatalogRole = z.infer<typeof catalogRoleSchema>;
export type ToolGrant = z.infer<typeof toolGrantSchema>;
export type Formation = z.infer<typeof formationSchema>;
export type OrgType = z.infer<typeof orgTypeSchema>;
export type Catalog = z.infer<typeof catalogSchema>;
