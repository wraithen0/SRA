import school243744 from "../fixtures/school.243744.json";
import school230038 from "../fixtures/school.230038.json";
import searchCa from "../fixtures/search.ca.first_generation.json";
import profilesFixture from "../fixtures/profiles.json";
import topicsFixture from "../fixtures/topics.json";
import statusFixture from "../fixtures/status.json";

const schools: Record<string, unknown> = {
  "243744": school243744,
  "230038": school230038,
  Stanford: school243744,
  "Stanford University": school243744
};

export function mockRequest<T>(path: string, params: Record<string, unknown> = {}): Promise<T> {
  const rawPath = path.split("?")[0];

  if (rawPath === "/api/v1/search") {
    const state = String(params.state ?? "CA").toUpperCase();
    const profile = String(params.profile ?? "first_generation");
    if (state === "CA" && profile === "first_generation") {
      return Promise.resolve(searchCa as unknown as T);
    }
    return Promise.resolve({ results: [], total: 0, limit: 10, offset: 0 } as unknown as T);
  }

  if (rawPath.startsWith("/api/v1/schools/")) {
    const key = decodeURIComponent(rawPath.slice("/api/v1/schools/".length));
    const found = schools[key];
    if (!found) return Promise.reject(new Error(`__mock_404__${key}`));
    return Promise.resolve(found as unknown as T);
  }

  if (rawPath === "/api/v1/programs") {
    return Promise.resolve({ programs: [] } as unknown as T);
  }

  if (rawPath === "/api/v1/deadlines") {
    const unitid = String(params.unitid ?? "243744");
    const found = schools[unitid] as { deadlines?: unknown[] } | undefined;
    return Promise.resolve({ deadlines: found?.deadlines ?? [] } as unknown as T);
  }

  if (rawPath === "/api/v1/status") {
    return Promise.resolve(statusFixture as unknown as T);
  }

  if (rawPath === "/api/v1/profiles") {
    return Promise.resolve(profilesFixture as unknown as T);
  }

  if (rawPath === "/api/v1/topics") {
    return Promise.resolve(topicsFixture as unknown as T);
  }

  return Promise.reject(new Error(`__mock_unhandled__${rawPath}`));
}