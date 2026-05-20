import { useState } from 'react';
import './FacetPanel.css';

export default function FacetPanel({
  documents = [],
  selectedDocIds,
  onDocIdsChange,
  searchMode,
  onSearchModeChange,
  useReranker,
  onRerankerChange,
  scoreThreshold,
  onScoreThresholdChange,
  minPage,
  onMinPageChange,
  maxPage,
  onMaxPageChange,
}) {
  const [isOpen, setIsOpen] = useState(false);

  const handleDocToggle = (docId) => {
    if (selectedDocIds.includes(docId)) {
      onDocIdsChange(selectedDocIds.filter(id => id !== docId));
    } else {
      onDocIdsChange([...selectedDocIds, docId]);
    }
  };

  const readyDocs = documents.filter(doc => doc.status === 'ready');

  return (
    <>
      <button className="mobile-toggle" onClick={() => setIsOpen(!isOpen)} aria-label="Toggle Filters">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{width: 20, height: 20}} aria-hidden="true">
          <polygon points="22 3 2 3 10 12.46 10 19 14 21 14 12.46 22 3"></polygon>
        </svg>
      </button>
      
      <div className={`facet-panel ${isOpen ? 'open' : ''}`}>
        <div className="facet-section">
          <h3>Search Mode</h3>
          <div className="radio-group">
            {['hybrid', 'dense', 'sparse'].map((mode) => (
              <label key={mode} className="radio-label">
                <input
                  type="radio"
                  name="searchMode"
                  value={mode}
                  checked={searchMode === mode}
                  onChange={(e) => onSearchModeChange(e.target.value)}
                />
                <span className="radio-custom"></span>
                <span className="mode-name">{mode.charAt(0).toUpperCase() + mode.slice(1)}</span>
              </label>
            ))}
          </div>
        </div>

        <div className="facet-section">
          <h3>Advanced</h3>
          <label className="checkbox-label">
            <input
              type="checkbox"
              checked={useReranker}
              onChange={(e) => onRerankerChange(e.target.checked)}
            />
            <span className="checkbox-custom"></span>
            Use Reranker
          </label>
        </div>

        <div className="facet-section">
          <div className="flex-between">
            <h3>Score Threshold</h3>
            <span className="mono threshold-value">{scoreThreshold.toFixed(2)}</span>
          </div>
          <input
            type="range"
            className="slider-custom"
            min="0"
            max="1"
            step="0.05"
            value={scoreThreshold}
            onChange={(e) => onScoreThresholdChange(parseFloat(e.target.value))}
            aria-label="Score threshold filter"
          />
        </div>

        <div className="facet-section">
          <div className="flex-between">
            <h3>Page Range</h3>
          </div>
          <div className="page-range-inputs">
            <input
              type="number"
              className="page-input"
              min="1"
              value={minPage}
              onChange={(e) => onMinPageChange(Math.max(1, parseInt(e.target.value) || 1))}
              placeholder="Min"
              aria-label="Minimum page number"
            />
            <span> - </span>
            <input
              type="number"
              className="page-input"
              min="1"
              value={maxPage}
              onChange={(e) => onMaxPageChange(Math.max(1, parseInt(e.target.value) || 100))}
              placeholder="Max"
              aria-label="Maximum page number"
            />
          </div>
        </div>

        <div className="facet-section">
          <h3>Documents</h3>
          {readyDocs.length === 0 ? (
            <p className="no-docs">No ready documents found.</p>
          ) : (
            <div className="doc-list">
              {readyDocs.map(doc => (
                <label key={doc.id} className="checkbox-label" title={doc.filename}>
                  <input
                    type="checkbox"
                    checked={selectedDocIds.includes(doc.id)}
                    onChange={() => handleDocToggle(doc.id)}
                  />
                  <span className="checkbox-custom"></span>
                  <span className="doc-filename">{doc.filename}</span>
                </label>
              ))}
            </div>
          )}
        </div>
      </div>
      
      {isOpen && <div className="mobile-overlay" onClick={() => setIsOpen(false)}></div>}
    </>
  );
}
