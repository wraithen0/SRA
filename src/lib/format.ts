const DATE_FORMAT = new Intl.DateTimeFormat("en-US", {
  year: "numeric",
  month: "short",
  day: "numeric",
  timeZone: "UTC"
});

const CURRENCY_FORMAT = new Intl.NumberFormat("en-US", {
  style: "currency",
  currency: "USD",
  maximumFractionDigits: 0
});

export function formatDate(iso: string | null): string {
  if (!iso) return "—";
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso;
  return DATE_FORMAT.format(date);
}

export function formatNetPrice(value: number | null): string {
  if (value === null || value === undefined) return "Not verified";
  return CURRENCY_FORMAT.format(value);
}

export function formatDaysLeft(days: number): string {
  if (days === 0) return "Today";
  if (days < 0) return `${Math.abs(days)} day${Math.abs(days) === 1 ? "" : "s"} ago`;
  return `${days} day${days === 1 ? "" : "s"} left`;
}

export function formatConfidence(value: number): string {
  return `${Math.round(value * 100)}% confidence`;
}