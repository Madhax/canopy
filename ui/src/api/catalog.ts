import { useQuery } from "@tanstack/react-query";
import { apiGet } from "./client";
import type { Catalog, CatalogRole, Formation, OrgType } from "./types";

export function useCatalog() {
  return useQuery({
    queryKey: ["catalog"],
    queryFn: () => apiGet<Catalog>("/catalog"),
    staleTime: Infinity, // catalog is static for a given build
  });
}

/** Index helpers over a loaded catalog. */
export function indexCatalog(catalog: Catalog) {
  const roles = new Map<string, CatalogRole>(catalog.roles.map((r) => [r.key, r]));
  const formations = new Map<string, Formation>(catalog.formations.map((f) => [f.key, f]));
  const orgTypes = new Map<string, OrgType>(catalog.organizationTypes.map((o) => [o.key, o]));
  return { roles, formations, orgTypes };
}
