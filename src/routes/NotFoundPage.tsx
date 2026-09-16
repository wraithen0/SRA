import { Link } from "react-router-dom";

export function NotFoundPage() {
  return (
    <div className="page">
      <div className="empty-state">
        <h1 className="page-title">That page does not exist.</h1>
        <Link to="/search">Back to search</Link>
      </div>
    </div>
  );
}