export function ResultSkeleton({ count = 3 }: { count?: number }) {
  return (
    <div className="result-skeleton" role="status" aria-label="Ranking schools">
      {Array.from({ length: count }, (_, index) => (
        <div className="result-skeleton__card" key={index}>
          <div className="result-skeleton__line result-skeleton__line--title" />
          <div className="result-skeleton__line result-skeleton__line--meta" />
          <div className="result-skeleton__bars">
            <div className="result-skeleton__bar" />
            <div className="result-skeleton__bar" />
          </div>
          <div className="result-skeleton__line result-skeleton__line--short" />
        </div>
      ))}
    </div>
  );
}