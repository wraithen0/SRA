import { formatConfidence } from "../../lib/format";

export function Confidence({ value }: { value: number }) {
  return <span className="confidence">{formatConfidence(value)}</span>;
}