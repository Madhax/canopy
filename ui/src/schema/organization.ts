// Zod mirror of the organization document (server/src/canopy_server/models.py §Organization).
// Recursive (child organizations nest full documents), so the schema is declared with z.lazy.
import { z } from "zod";
import { responsibilitySchema, salarySchema } from "./catalog";

export type { Deliverable, Responsibility, Salary } from "./catalog";

export const SCHEMA_VERSION = 1;

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

// ---- Recursive Organization / ChildOrganization ----------------------------
export interface OrganizationDoc {
  kind: "canopy.organization";
  schemaVersion: number;
  id: string;
  name: string;
  organizationType: string;
  createdAt?: string | null;
  updatedAt?: string | null;
  agents: z.infer<typeof agentSchema>[];
  dependencies: z.infer<typeof dependencySchema>[];
  customRoles: z.infer<typeof customRoleSchema>[];
  childOrganizations: ChildOrganizationDoc[];
  meta: Record<string, unknown>;
}

export interface ChildOrganizationDoc {
  mountAgentId: string;
  organization: OrganizationDoc;
}

export const organizationSchema: z.ZodType<OrganizationDoc> = z.lazy(() =>
  z
    .object({
      kind: z.literal("canopy.organization").default("canopy.organization"),
      schemaVersion: z.number().default(SCHEMA_VERSION),
      id: z.string(),
      name: z.string(),
      organizationType: z.string(),
      createdAt: z.string().nullable().optional(),
      updatedAt: z.string().nullable().optional(),
      agents: z.array(agentSchema).default([]),
      dependencies: z.array(dependencySchema).default([]),
      customRoles: z.array(customRoleSchema).default([]),
      childOrganizations: z.array(childOrganizationSchema).default([]),
      meta: z.record(z.unknown()).default({}),
    })
    .strict(),
) as z.ZodType<OrganizationDoc>;

export const childOrganizationSchema: z.ZodType<ChildOrganizationDoc> = z.lazy(() =>
  z
    .object({
      mountAgentId: z.string(),
      organization: organizationSchema,
    })
    .strict(),
) as z.ZodType<ChildOrganizationDoc>;

export type Agent = z.infer<typeof agentSchema>;
export type Dependency = z.infer<typeof dependencySchema>;
export type CustomRole = z.infer<typeof customRoleSchema>;
export type Point = z.infer<typeof pointSchema>;
export type RoleRef = z.infer<typeof roleRefSchema>;
export type Extensions = z.infer<typeof extensionsSchema>;
