import { useVocabulary } from "../../api/VocabularyContext";
import type { ProfileKey } from "../../api/types";

const PROFILE_KEYS: ProfileKey[] = [
  "first_generation",
  "student_with_disability",
  "international_stem"
];

export function ProfileSelect({
  value,
  onChange,
  id = "profile"
}: {
  value: ProfileKey;
  onChange: (value: ProfileKey) => void;
  id?: string;
}) {
  const { profiles } = useVocabulary();

  return (
    <label className="field" htmlFor={id}>
      <span className="field__label">Profile</span>
      <select
        id={id}
        className="field__input"
        value={value}
        onChange={(event) => onChange(event.target.value as ProfileKey)}
      >
        {PROFILE_KEYS.map((key) => (
          <option key={key} value={key}>
            {profiles.find((profile) => profile.key === key)?.label ?? key}
          </option>
        ))}
      </select>
    </label>
  );
}