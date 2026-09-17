import type { ReactNode } from "react";
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

export const CONTROL_LABELS: Record<string, string> = {
  public: "Public",
  private_nonprofit: "Private nonprofit",
  private_forprofit: "Private for-profit"
};

export const LEVEL_LABELS: Record<string, string> = {
  "2-year": "2-year",
  "4-year": "4-year"
};

const CONTROLS = ["", ...Object.keys(CONTROL_LABELS)];
const LEVELS = ["", ...Object.keys(LEVEL_LABELS)];

export function FilterBar({
  values,
  onChange,
  actions
}: {
  values: FilterValues;
  onChange: (next: Partial<FilterValues>) => void;
  actions?: ReactNode;
}) {
  return (
    <div className="filter-bar">
      <div className="filter-field filter-field--profile">
        <ProfileSelect value={values.profile} onChange={(profile) => onChange({ profile })} />
      </div>

      <label className="field filter-field filter-field--state" htmlFor="state">
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

      <label className="field filter-field filter-field--control" htmlFor="control">
        <span className="field__label">Control</span>
        <select
          id="control"
          className="field__input"
          value={values.control}
          onChange={(event) => onChange({ control: event.target.value })}
        >
          {CONTROLS.map((value) => (
            <option key={value || "any"} value={value}>
              {value ? CONTROL_LABELS[value] ?? value.replace(/_/g, " ") : "Any"}
            </option>
          ))}
        </select>
      </label>

      <label className="field filter-field filter-field--level" htmlFor="level">
        <span className="field__label">Level</span>
        <select
          id="level"
          className="field__input"
          value={values.level}
          onChange={(event) => onChange({ level: event.target.value })}
        >
          {LEVELS.map((value) => (
            <option key={value || "any"} value={value}>
              {value ? LEVEL_LABELS[value] ?? value : "Any"}
            </option>
          ))}
        </select>
      </label>

      <label className="field filter-field filter-field--price" htmlFor="max_net_price">
        <span className="field__label">Max net price</span>
        <span className="field__prefix-wrap">
          <span className="field__prefix" aria-hidden="true">
            $
          </span>
          <input
            id="max_net_price"
            className="field__input field__input--prefixed"
            inputMode="numeric"
            value={values.maxNetPrice}
            placeholder="15000"
            onChange={(event) => onChange({ maxNetPrice: event.target.value.replace(/[^0-9]/g, "") })}
          />
        </span>
      </label>

      <label className="filter-field filter-field--stem toggle" htmlFor="stem_only">
        <input
          id="stem_only"
          type="checkbox"
          className="toggle__input"
          checked={values.stemOnly}
          onChange={(event) => onChange({ stemOnly: event.target.checked })}
        />
        <span className="toggle__track" aria-hidden="true">
          <span className="toggle__thumb" />
        </span>
        <span className="toggle__label">STEM only</span>
      </label>

      {actions ? <div className="filter-bar__actions">{actions}</div> : null}
    </div>
  );
}