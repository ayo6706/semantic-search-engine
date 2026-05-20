export async function searchDocuments(params) {
  const res = await fetch('/api/v1/search', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(params),
  });
  if (!res.ok) throw new Error(`Search failed: ${res.status}`);
  return res.json();
}

export async function listDocuments() {
  const res = await fetch('/api/v1/documents');
  if (!res.ok) throw new Error(`Failed to fetch documents: ${res.status}`);
  return res.json();
}
