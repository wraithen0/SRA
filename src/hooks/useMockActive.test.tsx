import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { useMockActive } from "./useMockActive";
import { request, resetMockState } from "../api/client";

function Probe({ forced = false }: { forced?: boolean }) {
  const active = useMockActive(forced);
  return <div data-testid="active">{String(active)}</div>;
}

afterEach(() => {
  vi.unstubAllGlobals();
  vi.unstubAllEnvs();
  resetMockState();
});

it("tracks the mock flag and reverts after recovery", async () => {
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

  render(<Probe />);
  expect(screen.getByTestId("active")).toHaveTextContent("false");

  await request("/api/v1/status");
  await waitFor(() => expect(screen.getByTestId("active")).toHaveTextContent("true"), {
    timeout: 2000
  });

  await request("/api/v1/status");
  await waitFor(() => expect(screen.getByTestId("active")).toHaveTextContent("false"), {
    timeout: 2000
  });
});

it("stays true when forced", async () => {
  vi.stubEnv("VITE_SRA_MOCK", "1");
  render(<Probe forced />);
  expect(screen.getByTestId("active")).toHaveTextContent("true");
});