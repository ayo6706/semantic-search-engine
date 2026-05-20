import { useState, useRef, useEffect, useCallback } from 'react';
import { searchDocuments } from '../api/client';

export default function useSearch() {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);

  const [searchMode, setSearchMode] = useState('hybrid');
  const [useReranker, setUseReranker] = useState(true);
  const [selectedDocIds, setSelectedDocIds] = useState([]);
  const [scoreThreshold, setScoreThreshold] = useState(0);
  const [minPage, setMinPage] = useState(1);
  const [maxPage, setMaxPage] = useState(100);

  const debounceTimeout = useRef(null);
  const latestRequestRef = useRef(0);

  const executeSearch = useCallback(async (currentQuery, mode, reranker, docIds) => {
    if (!currentQuery.trim()) {
      setResults(null);
      setIsLoading(false);
      return;
    }

    const requestId = Date.now();
    latestRequestRef.current = requestId;

    setIsLoading(true);
    setError(null);

    try {
      const params = {
        query: currentQuery,
        top_k: 20, // get a bit more so client-side filtering works well
        use_reranker: reranker,
        search_mode: mode,
        ...(docIds.length > 0 ? { doc_ids: docIds } : {})
      };

      const response = await searchDocuments(params);
      
      // Only update if this is the latest request
      if (latestRequestRef.current === requestId) {
        setResults(response);
      }
    } catch (err) {
      if (latestRequestRef.current === requestId) {
        setError(err.message);
      }
    } finally {
      if (latestRequestRef.current === requestId) {
        setIsLoading(false);
      }
    }
  }, []);

  const prevFilters = useRef({ searchMode, useReranker, selectedDocIds });

  // Effect for debounced search when query changes
  useEffect(() => {
    if (debounceTimeout.current) clearTimeout(debounceTimeout.current);
    
    const filtersChanged = 
      prevFilters.current.searchMode !== searchMode ||
      prevFilters.current.useReranker !== useReranker ||
      prevFilters.current.selectedDocIds !== selectedDocIds;

    if (filtersChanged) {
      prevFilters.current = { searchMode, useReranker, selectedDocIds };
      executeSearch(query, searchMode, useReranker, selectedDocIds);
    } else {
      debounceTimeout.current = setTimeout(() => {
        executeSearch(query, searchMode, useReranker, selectedDocIds);
      }, 300);
    }

    return () => {
      if (debounceTimeout.current) clearTimeout(debounceTimeout.current);
    };
  }, [query, searchMode, useReranker, selectedDocIds, executeSearch]);

  const filteredResults = results?.results?.filter(r => 
    (r.score || 0) >= scoreThreshold &&
    r.page_num >= minPage &&
    r.page_num <= maxPage
  ) || [];

  return {
    query, setQuery,
    results, isLoading, error,
    searchMode, setSearchMode,
    useReranker, setUseReranker,
    selectedDocIds, setSelectedDocIds,
    scoreThreshold, setScoreThreshold,
    minPage, setMinPage,
    maxPage, setMaxPage,
    filteredResults,
    retry: () => executeSearch(query, searchMode, useReranker, selectedDocIds)
  };
}
