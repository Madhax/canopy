// Role-group + archetype-section color assignments (docs §7.6). Explicit hex so we can drive
// inline accents (node left borders, dots) reliably — AA-checked against both surfaces.

export const ROLE_GROUP_COLORS: Record<string, string> = {
  "leadership-coordination": "#d97706", // amber
  "software-engineering": "#2563eb", // blue
  "infra-security-reliability": "#0891b2", // cyan
  "data-ai": "#7c3aed", // violet
  "product-design": "#db2777", // pink
  "marketing-growth-content": "#16a34a", // green
  "sales-customer": "#ea580c", // orange
  "people-recruiting": "#0d9488", // teal
  "finance-legal": "#475569", // slate
  "physical-operations": "#92400e", // brown
  healthcare: "#dc2626", // red
  "research-education": "#4f46e5", // indigo
  "media-events": "#c026d3", // fuchsia
  "professional-services": "#78716c", // stone
  "nonprofit-community": "#65a30d", // lime
  custom: "#6b7280", // gray
};

export const ROLE_GROUP_LABELS: Record<string, string> = {
  "leadership-coordination": "Leadership & Coordination",
  "software-engineering": "Software Engineering",
  "infra-security-reliability": "Infra, Security & Reliability",
  "data-ai": "Data & AI",
  "product-design": "Product & Design",
  "marketing-growth-content": "Marketing, Growth & Content",
  "sales-customer": "Sales & Customer",
  "people-recruiting": "People & Recruiting",
  "finance-legal": "Finance & Legal",
  "physical-operations": "Physical Operations",
  healthcare: "Healthcare",
  "research-education": "Research & Education",
  "media-events": "Media & Events",
  "professional-services": "Professional Services",
  "nonprofit-community": "Nonprofit & Community",
  custom: "Custom",
};

export const SECTION_COLORS: Record<string, string> = {
  "tech-enterprise": "#2563eb",
  "physical-world": "#b45309",
  "knowledge-community": "#4f46e5",
  "professional-services": "#0d9488",
  "corporate-chassis": "#475569",
};

export const SECTION_LABELS: Record<string, string> = {
  "tech-enterprise": "Tech Enterprise",
  "physical-world": "Physical World",
  "knowledge-community": "Knowledge & Community",
  "professional-services": "Professional Services",
  "corporate-chassis": "Corporate Chassis",
};

export const SECTION_ORDER = [
  "tech-enterprise",
  "physical-world",
  "knowledge-community",
  "professional-services",
  "corporate-chassis",
];

export function roleGroupColor(group: string): string {
  return ROLE_GROUP_COLORS[group] ?? ROLE_GROUP_COLORS.custom;
}

export function sectionColor(section: string): string {
  return SECTION_COLORS[section] ?? "#6b7280";
}
