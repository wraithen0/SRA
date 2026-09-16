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
    const fetchSpy = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ detail: "boom" }), {
        status: 500,
        headers: { "content-type": "application/json" }
      })
    );
    vi.stubGlobal("fetch", fetchSpy);
    const err = (await request("/api/v1/status").catch((e) => e)) as ApiError;
    expect(err).toBeInstanceOf(ApiError);
    expect(err.status).toBe(500);
    expect(err.detail).toBe("boom");
    expect(fetchSpy).toHaveBeenCalledTimes(1);
    expect(isMockActive()).toBe(false);
  });

  it("uses the mock transport when VITE_SRA_MOCK is 1", async () => {
    vi.stubEnv("VITE_SRA_MOCK", "1");
    const fetchSpy = vi.fn();
    vi.stubGlobal("fetch", fetchSpy);
    const status = (await request("/api/v1/status")) as { institutions: number };
    expect(fetchSpy).not.toHaveBeenCalled();
    expect(status.institutions).toBe(6243);
    expect(isMockActive()).toBe(true);
  });

  it("falls back to fixtures on a network error in dev", async () => {
    vi.stubEnv("VITE_SRA_MOCK", "0");
    vi.stubEnv("PROD", false);
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("network down")));
    const status = (await request("/api/v1/status")) as { institutions: number };
    expect(status.institutions).toBe(6243);
    expect(isMockActive()).toBe(true);
  });

  it("does not fall back in production builds", async () => {
    vi.stubEnv("VITE_SRA_MOCK", "0");
    vi.stubEnv("PROD", true);
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("network down")));
    await expect(request("/api/v1/status")).rejects.toBeInstanceOf(TypeError);
    expect(isMockActive()).toBe(false);
  });

  it("clears mockActive on the next successful request after the backend recovers", async () => {
    vi.stubEnv("VITE_SRA_MOCK", "0");
    vi.stubEnv("PROD", false);
    const fetchMock = vi
      .fn()
      .mockRejectedValueOnce(new TypeError("network down"))
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ institutions: 999 }), {
          status: 200,
          headers: { "content-type": "application/json" }
        })
      );
    vi.stubGlobal("fetch", fetchMock);

    const first = (await request("/api/v1/status")) as { institutions: number };
    expect(first.institutions).toBe(6243);
    expect(isMockActive()).toBe(true);

    const second = (await request("/api/v1/status")) as { institutions: number };
    expect(second.institutions).toBe(999);
    expect(isMockActive()).toBe(false);
  });

  it("stays on fixtures when VITE_SRA_MOCK is 1 even if the API is reachable", async () => {
    vi.stubEnv("VITE_SRA_MOCK", "1");
    const fetchSpy = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ institutions: 999 }), { status: 200 })
    );
    vi.stubGlobal("fetch", fetchSpy);
    const status = (await request("/api/v1/status")) as { institutions: number };
    expect(fetchSpy).not.toHaveBeenCalled();
    expect(status.institutions).toBe(6243);
    expect(isMockActive()).toBe(true);
  });

  it("does not fall back on a 500 and clears a prior fallback flag", async () => {
    vi.stubEnv("VITE_SRA_MOCK", "0");
    vi.stubEnv("PROD", false);
    const fetchMock = vi
      .fn()
      .mockRejectedValueOnce(new TypeError("network down"))
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ detail: "boom" }), {
          status: 500,
          headers: { "content-type": "application/json" }
        })
      );
    vi.stubGlobal("fetch", fetchMock);

    await request("/api/v1/status").catch(() => undefined);
    expect(isMockActive()).toBe(true);

    const err = (await request("/api/v1/status").catch((e) => e)) as ApiError;
    expect(err).toBeInstanceOf(ApiError);
    expect(err.status).toBe(500);
    expect(err.detail).toBe("boom");
    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(isMockActive()).toBe(false);
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

  it("returns count/results envelopes from the mock for programs and deadlines", async () => {
    vi.stubEnv("VITE_SRA_MOCK", "1");
    const programs = (await request("/api/v1/programs")) as { count: number; results: unknown[] };
    expect(typeof programs.count).toBe("number");
    expect(Array.isArray(programs.results)).toBe(true);
    const deadlines = (await request("/api/v1/deadlines", { unitid: 243744 })) as {
      count: number;
      results: unknown[];
    };
    expect(typeof deadlines.count).toBe("number");
    expect(Array.isArray(deadlines.results)).toBe(true);
  });
});