import { X } from "lucide-react";
import { formatNetPrice } from "../../lib/format";
import { CONTROL_LABELS, LEVEL_LABELS, type FilterValues } from "./FilterBar";

interface Chip {
  key: string;
  label: string;
  clear: Partial<FilterValues> & { q?: string };
}

export function ActiveFilters({
  q,
  values,
  onChange
}: {
  q?: string;
  values: FilterValues;
  onChange: (patch: Partial<FilterValues> & { q?: string }) => void;
}) {
  const chips: Chip[] = [];

  if (q) chips.push({ key: "q", label: `"${q}"`, clear: { q: undefined } });
  if (values.state) {
    chips.push({ key: "state", label: values.state.toUpperCase(), clear: { state: "" } });
  }
  if (values.control) {
    chips.push({
      key: "control",
      label: CONTROL_LABELS[values.control] ?? values.control,
      clear: { control: "" }
    });
  }
  if (values.level) {
    chips.push({
      key: "level",
      label: LEVEL_LABELS[values.level] ?? values.level,
      clear: { level: "" }
    });
  }
  if (values.stemOnly) chips.push({ key: "stem", label: "STEM only", clear: { stemOnly: false } });
  if (values.maxNetPrice) {
    const amount = Number(values.maxNetPrice);
    chips.push({
      key: "price",
      label: `Net price ≤ ${formatNetPrice(Number.isFinite(amount) ? amount : 0)}`,
      clear: { maxNetPrice: "" }
    });
  }

  if (chips.length === 0) return null;

  return (
    <div className="active-filters">
      <div className="active-filters__bar">
        <p className="active-filters__heading">
          {chips.length} {chips.length === 1 ? "filter" : "filters"} applied
        </p>
        <button
          type="button"
          className="active-filters__clear"
          onClick={() => onChange({ q: undefined, state: "", control: "", level: "", stemOnly: false, maxNetPrice: "" })}
        >
          Clear all
        </button>
      </div>
      <ul className="filter-chips">
        {chips.map((chip) => (
          <li key={chip.key} className="filter-chip">
            <span className="filter-chip__label">{chip.label}</span>
            <button
              type="button"
              className="filter-chip__remove"
              aria-label={`Remove ${chip.label}`}
              title={`Remove ${chip.label}`}
              onClick={() => onChange(chip.clear)}
            >
              <X size={14} aria-hidden="true" />
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}