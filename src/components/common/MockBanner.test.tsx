import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { MockBanner } from "./MockBanner";
import { request, resetMockState } from "../../api/client";

afterEach(() => {
  vi.unstubAllGlobals();
  vi.unstubAllEnvs();
  resetMockState();
});

it("appears when the sidecar is unreachable and disappears after recovery", async () => {
  vi.stubEnv("VITE_SRA_MOCK", "0");
  vi.stubEnv("PROD", false);
  const fetchMock = vi
    .fn()
    .mockRejectedValueOnce(new TypeError("network down"))
    .mockResolvedValueOnce(
      new Response(JSON.stringify({ schools: 999 }), {
        status: 200,
        headers: { "content-type": "application/json" }
      })
    );
  vi.stubGlobal("fetch", fetchMock);

  render(<MockBanner />);
  expect(screen.queryByRole("status")).toBeNull();

  await request("/api/v1/status");
  await waitFor(() => expect(screen.getByRole("status")).toBeInTheDocument(), { timeout: 2000 });

  await request("/api/v1/status");
  await waitFor(() => expect(screen.queryByRole("status")).toBeNull(), { timeout: 2000 });
});

it("stays visible under VITE_SRA_MOCK=1 even when the API is reachable", async () => {
  vi.stubEnv("VITE_SRA_MOCK", "1");
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ schools: 999 }), { status: 200 })
    )
  );

  render(<MockBanner />);
  await request("/api/v1/status");
  await waitFor(() => expect(screen.getByRole("status")).toBeInTheDocument(), { timeout: 2000 });
});