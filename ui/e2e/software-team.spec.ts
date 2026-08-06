// The mvp.md §3 arc as a headless e2e: a real control plane, a real subprocess fleet on the
// keyless mock/loop spine, and the operator driving everything through the UI — actuate, submit
// an intent, approve the REAL proposed batch, accept the synthesized deliverable, deactuate.
// Org/profile/binding setup goes through the API (those editor flows are component-tested);
// the operate loop itself is exercised end to end in the browser.
import { expect, test, type APIRequestContext } from "@playwright/test";

const INTENT = "Add CSV export; all tests must pass";

interface OrgDoc {
  id: string;
  name: string;
  agents: { id: string }[];
}

async function seedBoundPod(request: APIRequestContext): Promise<OrgDoc> {
  const orgRes = await request.post("/api/organizations", {
    data: {
      name: "E2E Software Team",
      organizationType: "product-engineering",
      seed: { kind: "formation", formationKey: "product-engineering-pod" },
    },
  });
  expect(orgRes.ok()).toBeTruthy();
  const org: OrgDoc = await orgRes.json();

  const profRes = await request.post(`/api/organizations/${org.id}/profiles`, {
    data: { name: "Mock", provider: "mock", model: "mock-1" },
  });
  expect(profRes.ok()).toBeTruthy();
  const profile = await profRes.json();
  for (const agent of org.agents) {
    const bind = await request.put(`/api/organizations/${org.id}/bindings`, {
      data: { agentNodeId: agent.id, profileId: profile.id },
    });
    expect(bind.ok()).toBeTruthy();
  }
  return org;
}

test("the software team runs an intent end to end", async ({ page, request }) => {
  const org = await seedBoundPod(request);

  // ---- Actuate: four real agent processes boot and register.
  await page.goto("/actuate");
  const row = page.locator("div.rounded-xl").filter({ hasText: org.name });
  await row.getByRole("button", { name: "▶ Actuate" }).click();
  await expect(row.getByText(/live · 4\/4 ready/)).toBeVisible({ timeout: 90_000 });

  // ---- Submit the intent from the console; the SSE channel is the freshness spine.
  await page.goto("/execute");
  await page.getByRole("combobox").selectOption({ label: org.name });
  await expect(page.getByTitle("Live over SSE")).toBeVisible({ timeout: 20_000 });
  await page.getByPlaceholder(/Give the org work/).fill(INTENT);
  await page.getByRole("button", { name: "Submit intent" }).click();

  // ---- The lead's staged fan-out lands in the inbox as the REAL proposed batch.
  await expect(page.getByText(/3 proposed delegations/)).toBeVisible({ timeout: 120_000 });
  await page.getByRole("button", { name: "Approve" }).click();

  // ---- Children run and deliver; the manager reviews and synthesizes; the root's
  //      deliverable waits on the operator in the living plan. Anchor on the LEAD's row —
  //      children hit "delivering" first, and their acceptance is the manager's job, not ours.
  const rootRow = page
    .locator("div.group")
    .filter({ hasText: "Engineering Lead" })
    .filter({ hasText: "delivering" });
  await expect(rootRow).toBeVisible({ timeout: 150_000 });
  await rootRow.hover();
  await rootRow.getByRole("button", { name: "accept", exact: true }).click();

  // ---- Acceptance closes the arc: the intent chip flips and the pulse drains.
  await expect(page.getByText("completed", { exact: true })).toBeVisible({ timeout: 30_000 });
  await expect(page.getByText(/^0 open intents$/)).toBeVisible({ timeout: 20_000 });

  // ---- Deactuate from the UI — the fleet winds down cleanly.
  await page.goto("/actuate");
  await row.getByRole("button", { name: "Deactuate" }).click();
  await expect(row.getByRole("button", { name: "▶ Actuate" })).toBeVisible({ timeout: 60_000 });
});
