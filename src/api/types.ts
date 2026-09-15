export type ProfileKey =
  | "first_generation"
  | "student_with_disability"
  | "international_stem";

export interface Institution {
  unitid: number;
  name: string;
  city: string | null;
  state_abbr: string | null;
  control: string | null;
  url_homepage: string | null;
  avg_net_price: number | null;
  [key: string]: unknown;
}

export interface Reason {
  signal: string;
  label: string;
  value: number;
  weight: number;
}

export interface Fact {
  topic: string;
  value: string;
  url: string | null;
  extractor: "rule" | "llm";
  confidence: number;
  evidence: string | null;
  observed_at: string | null;
  expires_at: string | null;
  stale: boolean;
}

export interface Deadline {
  label: string;
  date_iso: string;
  category: string;
  url: string | null;
  is_past: boolean;
  days_left: number;
}

export interface Program {
  program_id: string;
  name: string;
  official_url: string | null;
  amount_text: string | null;
  deadlines: Deadline[];
}

export type PlaybookStatus = "action" | "verify";

export interface PlaybookStep {
  order: number;
  title: string;
  detail: string;
  url: string | null;
  deadline: string | null;
  status: PlaybookStatus;
}

export interface Match {
  institution: Institution;
  score: number;
  signals: Record<string, number>;
  why: Reason[];
  needs_covered: string[];
  links: Record<string, string>;
  facts: Fact[];
  deadlines: Deadline[];
  programs: Program[];
  playbook: PlaybookStep[];
  gaps: string[];
  last_verified: string | null;
  stale: boolean;
}

export interface SearchResponse {
  results: Match[];
  total?: number;
  limit?: number;
  offset?: number;
}

export interface SearchQuery {
  profile: ProfileKey;
  q?: string;
  state?: string;
  control?: string;
  level?: string;
  stem_only?: boolean;
  max_net_price?: number;
  require?: string;
  limit: number;
  offset: number;
}

export interface StatusResponse {
  ok?: boolean;
  schools?: number;
  programs?: number;
  stale?: number;
  [key: string]: unknown;
}

export interface ProfileOption {
  key: string;
  label: string;
}

export interface TopicOption {
  key: string;
  label: string;
}

export interface ProfilesResponse {
  profiles: ProfileOption[];
}

export interface TopicsResponse {
  topics: TopicOption[];
}