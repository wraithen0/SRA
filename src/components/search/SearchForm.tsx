import { Search, X } from "lucide-react";

export function SearchForm({
  value,
  onChange,
  onClear
}: {
  value: string;
  onChange: (value: string) => void;
  onClear: () => void;
}) {
  return (
    <div className="search-form">
      <label className="field field--grow" htmlFor="q">
        <span className="field__label">School name or keyword</span>
        <span className="field__with-icon">
          <Search size={22} aria-hidden="true" />
          <input
            id="q"
            className="field__input search-form__input"
            type="search"
            value={value}
            placeholder="Stanford"
            onChange={(event) => onChange(event.target.value)}
          />
          {value ? (
            <button
              type="button"
              className="search-form__clear"
              aria-label="Clear search"
              onClick={onClear}
            >
              <X size={16} aria-hidden="true" />
            </button>
          ) : null}
        </span>
      </label>
    </div>
  );
}