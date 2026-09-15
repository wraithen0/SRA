import { renderHook, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { useApi } from "./useApi";

describe("useApi", () => {
  it("resolves data and clears loading", async () => {
    const { result } = renderHook(() => useApi(() => Promise.resolve("ok"), []));
    expect(result.current.loading).toBe(true);
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.data).toBe("ok");
    expect(result.current.error).toBeNull();
  });

  it("captures errors", async () => {
    const { result } = renderHook(() => useApi(() => Promise.reject(new Error("nope")), []));
    await waitFor(() => expect(result.current.error).toBeInstanceOf(Error));
    expect(result.current.data).toBeNull();
  });

  it("does not warn about setting state after unmount", async () => {
    const spy = vi.spyOn(console, "error");
    const { unmount } = renderHook(() => useApi(() => Promise.resolve("ok"), []));
    unmount();
    await new Promise((resolve) => setTimeout(resolve, 10));
    expect(spy).not.toHaveBeenCalled();
    spy.mockRestore();
  });
});