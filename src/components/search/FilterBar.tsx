import type { ProfileKey } from "../../api/types";
import { ProfileSelect } from "../layout/ProfileSelect";

export interface FilterValues {
  profile: ProfileKey;
  state: string;
  control: string;
  level: string;
  stemOnly: boolean;
  maxNetPrice: string;
}

const CONTROLS = ["", "public", "private_nonprofit", "private_forprofit"];
const LEVELS = ["", "2-year", "4-year"];

export function FilterBar({
  values,
  onChange
}: {
  values: FilterValues;
  onChange: (next: Partial<FilterValues>) => void;
}) {
  return (
    <div className="filter-bar">
      <ProfileSelect value={values.profile} onChange={(profile) => onChange({ profile })} />

      <label className="field" htmlFor="state">
        <span className="field__label">State</span>
        <input
          id="state"
          className="field__input"
          value={values.state}
          maxLength={2}
          placeholder="CA"
          onChange={(event) => onChange({ state: event.target.value.toUpperCase() })}
        />
      </label>

      <label className="field" htmlFor="control">
        <span className="field__label">Control</span>
        <select
          id="control"
          className="field__input"
          value={values.control}
          onChange={(event) => onChange({ control: event.target.value })}
        >
          {CONTROLS.map((value) => (
            <option key={value || "any"} value={value}>
              {value ? value.replace(/_/g, " ") : "Any"}
            </option>
          ))}
        </select>
      </label>

      <label className="field" htmlFor="level">
        <span className="field__label">Level</span>
        <select
          id="level"
          className="field__input"
          value={values.level}
          onChange={(event) => onChange({ level: event.target.value })}
        >
          {LEVELS.map((value) => (
            <option key={value || "any"} value={value}>
              {value || "Any"}
            </option>
          ))}
        </select>
      </label>

      <label className="field" htmlFor="max_net_price">
        <span className="field__label">Max net price</span>
        <input
          id="max_net_price"
          className="field__input"
          inputMode="numeric"
          value={values.maxNetPrice}
          placeholder="15000"
          onChange={(event) => onChange({ maxNetPrice: event.target.value.replace(/[^0-9]/g, "") })}
        />
      </label>

      <label className="field field--check" htmlFor="stem_only">
        <input
          id="stem_only"
          type="checkbox"
          checked={values.stemOnly}
          onChange={(event) => onChange({ stemOnly: event.target.checked })}
        />
        <span className="field__label">STEM only</span>
      </label>
    </div>
  );
}