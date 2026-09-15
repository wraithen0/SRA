import { request } from "./client";
import type {
  Match,
  ProfileKey,
  ProfilesResponse,
  SearchQuery,
  SearchResponse,
  StatusResponse,
  TopicsResponse
} from "./types";

export function search(query: SearchQuery): Promise<SearchResponse> {
  return request<SearchResponse>("/api/v1/search", { ...query });
}

export function school(key: string, profile: ProfileKey): Promise<Match> {
  return request<Match>(`/api/v1/schools/${encodeURIComponent(key)}`, { profile });
}

export function programs(query: Record<string, unknown> = {}): Promise<unknown> {
  return request<unknown>("/api/v1/programs", query);
}

export function deadlines(unitid: number): Promise<unknown> {
  return request<unknown>("/api/v1/deadlines", { unitid });
}

export function status(): Promise<StatusResponse> {
  return request<StatusResponse>("/api/v1/status");
}

export function profiles(): Promise<ProfilesResponse> {
  return request<ProfilesResponse>("/api/v1/profiles");
}

export function topics(): Promise<TopicsResponse> {
  return request<TopicsResponse>("/api/v1/topics");
}