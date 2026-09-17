import { useEffect, useState } from "react";
import { Search, X } from "lucide-react";
import { useDebouncedValue } from "../../hooks/useDebouncedValue";

export function SearchForm({ value, onChange }: { value: string; onChange: (value: string) => void }) {
  const [draft, setDraft] = useState(value);
  const debounced = useDebouncedValue(draft, 300);

  useEffect(() => {
    setDraft(value);
  }, [value]);

  useEffect(() => {
    if (debounced !== value) onChange(debounced);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [debounced]);

  const clear = () => {
    setDraft("");
    onChange("");
  };

  return (
    <form className="search-form" role="search" onSubmit={(event) => event.preventDefault()}>
      <label className="field field--grow" htmlFor="q">
        <span className="field__label">School name or keyword</span>
        <span className="field__with-icon">
          <Search size={22} aria-hidden="true" />
          <input
            id="q"
            className="field__input search-form__input"
            type="search"
            value={draft}
            placeholder="Stanford"
            onChange={(event) => setDraft(event.target.value)}
          />
          {draft ? (
            <button
              type="button"
              className="search-form__clear"
              aria-label="Clear search"
              onClick={clear}
            >
              <X size={16} aria-hidden="true" />
            </button>
          ) : null}
        </span>
      </label>
    </form>
  );
}