import { afterEach, describe, expect, it, vi } from "vitest";
import {
  ApiError,
  UnknownSchoolError,
  buildQuery,
  isMockActive,
  request,
  resetMockState
} from "./client";

afterEach(() => {
  vi.unstubAllGlobals();
  vi.unstubAllEnvs();
  resetMockState();
});

describe("buildQuery", () => {
  it("omits undefined and empty values and encodes the rest", () => {
    expect(buildQuery({ profile: "first_generation", state: "CA", q: undefined })).toBe(
      "?profile=first_generation&state=CA"
    );
  });

  it("serializes booleans and numbers", () => {
    expect(buildQuery({ stem_only: true, limit: 10 })).toBe("?stem_only=true&limit=10");
  });

  it("returns an empty string when there is nothing to send", () => {
    expect(buildQuery({})).toBe("");
  });
});

describe("request", () => {
  it("throws UnknownSchoolError on a 404 for a school path", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify({ detail: "unknown school" }), {
          status: 404,
          headers: { "content-type": "application/json" }
        })
      )
    );
    await expect(request("/api/v1/schools/nope")).rejects.toBeInstanceOf(UnknownSchoolError);
  });

  it("throws ApiError carrying the detail on a 500", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify({ detail: "boom" }), {
          status: 500,
          headers: { "content-type": "application/json" }
        })
      )
    );
    const err = (await request("/api/v1/status").catch((e) => e)) as ApiError;
    expect(err).toBeInstanceOf(ApiError);
    expect(err.status).toBe(500);
    expect(err.detail).toBe("boom");
  });

  it("uses the mock transport when VITE_SRA_MOCK is 1", async () => {
    vi.stubEnv("VITE_SRA_MOCK", "1");
    const fetchSpy = vi.fn();
    vi.stubGlobal("fetch", fetchSpy);
    const status = (await request("/api/v1/status")) as { schools: number };
    expect(fetchSpy).not.toHaveBeenCalled();
    expect(status.schools).toBe(6243);
    expect(isMockActive()).toBe(true);
  });

  it("falls back to fixtures on a network error in dev", async () => {
    vi.stubEnv("VITE_SRA_MOCK", "0");
    vi.stubEnv("PROD", false);
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("network down")));
    const status = (await request("/api/v1/status")) as { schools: number };
    expect(status.schools).toBe(6243);
    expect(isMockActive()).toBe(true);
  });

  it("does not fall back in production builds", async () => {
    vi.stubEnv("VITE_SRA_MOCK", "0");
    vi.stubEnv("PROD", true);
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("network down")));
    await expect(request("/api/v1/status")).rejects.toBeInstanceOf(TypeError);
  });

  it("returns the national layer and cache provenance from the search fixture", async () => {
    vi.stubEnv("VITE_SRA_MOCK", "1");
    const data = (await request("/api/v1/search", {
      profile: "first_generation",
      state: "CA"
    })) as {
      universe_size?: number;
      cache?: { hit: boolean; fingerprint: string };
      national_programs?: unknown[];
      national_deadlines?: unknown[];
    };
    expect(data.universe_size).toBe(6243);
    expect(data.cache).toEqual({ hit: true, fingerprint: "7f8b9c3" });
    expect(data.national_programs?.length).toBeGreaterThanOrEqual(2);
    expect(data.national_deadlines?.length).toBeGreaterThanOrEqual(2);
  });
});