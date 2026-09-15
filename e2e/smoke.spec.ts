import { expect, test } from "@playwright/test";

test("search to school detail, with GET-only traffic", async ({ page }) => {
  const methods: string[] = [];
  page.on("request", (request) => methods.push(request.method()));

  await page.goto("/?profile=first_generation&state=CA");

  await expect(page.getByText("Stanford University")).toBeVisible();
  await expect(page.getByText("42/100")).toBeVisible();

  await page.getByLabel("State").fill("CA");
  await expect(page).toHaveURL(/state=CA/);

  await page.getByRole("link", { name: "Stanford University" }).click();
  await expect(page).toHaveURL(/\/schools\/243744/);

  await expect(page.getByRole("heading", { name: "Stanford University" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Official links" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Evidence" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Not verified yet" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Playbook" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Deadlines" }).first()).toBeVisible();
  await expect(page.getByRole("heading", { name: "Programmes" })).toBeVisible();

  expect(methods.filter((method) => method === "POST")).toEqual([]);
});