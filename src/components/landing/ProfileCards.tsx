import { Link } from "react-router-dom";
import { Accessibility, Building2, Globe } from "lucide-react";
import { useVocabulary } from "../../api/VocabularyContext";
import { profileLabel } from "../../lib/url";
import type { ProfileKey } from "../../api/types";

const ICONS: Record<ProfileKey, typeof Building2> = {
  first_generation: Building2,
  student_with_disability: Accessibility,
  international_stem: Globe
};

const NEEDS: Record<ProfileKey, string> = {
  first_generation:
    "Net price estimates · Institutional grants · Application-fee waivers · FAFSA codes & dates · TRIO and mentorship programs",
  student_with_disability:
    "Disability services office · Accommodation processes · Assistive-tech funding · State vocational rehabilitation",
  international_stem:
    "Need-based institutional aid · Tuition waivers · Graduate funding (RA/TA) · CSS Profile · CPT/OPT guidance"
};

const KEYS: ProfileKey[] = [
  "first_generation",
  "student_with_disability",
  "international_stem"
];

export function ProfileCards() {
  const { profiles } = useVocabulary();
  const label = (key: ProfileKey) => profileLabel(key, profiles);

  return (
    <ul className="profile-cards reveal">
      {KEYS.map((key) => {
        const Icon = ICONS[key];
        return (
          <li key={key} className="profile-card">
            <Icon size={24} aria-hidden="true" className="profile-card__icon" />
            <h3 className="profile-card__name">{label(key)}</h3>
            <p className="profile-card__needs">{NEEDS[key]}</p>
            <Link className="profile-card__cta" to={`/search?profile=${key}`}>
              Search for {label(key)}
            </Link>
          </li>
        );
      })}
    </ul>
  );
}
