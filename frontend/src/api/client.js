export async function searchDocuments(params, { signal, searchSessionId, searchRequestId } = {}) {
  const headers = { 'Content-Type': 'application/json' };
  if (searchSessionId) headers['X-Search-Session-Id'] = searchSessionId;
  if (searchRequestId != null) headers['X-Search-Request-Id'] = String(searchRequestId);

  const res = await fetch('/api/v1/search', {
    method: 'POST',
    headers,
    body: JSON.stringify(params),
    signal,
  });
  if (!res.ok) throw new Error(`Search failed: ${res.status}`);
  return res.json();
}

export async function listDocuments() {
  const res = await fetch('/api/v1/documents');
  if (!res.ok) throw new Error(`Failed to fetch documents: ${res.status}`);
  return res.json();
}
