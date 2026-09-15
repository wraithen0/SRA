import { ArrowUpRight } from "lucide-react";
import { useVocabulary } from "../../api/VocabularyContext";

export function OfficialLinks({ links }: { links: Record<string, string> }) {
  const { topicLabel } = useVocabulary();
  const entries = Object.entries(links);

  if (entries.length === 0) return null;

  return (
    <section className="section" aria-labelledby="links-heading">
      <h2 className="section__title" id="links-heading">
        Official links
      </h2>
      <ul className="link-grid">
        {entries.map(([key, url]) => (
          <li key={key}>
            <a className="link-card" href={url} target="_blank" rel="noopener noreferrer">
              <span>{topicLabel(key)}</span>
              <ArrowUpRight size={20} aria-hidden="true" />
            </a>
          </li>
        ))}
      </ul>
    </section>
  );
}