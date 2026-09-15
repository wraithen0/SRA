import type { ProfileKey, ProfileOption, SearchQuery } from "../api/types";

const PROFILE_KEYS: ProfileKey[] = [
  "first_generation",
  "student_with_disability",
  "international_stem"
];

export const DEFAULT_QUERY: SearchQuery = {
  profile: "first_generation",
  limit: 10,
  offset: 0
};

function toNonNegativeInt(value: string | null, fallback: number): number {
  if (value === null || value.trim() === "") return fallback;
  const n = Number(value);
  if (!Number.isFinite(n) || n < 0) return fallback;
  return Math.trunc(n);
}

export function parseSearchQuery(params: URLSearchParams): SearchQuery {
  const profileParam = params.get("profile");
  const profile = PROFILE_KEYS.includes(profileParam as ProfileKey)
    ? (profileParam as ProfileKey)
    : DEFAULT_QUERY.profile;

  const query: SearchQuery = {
    profile,
    limit: toNonNegativeInt(params.get("limit"), DEFAULT_QUERY.limit),
    offset: toNonNegativeInt(params.get("offset"), DEFAULT_QUERY.offset)
  };

  const q = params.get("q");
  if (q) query.q = q;
  const state = params.get("state");
  if (state) query.state = state;
  const control = params.get("control");
  if (control) query.control = control;
  const level = params.get("level");
  if (level) query.level = level;
  const require = params.get("require");
  if (require) query.require = require;

  const stemOnly = params.get("stem_only");
  if (stemOnly !== null) query.stem_only = stemOnly !== "false";

  const maxNetPrice = params.get("max_net_price");
  if (maxNetPrice !== null) {
    const n = Number(maxNetPrice);
    if (Number.isFinite(n) && n >= 0) query.max_net_price = Math.trunc(n);
  }

  return query;
}

export function serializeSearchQuery(query: SearchQuery): URLSearchParams {
  const params = new URLSearchParams();
  params.set("profile", query.profile);
  params.set("limit", String(query.limit));
  params.set("offset", String(query.offset));
  if (query.q) params.set("q", query.q);
  if (query.state) params.set("state", query.state);
  if (query.control) params.set("control", query.control);
  if (query.level) params.set("level", query.level);
  if (query.require) params.set("require", query.require);
  if (query.stem_only !== undefined) params.set("stem_only", String(query.stem_only));
  if (query.max_net_price !== undefined) params.set("max_net_price", String(query.max_net_price));
  return params;
}

export function profileLabel(key: string, options: ProfileOption[]): string {
  return options.find((option) => option.key === key)?.label ?? key;
}