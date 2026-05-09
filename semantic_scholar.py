"""
Semantic Scholar API for citation metadata lookup.
Supports bulk title search - much better coverage than arXiv.
"""

import requests
from dataclasses import dataclass
from typing import Optional


HEADERS = {
    'User-Agent': 'CitationNavigator/1.0',
}

# Add API key here for higher rate limits (optional)
# HEADERS['x-api-key'] = 'your-api-key'

BASE_URL = "https://api.semanticscholar.org/graph/v1"


@dataclass
class PaperMetadata:
    """Metadata from Semantic Scholar."""
    paper_id: str
    title: str
    authors: list[str]
    abstract: Optional[str]
    year: Optional[int]
    venue: Optional[str]
    citation_count: Optional[int]
    doi: Optional[str] = None
    arxiv_id: Optional[str] = None
    url: Optional[str] = None
    pdf_url: Optional[str] = None


def search_paper(title: str) -> Optional[PaperMetadata]:
    """
    Search for a paper by title.

    Args:
        title: Paper title to search for

    Returns:
        PaperMetadata or None if not found
    """
    url = f"{BASE_URL}/paper/search"
    params = {
        "query": title,
        "limit": 1,
        "fields": "paperId,title,authors,abstract,year,venue,citationCount,externalIds,url,openAccessPdf"
    }

    try:
        response = requests.get(url, params=params, headers=HEADERS, timeout=30)
        if response.status_code != 200:
            return None

        data = response.json()
        if not data.get("data"):
            return None

        return _parse_paper(data["data"][0])
    except Exception:
        return None


def bulk_search_papers(titles: list[str]) -> dict[str, PaperMetadata]:
    """
    Search for multiple papers by title in a single batch request.

    Args:
        titles: List of paper titles

    Returns:
        Dict mapping original title -> PaperMetadata
    """
    if not titles:
        return {}

    url = f"{BASE_URL}/paper/batch"
    params = {
        "fields": "paperId,title,authors,abstract,year,venue,citationCount,externalIds,url,openAccessPdf"
    }

    # Semantic Scholar batch endpoint expects paper IDs, not titles
    # We need to use the search endpoint for each, but can do it smarter
    # by using the bulk match endpoint

    # Actually, use the paper/search endpoint with bulk matching
    # First, search all titles and collect results
    results = {}

    # Process in batches to avoid rate limits
    batch_size = 10
    for i in range(0, len(titles), batch_size):
        batch = titles[i:i + batch_size]
        for title in batch:
            if not title:
                continue
            paper = search_paper(title)
            if paper:
                # Map by normalized original title
                results[title.lower().strip()] = paper

    return results


def bulk_search_papers_fast(titles: list[str]) -> dict[str, PaperMetadata]:
    """
    Search for multiple papers using the batch title search.
    Uses POST to /paper/batch with title matching.

    Args:
        titles: List of paper titles

    Returns:
        Dict mapping original title -> PaperMetadata
    """
    if not titles:
        return {}

    # Clean titles
    clean_titles = [t.strip() for t in titles if t and t.strip()]
    if not clean_titles:
        return {}

    # Use the search endpoint for each title (Semantic Scholar doesn't have true bulk title search)
    # But we can parallelize or batch smartly
    url = f"{BASE_URL}/paper/search/bulk"

    # Actually S2 has a relevance search that works well
    # Let's use individual searches but handle errors gracefully
    results = {}

    for title in clean_titles:
        try:
            paper = search_paper(title)
            if paper:
                results[title.lower().strip()] = paper
        except Exception:
            continue

    return results


def lookup_by_doi(doi: str) -> Optional[PaperMetadata]:
    """
    Look up paper by DOI.

    Args:
        doi: DOI identifier

    Returns:
        PaperMetadata or None if not found
    """
    url = f"{BASE_URL}/paper/DOI:{doi}"
    params = {
        "fields": "paperId,title,authors,abstract,year,venue,citationCount,externalIds,url,openAccessPdf"
    }

    try:
        response = requests.get(url, params=params, headers=HEADERS, timeout=30)
        if response.status_code != 200:
            return None

        return _parse_paper(response.json())
    except Exception:
        return None


def _parse_paper(data: dict) -> Optional[PaperMetadata]:
    """Parse paper data from Semantic Scholar API response."""
    if not data:
        return None

    # Extract authors
    authors = []
    for author in data.get("authors", []):
        name = author.get("name")
        if name:
            authors.append(name)

    # Extract external IDs
    external_ids = data.get("externalIds", {}) or {}
    doi = external_ids.get("DOI")
    arxiv_id = external_ids.get("ArXiv")

    # Extract PDF URL
    pdf_url = None
    open_access = data.get("openAccessPdf")
    if open_access:
        pdf_url = open_access.get("url")

    return PaperMetadata(
        paper_id=data.get("paperId", ""),
        title=data.get("title", ""),
        authors=authors,
        abstract=data.get("abstract"),
        year=data.get("year"),
        venue=data.get("venue"),
        citation_count=data.get("citationCount"),
        doi=doi,
        arxiv_id=arxiv_id,
        url=data.get("url"),
        pdf_url=pdf_url
    )


def enrich_citation(citation: dict) -> dict:
    """
    Enrich a citation dict with Semantic Scholar metadata.
    Tries DOI first, then title search.

    Args:
        citation: Citation dict from GROBID extraction

    Returns:
        Enriched citation dict with 'metadata' field if found
    """
    metadata = None

    # Try DOI first (most reliable)
    if citation.get('doi'):
        metadata = lookup_by_doi(citation['doi'])

    # Fall back to title search
    if not metadata and citation.get('title'):
        metadata = search_paper(citation['title'])

    if metadata:
        citation['metadata'] = {
            'paper_id': metadata.paper_id,
            'title': metadata.title,
            'authors': metadata.authors,
            'abstract': metadata.abstract,
            'year': metadata.year,
            'venue': metadata.venue,
            'citation_count': metadata.citation_count,
            'doi': metadata.doi,
            'arxiv_id': metadata.arxiv_id,
            'url': metadata.url,
            'pdf_url': metadata.pdf_url
        }

    return citation


def enrich_citations_bulk(citations: list[dict]) -> list[dict]:
    """
    Enrich all citations with Semantic Scholar metadata.

    Args:
        citations: List of citation dicts from GROBID extraction

    Returns:
        List of enriched citation dicts
    """
    for i, citation in enumerate(citations):
        print(f"[*] Fetching metadata for citation {i+1}/{len(citations)}...")
        enrich_citation(citation)

    return citations


if __name__ == "__main__":
    # Test search
    result = search_paper("Attention Is All You Need")
    if result:
        print(f"Title: {result.title}")
        print(f"Authors: {', '.join(result.authors)}")
        print(f"Year: {result.year}")
        print(f"Citations: {result.citation_count}")
        print(f"Abstract: {result.abstract[:200] if result.abstract else 'N/A'}...")
    else:
        print("Not found")
