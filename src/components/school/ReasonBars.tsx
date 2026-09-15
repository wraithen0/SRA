import type { Reason } from "../../api/types";
import { sortReasons } from "../../lib/sort";

export function ReasonBars({ reasons }: { reasons: Reason[] }) {
  if (reasons.length === 0) return null;

  return (
    <ul className="reason-bars">
      {sortReasons(reasons).map((reason) => (
        <li key={reason.signal} className="reason-bar">
          <span className="reason-bar__label">{reason.label}</span>
          <span
            className="reason-bar__track"
            role="meter"
            aria-valuenow={reason.weight}
            aria-valuemin={0}
            aria-valuemax={100}
            aria-label={`${reason.label} weight`}
          >
            <span
              className="reason-bar__fill"
              style={{ width: `${Math.round(reason.value * 100)}%` }}
            />
          </span>
          <span className="reason-bar__value">{reason.value.toFixed(2)}</span>
          <span className="reason-bar__weight">w{reason.weight}</span>
        </li>
      ))}
    </ul>
  );
}