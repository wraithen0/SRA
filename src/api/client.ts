import { mockRequest } from "./mock";

export class ApiError extends Error {
  status: number;
  detail: string;

  constructor(status: number, detail: string) {
    super(detail);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
  }
}

export class UnknownSchoolError extends ApiError {
  constructor(detail: string) {
    super(404, detail);
    this.name = "UnknownSchoolError";
  }
}

let mockActive = false;

export function isMockActive(): boolean {
  return mockActive;
}

export function resetMockState(): void {
  mockActive = false;
}

export function resolveConfig(): { baseUrl: string; mock: boolean } {
  return {
    baseUrl: import.meta.env.VITE_SRA_API_BASE ?? "http://localhost:8000",
    mock: import.meta.env.VITE_SRA_MOCK === "1"
  };
}

export function buildQuery(params: Record<string, unknown>): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === null || value === "") continue;
    search.set(key, String(value));
  }
  const qs = search.toString();
  return qs ? `?${qs}` : "";
}

async function readDetail(res: Response): Promise<string> {
  try {
    const body = (await res.json()) as { detail?: unknown };
    if (typeof body.detail === "string") return body.detail;
  } catch {
    return res.statusText || "Request failed";
  }
  return res.statusText || "Request failed";
}

function toApiError(err: Error, path: string): Error {
  if (err.message.startsWith("__mock_404__")) {
    const key = err.message.replace("__mock_404__", "");
    if (path.startsWith("/api/v1/schools/")) {
      return new UnknownSchoolError(`No record for ${key}.`);
    }
    return new ApiError(404, "Not found");
  }
  if (err.message.startsWith("__mock_unhandled__")) {
    return new ApiError(404, "Not found");
  }
  return err;
}

export async function request<T>(
  path: string,
  params: Record<string, unknown> = {}
): Promise<T> {
  const { baseUrl, mock } = resolveConfig();

  if (mock) {
    mockActive = true;
    return mockRequest<T>(path, params).catch((err: Error) => {
      throw toApiError(err, path);
    });
  }

  let res: Response;
  try {
    res = await fetch(`${baseUrl}${path}${buildQuery(params)}`, {
      method: "GET",
      headers: { accept: "application/json" }
    });
  } catch (err) {
    if (!import.meta.env.PROD) {
      mockActive = true;
      try {
        return await mockRequest<T>(path, params);
      } catch (mockErr) {
        throw toApiError(mockErr as Error, path);
      }
    }
    throw err;
  }

  if (!res.ok) {
    const detail = await readDetail(res);
    if (res.status === 404 && path.startsWith("/api/v1/schools/")) {
      throw new UnknownSchoolError(detail);
    }
    throw new ApiError(res.status, detail);
  }

  return (await res.json()) as T;
}