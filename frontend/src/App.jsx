import { useEffect, useState } from 'react';
import SearchBar from './components/SearchBar';
import FacetPanel from './components/FacetPanel';
import AnalyticsBar from './components/AnalyticsBar';
import ResultCard from './components/ResultCard';
import useSearch from './hooks/useSearch';
import { listDocuments } from './api/client';
import './App.css';

function App() {
  const [documents, setDocuments] = useState([]);
  
  const {
    query, setQuery,
    results, isLoading, error,
    searchMode, setSearchMode,
    useReranker, setUseReranker,
    selectedDocIds, setSelectedDocIds,
    scoreThreshold, setScoreThreshold,
    minPage, setMinPage,
    maxPage, setMaxPage,
    filteredResults,
    retry
  } = useSearch();

  useEffect(() => {
    listDocuments()
      .then(data => {
        if (data && data.items) {
          setDocuments(data.items);
        }
      })
      .catch(err => console.error("Failed to load documents:", err));
  }, []);

  return (
    <div className="app-container">
      <a href="#main-content" className="skip-link">Skip to main content</a>
      <h1 className="sr-only">Semantic Search Engine</h1>
      
      <FacetPanel
        documents={documents}
        selectedDocIds={selectedDocIds}
        onDocIdsChange={setSelectedDocIds}
        searchMode={searchMode}
        onSearchModeChange={setSearchMode}
        useReranker={useReranker}
        onRerankerChange={setUseReranker}
        scoreThreshold={scoreThreshold}
        onScoreThresholdChange={setScoreThreshold}
        minPage={minPage}
        onMinPageChange={setMinPage}
        maxPage={maxPage}
        onMaxPageChange={setMaxPage}
      />
      
      <main id="main-content" className="main-content" tabIndex="-1">
        <div className="search-header">
          <SearchBar
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            isLoading={isLoading}
            resultCount={results ? filteredResults.length : null}
          />
        </div>

        {error && (
          <div className="error-message">
            <p>{error}</p>
            <button onClick={retry}>Retry</button>
          </div>
        )}

        <div className="results-area">
          {results && (
            <AnalyticsBar 
              response={{...results, total_results: filteredResults.length, results: filteredResults}} 
            />
          )}

          {results && filteredResults.length === 0 && !isLoading && !error && (
            <div className="empty-state">
              <p>No results found for your query or current filters.</p>
              <button onClick={() => setScoreThreshold(0)}>Clear Score Filter</button>
            </div>
          )}

          {!results && !query && !isLoading && (
            <div className="empty-state initial">
              <h2>Semantic Search Engine</h2>
              <p>Start typing to search across all indexed documents.</p>
              <kbd className="mono">/</kbd> <span>to focus</span>
            </div>
          )}

          <div className="results-list">
            {filteredResults.map((res, index) => (
              <ResultCard key={res.chunk_id || index} result={res} index={index} />
            ))}
          </div>
        </div>
      </main>
    </div>
  );
}

export default App;
