import { describe, expect, it } from "vitest";
import { DEFAULT_QUERY, parseSearchQuery, serializeSearchQuery, profileLabel } from "./url";

describe("parseSearchQuery", () => {
  it("applies defaults for absent params", () => {
    expect(parseSearchQuery(new URLSearchParams())).toEqual(DEFAULT_QUERY);
  });

  it("parses booleans, numbers, and known profiles", () => {
    const q = parseSearchQuery(
      new URLSearchParams("profile=international_stem&stem_only=true&limit=25&max_net_price=15000")
    );
    expect(q.profile).toBe("international_stem");
    expect(q.stem_only).toBe(true);
    expect(q.limit).toBe(25);
    expect(q.max_net_price).toBe(15000);
  });

  it("falls back to defaults for invalid numbers and unknown profiles", () => {
    const q = parseSearchQuery(new URLSearchParams("limit=abc&offset=-1&profile=made_up"));
    expect(q.limit).toBe(DEFAULT_QUERY.limit);
    expect(q.offset).toBe(DEFAULT_QUERY.offset);
    expect(q.profile).toBe(DEFAULT_QUERY.profile);
  });

  it("treats stem_only=false as false", () => {
    expect(parseSearchQuery(new URLSearchParams("stem_only=false")).stem_only).toBe(false);
  });
});

describe("serializeSearchQuery", () => {
  it("writes the required params and omits the unset ones", () => {
    const params = serializeSearchQuery({ ...DEFAULT_QUERY, state: "CA" });
    expect(params.toString()).toBe("profile=first_generation&limit=10&offset=0&state=CA");
  });

  it("round-trips through parse", () => {
    const original = {
      ...DEFAULT_QUERY,
      profile: "international_stem" as const,
      q: "engineering",
      stem_only: true
    };
    expect(parseSearchQuery(serializeSearchQuery(original))).toEqual(original);
  });
});

describe("profileLabel", () => {
  it("returns the matching label and falls back to the raw key", () => {
    const options = [{ key: "first_generation", label: "First-generation student" }];
    expect(profileLabel("first_generation", options)).toBe("First-generation student");
    expect(profileLabel("made_up", options)).toBe("made_up");
  });
});