"""
OpenAlex API for citation metadata lookup.
Better abstract coverage than Semantic Scholar.
"""

import os
import requests
from dataclasses import dataclass
from typing import Optional


HEADERS = {
    'User-Agent': 'CitationNavigator/1.0',
}

# Add API key for higher rate limits (optional)
# Get one at https://openalex.org/users/me
API_KEY = os.environ.get('OPENALEX_API_KEY')
if API_KEY:
    HEADERS['api_key'] = API_KEY

BASE_URL = "https://api.openalex.org"


@dataclass
class PaperMetadata:
    """Metadata from OpenAlex."""
    paper_id: str
    title: str
    authors: list[str]
    abstract: Optional[str]
    year: Optional[int]
    venue: Optional[str]
    citation_count: Optional[int]
    doi: Optional[str] = None
    url: Optional[str] = None
    pdf_url: Optional[str] = None


def _reconstruct_abstract(inverted_index: dict) -> Optional[str]:
    """Reconstruct abstract from OpenAlex inverted index format."""
    if not inverted_index:
        return None
    words = {}
    for word, positions in inverted_index.items():
        for pos in positions:
            words[pos] = word
    return ' '.join(words[i] for i in sorted(words.keys()))


def search_paper(title: str) -> Optional[PaperMetadata]:
    """
    Search for a paper by title.

    Args:
        title: Paper title to search for

    Returns:
        PaperMetadata or None if not found
    """
    url = f"{BASE_URL}/works"
    params = {
        "search": title,
        "per_page": 1,
        "select": "id,title,authorships,abstract_inverted_index,publication_year,primary_location,cited_by_count,doi"
    }

    try:
        response = requests.get(url, params=params, headers=HEADERS, timeout=30)
        if response.status_code != 200:
            return None

        data = response.json()
        results = data.get("results", [])
        if not results:
            return None

        return _parse_paper(results[0])
    except Exception:
        return None


def lookup_by_doi(doi: str) -> Optional[PaperMetadata]:
    """
    Look up paper by DOI.

    Args:
        doi: DOI identifier

    Returns:
        PaperMetadata or None if not found
    """
    url = f"{BASE_URL}/works/doi:{doi}"
    params = {
        "select": "id,title,authorships,abstract_inverted_index,publication_year,primary_location,cited_by_count,doi"
    }

    try:
        response = requests.get(url, params=params, headers=HEADERS, timeout=30)
        if response.status_code != 200:
            return None

        return _parse_paper(response.json())
    except Exception:
        return None


def _parse_paper(data: dict) -> Optional[PaperMetadata]:
    """Parse paper data from OpenAlex API response."""
    if not data:
        return None

    # Extract authors
    authors = []
    for authorship in data.get("authorships", []):
        author = authorship.get("author", {})
        name = author.get("display_name")
        if name:
            authors.append(name)

    # Reconstruct abstract from inverted index
    abstract = _reconstruct_abstract(data.get("abstract_inverted_index"))

    # Extract venue
    venue = None
    primary_location = data.get("primary_location") or {}
    source = primary_location.get("source") or {}
    venue = source.get("display_name")

    # Extract PDF URL
    pdf_url = primary_location.get("pdf_url")

    # Extract DOI (remove https://doi.org/ prefix if present)
    doi = data.get("doi")
    if doi and doi.startswith("https://doi.org/"):
        doi = doi[16:]

    return PaperMetadata(
        paper_id=data.get("id", ""),
        title=data.get("title", ""),
        authors=authors,
        abstract=abstract,
        year=data.get("publication_year"),
        venue=venue,
        citation_count=data.get("cited_by_count"),
        doi=doi,
        url=data.get("id"),  # OpenAlex ID is the URL
        pdf_url=pdf_url
    )


def enrich_citation(citation: dict) -> dict:
    """
    Enrich a citation dict with OpenAlex metadata.
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
            'url': metadata.url,
            'pdf_url': metadata.pdf_url
        }

    return citation


def enrich_citations_bulk(citations: list[dict]) -> list[dict]:
    """
    Enrich all citations with OpenAlex metadata.

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
