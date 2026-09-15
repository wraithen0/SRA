import { AlertTriangle } from "lucide-react";

export function ErrorBox({ error }: { error: Error | null }) {
  if (!error) return null;
  return (
    <div className="error-box" role="alert">
      <AlertTriangle size={20} aria-hidden="true" />
      <span>{error.message || "Request failed."}</span>
    </div>
  );
}