// Zod mirror of the team document (server/src/canopy_server/models.py §Team).
// Kind `canopy.team`, schemaVersion 2 (v1 `canopy.organization` migrates in migrate.ts).
// Recursive (child teams nest full documents), so the schema is declared with z.lazy.
import { z } from "zod";
import { responsibilitySchema, salarySchema } from "./catalog";

export type { Deliverable, Responsibility, Salary } from "./catalog";

export const SCHEMA_VERSION = 2;

export const pointSchema = z.object({ x: z.number(), y: z.number() }).strict();

export const roleRefSchema = z
  .object({ key: z.string(), version: z.number().default(1) })
  .strict();

export const extensionsSchema = z
  .object({
    instructions: z.string().default(""),
    responsibilities: z.array(responsibilitySchema).default([]),
  })
  .strict();

export const agentSchema = z
  .object({
    id: z.string(),
    name: z.string(),
    role: roleRefSchema,
    managerId: z.string().nullable().default(null),
    extensions: extensionsSchema.default({ instructions: "", responsibilities: [] }),
    salary: salarySchema,
    position: pointSchema.default({ x: 0, y: 0 }),
  })
  .strict();

export const dependencySchema = z
  .object({
    id: z.string(),
    from: z.string(),
    to: z.string(),
    // When the dependent unlocks: at the upstream's acceptance (consume, default)
    // or at its delivery/submission (verify) — docs/domain-model.md §Dependency.
    resolveOn: z.enum(["accepted", "delivered"]).default("accepted"),
    note: z.string().nullable().optional(),
  })
  .strict();

export const customRoleSchema = z
  .object({
    key: z.string(),
    version: z.number().default(1),
    title: z.string(),
    group: z.string().default("custom"),
    purpose: z.string().default(""),
    responsibilities: z.array(responsibilitySchema).default([]),
    isManager: z.boolean().default(false),
    defaultSalary: salarySchema,
  })
  .strict();

// ---- Recursive Team / ChildTeam --------------------------------------------
export interface TeamDoc {
  kind: "canopy.team";
  schemaVersion: number;
  id: string;
  name: string;
  // The archetype key (catalog `organizationTypes[]` — field name kept for catalog
  // compatibility; the docs call the concept TeamType post-rename).
  organizationType: string;
  createdAt?: string | null;
  updatedAt?: string | null;
  agents: z.infer<typeof agentSchema>[];
  dependencies: z.infer<typeof dependencySchema>[];
  customRoles: z.infer<typeof customRoleSchema>[];
  childTeams: ChildTeamDoc[];
  meta: Record<string, unknown>;
}

export interface ChildTeamDoc {
  mountAgentId: string;
  team: TeamDoc;
}

export const teamSchema: z.ZodType<TeamDoc> = z.lazy(() =>
  z
    .object({
      kind: z.literal("canopy.team").default("canopy.team"),
      schemaVersion: z.number().default(SCHEMA_VERSION),
      id: z.string(),
      name: z.string(),
      organizationType: z.string(),
      createdAt: z.string().nullable().optional(),
      updatedAt: z.string().nullable().optional(),
      agents: z.array(agentSchema).default([]),
      dependencies: z.array(dependencySchema).default([]),
      customRoles: z.array(customRoleSchema).default([]),
      childTeams: z.array(childTeamSchema).default([]),
      meta: z.record(z.unknown()).default({}),
    })
    .strict(),
) as z.ZodType<TeamDoc>;

export const childTeamSchema: z.ZodType<ChildTeamDoc> = z.lazy(() =>
  z
    .object({
      mountAgentId: z.string(),
      team: teamSchema,
    })
    .strict(),
) as z.ZodType<ChildTeamDoc>;

export type Agent = z.infer<typeof agentSchema>;
export type Dependency = z.infer<typeof dependencySchema>;
export type CustomRole = z.infer<typeof customRoleSchema>;
export type Point = z.infer<typeof pointSchema>;
export type RoleRef = z.infer<typeof roleRefSchema>;
export type Extensions = z.infer<typeof extensionsSchema>;
