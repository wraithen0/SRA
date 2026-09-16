import { createContext, useContext, useMemo, type ReactNode } from "react";
import { profiles as fetchProfiles, topics as fetchTopics } from "./endpoints";
import type { ProfileOption, TopicOption } from "./types";
import { useApi } from "../hooks/useApi";

export function topicLabelFrom(topics: TopicOption[], key: string): string {
  return topics.find((topic) => topic.key === key)?.label ?? key;
}

interface VocabularyValue {
  profiles: ProfileOption[];
  topics: TopicOption[];
  topicLabel: (key: string) => string;
  loading: boolean;
}

const VocabularyContext = createContext<VocabularyValue>({
  profiles: [],
  topics: [],
  topicLabel: (key) => key,
  loading: true
});

export function VocabularyProvider({ children }: { children: ReactNode }) {
  const profilesState = useApi(() => fetchProfiles(), []);
  const topicsState = useApi(() => fetchTopics(), []);

  const value = useMemo<VocabularyValue>(() => {
    const profiles = profilesState.data?.profiles ?? [];
    const topics = topicsState.data?.topics ?? [];
    return {
      profiles,
      topics,
      topicLabel: (key: string) => topicLabelFrom(topics, key),
      loading: profilesState.loading || topicsState.loading
    };
  }, [profilesState.data, topicsState.data, profilesState.loading, topicsState.loading]);

  return <VocabularyContext.Provider value={value}>{children}</VocabularyContext.Provider>;
}

export function useVocabulary(): VocabularyValue {
  return useContext(VocabularyContext);
}