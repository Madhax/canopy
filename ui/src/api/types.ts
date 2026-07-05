export type { Catalog, CatalogRole, Formation, OrgType } from "../schema/catalog";
export type {
  Agent,
  ChildOrganizationDoc,
  CustomRole,
  Dependency,
  OrganizationDoc,
} from "../schema/organization";
export type { ValidationIssue } from "../validation/codes";

export interface OrgSummary {
  id: string;
  name: string;
  organizationType: string;
  agentCount: number;
  childOrgCount: number;
  updatedAt: string | null;
  valid: boolean;
}

export type SeedSpec =
  | { kind: "blank" }
  | { kind: "root"; roleKey: string }
  | { kind: "formation"; formationKey: string };
