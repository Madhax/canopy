// Mirrors server/src/canopy_server/migrate.py. schemaVersion gates loading; v1
// (`canopy.organization`, `childOrganizations[].organization`) migrates to v2
// (`canopy.team`, `childTeams[].team`) and is accepted indefinitely — import is the
// compatibility surface; export always emits v2 (design/organizations/07 §2.2).
import { SCHEMA_VERSION, type TeamDoc } from "./team";

export class UnsupportedSchemaVersion extends Error {
  constructor(public version: unknown) {
    super(
      `Unsupported team schemaVersion: ${JSON.stringify(version)} ` +
        `(this build understands up to ${SCHEMA_VERSION})`,
    );
    this.name = "UnsupportedSchemaVersion";
  }
}

export function migrateTeam(doc: any): TeamDoc {
  if (doc == null || typeof doc !== "object") return doc;
  const version = doc.schemaVersion ?? SCHEMA_VERSION;
  if (typeof version !== "number" || version > SCHEMA_VERSION || version < 1) {
    throw new UnsupportedSchemaVersion(version);
  }

  if (version < 2 || doc.kind === "canopy.organization") {
    doc.kind = "canopy.team";
    doc.schemaVersion = SCHEMA_VERSION;
    if ("childOrganizations" in doc) {
      const children = doc.childOrganizations ?? [];
      delete doc.childOrganizations;
      doc.childTeams = children.map((child: any) => {
        if (child && typeof child === "object" && "organization" in child) {
          const { organization, ...rest } = child;
          return { ...rest, team: organization };
        }
        return child;
      });
    }
  }

  // Recurse (covers already-v2 children and freshly renamed ones alike).
  for (const child of doc.childTeams ?? []) {
    if (child && typeof child.team === "object") {
      child.team = migrateTeam(child.team);
    }
  }
  return doc as TeamDoc;
}
