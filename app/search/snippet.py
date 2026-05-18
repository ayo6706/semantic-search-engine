import re


def _fallback_split_sentences(text: str) -> list[str]:
    return [
        sentence.strip()
        for sentence in re.split(r"(?<=[.!?])\s+", text)
        if sentence.strip()
    ]


def _split_sentences(text: str) -> list[str]:
    """Split text with NLTK when available, falling back to a simple splitter."""
    try:
        from nltk import download
        from nltk.data import find
        from nltk.tokenize import sent_tokenize
    except ImportError:
        return _fallback_split_sentences(text)

    try:
        find("tokenizers/punkt_tab")
    except LookupError:
        try:
            download("punkt_tab", quiet=True)
            find("tokenizers/punkt_tab")
        except (LookupError, OSError):
            try:
                find("tokenizers/punkt")
            except LookupError:
                try:
                    download("punkt", quiet=True)
                except (LookupError, OSError):
                    return _fallback_split_sentences(text)

    try:
        return [sentence.strip() for sentence in sent_tokenize(text) if sentence.strip()]
    except (LookupError, OSError):
        return _fallback_split_sentences(text)


def extract_snippet(text: str, query: str, max_sentences: int = 3) -> str:
    """Extract the most relevant snippet from text based on query terms.

    Finds the sentence window, up to max_sentences, with the highest overlap
    of query terms and wraps matching terms in <mark> tags.
    """
    if not text or not query:
        return text[:200] + "..." if len(text) > 200 else text

    query_terms = set(re.findall(r"\b\w+\b", query.lower()))

    if not query_terms:
        return text[:200] + "..." if len(text) > 200 else text

    max_sentences = max(1, max_sentences)

    sentences = _split_sentences(text)

    if not sentences:
        return text[:200] + "..." if len(text) > 200 else text

    if len(sentences) <= max_sentences:
        best_window = sentences
        start_idx = 0
        end_idx = len(sentences) - 1
    else:
        best_score = -1
        best_window = []
        start_idx = 0
        end_idx = 0

        min_window_size = min(2, max_sentences)
        for window_size in range(min_window_size, max_sentences + 1):
            for i in range(len(sentences) - window_size + 1):
                window = sentences[i:i + window_size]
                window_words = set(
                    re.findall(r"\b\w+\b", " ".join(window).lower())
                )

                score = len(query_terms & window_words)

                if score > best_score:
                    best_score = score
                    best_window = window
                    start_idx = i
                    end_idx = i + window_size - 1

        if best_score == 0:
            best_window = sentences[:max_sentences]
            start_idx = 0
            end_idx = len(best_window) - 1

    snippet = " ".join(best_window)

    # Sort descending to prevent shorter terms from overriding longer partial matches
    sorted_terms = sorted(query_terms, key=len, reverse=True)
    terms_pattern = "|".join(re.escape(term) for term in sorted_terms)
    pattern = re.compile(rf"\b({terms_pattern})\b", flags=re.IGNORECASE)
    snippet = pattern.sub(r"<mark>\1</mark>", snippet)

    if start_idx > 0:
        snippet = "... " + snippet
    if end_idx < len(sentences) - 1:
        snippet = snippet + " ..."

    return snippet
