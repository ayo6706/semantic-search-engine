import { useState } from 'react';
import './ResultCard.css';

export default function ResultCard({ result, index }) {
  const [showTooltip, setShowTooltip] = useState(false);

  const formatScore = (s) => (s !== undefined && s !== null ? s.toFixed(3) : null);

  const getScoreColor = (score) => {
    // 0 -> 0.5 -> 1.0 (Red -> Yellow -> Green)
    // using HSL: 0 is Red, 60 is Yellow, 120 is Green
    const hue = Math.max(0, Math.min(120, score * 120));
    return `hsl(${hue}, 80%, 50%)`;
  };

  const finalScore = result.score || 0;
  const scoreColor = getScoreColor(finalScore);

  return (
    <div 
      className="result-card" 
      style={{ animationDelay: `${index * 50}ms`, borderLeftColor: 'var(--accent)' }}
    >
      <div className="result-header">
        <div className="result-meta">
          <span className="filename">{result.doc_filename}</span>
          <span className="page-num">Page {result.page_num}</span>
        </div>
        
        <div 
          className="score-badge-container"
          onMouseEnter={() => setShowTooltip(true)}
          onMouseLeave={() => setShowTooltip(false)}
          onFocus={() => setShowTooltip(true)}
          onBlur={() => setShowTooltip(false)}
          onKeyDown={(e) => { if (e.key === 'Escape') setShowTooltip(false); }}
          tabIndex={0}
          role="button"
          aria-haspopup="true"
          aria-expanded={showTooltip}
          aria-label={`Score: ${(finalScore * 100).toFixed(1)}%. Click or focus to see score breakdown.`}
        >
          <div 
            className="score-badge mono" 
            style={{ color: scoreColor, borderColor: scoreColor }}
          >
            {(finalScore * 100).toFixed(1)}
          </div>
          
          {showTooltip && (
            <div className="score-tooltip">
              <div className="tooltip-row">
                <span>Final:</span>
                <span className="mono">{formatScore(result.score)}</span>
              </div>
              {result.dense_score != null && (
                <div className="tooltip-row">
                  <span>Dense:</span>
                  <span className="mono">{formatScore(result.dense_score)}</span>
                </div>
              )}
              {result.sparse_score != null && (
                <div className="tooltip-row">
                  <span>Sparse:</span>
                  <span className="mono">{formatScore(result.sparse_score)}</span>
                </div>
              )}
              {result.rerank_score != null && (
                <div className="tooltip-row">
                  <span>Rerank:</span>
                  <span className="mono">{formatScore(result.rerank_score)}</span>
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      <div 
        className="snippet-content" 
        dangerouslySetInnerHTML={{ __html: result.snippet || result.text }} 
      />
    </div>
  );
}
