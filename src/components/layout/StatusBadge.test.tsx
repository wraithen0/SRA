import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { StatusBadge } from "./StatusBadge";
import { resetMockState } from "../../api/client";

afterEach(() => {
  vi.unstubAllEnvs();
  resetMockState();
});

describe("StatusBadge", () => {
  it("reads institutions from /status and labels them as schools", async () => {
    vi.stubEnv("VITE_SRA_MOCK", "1");
    render(<StatusBadge />);
    await waitFor(() => expect(screen.getByText(/6,243 schools/)).toBeInTheDocument());
    expect(screen.getByText(/75 programmes/)).toBeInTheDocument();
  });
});