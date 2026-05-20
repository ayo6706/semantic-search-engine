import './AnalyticsBar.css';

export default function AnalyticsBar({ response }) {
  if (!response) return null;

  const { latency_ms, total_results, search_mode, reranker_used, results = [] } = response;

  const getLatencyColor = (ms) => {
    if (ms < 200) return 'var(--success)';
    if (ms < 500) return 'var(--warning)';
    return 'var(--danger)';
  };

  const getScoreColor = (score) => {
    const hue = Math.max(0, Math.min(120, score * 120));
    return `hsl(${hue}, 80%, 50%)`;
  };

  const barWidth = 8;
  const gap = 2;
  const maxHeight = 32;

  return (
    <div className="analytics-bar">
      <div className="analytics-stats">
        <div className="stat-pill">
          <span className="stat-label">Results</span>
          <span className="stat-value mono">{total_results}</span>
        </div>
        
        <div className="stat-pill">
          <span className="stat-label">Latency</span>
          <span 
            className="stat-value mono"
            style={{ color: getLatencyColor(latency_ms) }}
          >
            {latency_ms?.toFixed(0)}ms
          </span>
        </div>

        <div className="stat-pill">
          <span className="stat-label">Mode</span>
          <span className="stat-value badge">{search_mode}</span>
        </div>

        {reranker_used ? (
          <div className="stat-pill">
            <span className="stat-value badge rerank-badge">Reranked</span>
          </div>
        ) : (
          <div className="stat-pill">
            <span className="stat-label">Reranker</span>
            <span className="stat-value badge">Off</span>
          </div>
        )}
      </div>

      {results.length > 0 && (
        <div className="analytics-chart">
          <span className="chart-label">Score Dist</span>
          <svg 
            width={(barWidth + gap) * results.length} 
            height={maxHeight} 
            className="score-svg"
            role="img"
            aria-label={`Score distribution for ${results.length} search results`}
          >
            {results.map((r, i) => {
              const finalScore = r.score || 0;
              const h = Math.max(2, finalScore * maxHeight);
              return (
                <rect
                  key={i}
                  x={i * (barWidth + gap)}
                  y={maxHeight - h}
                  width={barWidth}
                  height={h}
                  fill={getScoreColor(finalScore)}
                  rx={2}
                  className="chart-bar"
                  style={{ animationDelay: `${i * 30}ms` }}
                />
              );
            })}
          </svg>
        </div>
      )}
    </div>
  );
}
