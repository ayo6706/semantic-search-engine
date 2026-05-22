import { useState, useRef, useEffect, useCallback } from 'react';
import { searchDocuments } from '../api/client';

export default function useSearch() {
  const [query, setQueryValue] = useState('');
  const [results, setResults] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);

  const [searchMode, setSearchMode] = useState('hybrid');
  const [useReranker, setUseReranker] = useState(true);
  const [selectedDocIds, setSelectedDocIds] = useState([]);
  const [scoreThreshold, setScoreThreshold] = useState(0);
  const [minPage, setMinPage] = useState(1);
  const [maxPage, setMaxPage] = useState(100);

  const abortControllerRef = useRef(null);
  const searchSessionId = useRef(
    globalThis.crypto?.randomUUID?.() ?? `${Date.now()}-${Math.random()}`
  );
  const searchRequestId = useRef(0);
  const submittedQueryRef = useRef('');

  const setQuery = useCallback((value) => {
    setQueryValue(value);
    if (!value.trim()) {
      submittedQueryRef.current = '';
      abortControllerRef.current?.abort();
      setResults(null);
      setError(null);
      setIsLoading(false);
    }
  }, []);

  const executeSearch = useCallback(async (currentQuery, mode, reranker, docIds) => {
    if (!currentQuery.trim()) {
      setResults(null);
      setIsLoading(false);
      return;
    }

    // Cancel any in-flight request so the backend stops processing stale work.
    abortControllerRef.current?.abort();
    const controller = new AbortController();
    abortControllerRef.current = controller;
    const requestId = searchRequestId.current + 1;
    searchRequestId.current = requestId;

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

      const response = await searchDocuments(params, {
        signal: controller.signal,
        searchSessionId: searchSessionId.current,
        searchRequestId: requestId,
      });

      if (!controller.signal.aborted) {
        setResults(response);
      }
    } catch (err) {
      if (controller.signal.aborted) return;
      setError(err.message);
    } finally {
      if (!controller.signal.aborted) {
        setIsLoading(false);
      }
    }
  }, []);

  const submitSearch = useCallback(() => {
    const submittedQuery = query.trim();
    submittedQueryRef.current = submittedQuery;
    executeSearch(submittedQuery, searchMode, useReranker, selectedDocIds);
  }, [query, searchMode, useReranker, selectedDocIds, executeSearch]);

  useEffect(() => {
    if (submittedQueryRef.current) {
      executeSearch(
        submittedQueryRef.current,
        searchMode,
        useReranker,
        selectedDocIds
      );
    }
  }, [searchMode, useReranker, selectedDocIds, executeSearch]);

  // Cancel in-flight request on unmount.
  useEffect(() => {
    return () => abortControllerRef.current?.abort();
  }, []);

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
    submitSearch,
    retry: () => executeSearch(
      submittedQueryRef.current || query,
      searchMode,
      useReranker,
      selectedDocIds
    )
  };
}
