export type { Catalog, CatalogRole, Formation, OrgType } from "../schema/catalog";
export type {
  Agent,
  ChildTeamDoc,
  CustomRole,
  Dependency,
  TeamDoc,
} from "../schema/team";
export type { ValidationIssue } from "../validation/codes";

export interface OrgSummary {
  id: string;
  name: string;
  organizationType: string;
  agentCount: number;
  childTeamCount: number;
  updatedAt: string | null;
  valid: boolean;
  /** Organization membership — server-side state, never part of the document (C1). */
  organizationId?: string | null;
}

export type SeedSpec =
  | { kind: "blank" }
  | { kind: "root"; roleKey: string }
  | { kind: "formation"; formationKey: string };
