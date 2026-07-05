// Mirrors server/src/canopy_server/migrate.py. schemaVersion gates loading; v1 is identity.
import { SCHEMA_VERSION, type OrganizationDoc } from "./organization";

export class UnsupportedSchemaVersion extends Error {
  constructor(public version: unknown) {
    super(
      `Unsupported organization schemaVersion: ${JSON.stringify(version)} ` +
        `(this build understands up to ${SCHEMA_VERSION})`,
    );
    this.name = "UnsupportedSchemaVersion";
  }
}

export function migrateOrganization(doc: any): OrganizationDoc {
  if (doc == null || typeof doc !== "object") return doc;
  const version = doc.schemaVersion ?? SCHEMA_VERSION;
  if (typeof version !== "number" || version > SCHEMA_VERSION || version < 1) {
    throw new UnsupportedSchemaVersion(version);
  }
  // v1 identity; recurse into children so a mixed-version tree migrates as one unit.
  for (const child of doc.childOrganizations ?? []) {
    if (child && typeof child.organization === "object") {
      child.organization = migrateOrganization(child.organization);
    }
  }
  return doc as OrganizationDoc;
}
