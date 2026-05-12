"""
Citation extraction using GROBID service.
GROBID parses PDF documents and extracts structured bibliographic data.
"""

import requests
import time
from dataclasses import dataclass
from typing import Optional
import xml.etree.ElementTree as ET


# GROBID TEI XML namespace
TEI_NS = {'tei': 'http://www.tei-c.org/ns/1.0'}


@dataclass
class Citation:
    """Represents an extracted citation."""
    id: str
    title: Optional[str] = None
    authors: list[str] = None
    year: Optional[str] = None
    journal: Optional[str] = None
    volume: Optional[str] = None
    pages: Optional[str] = None
    doi: Optional[str] = None
    arxiv_id: Optional[str] = None
    raw_text: Optional[str] = None

    def __post_init__(self):
        if self.authors is None:
            self.authors = []


class GrobidClient:
    """Client for interacting with GROBID service."""

    def __init__(self, grobid_url: str = "http://localhost:8070"):
        self.grobid_url = grobid_url.rstrip('/')

    def is_alive(self) -> bool:
        """Check if GROBID service is running."""
        print(f"[*] Checking GROBID at {self.grobid_url}...")
        try:
            response = requests.get(f"{self.grobid_url}/api/isalive", timeout=5)
            print(f"[*] GROBID responded: {response.status_code}")
            return response.status_code == 200
        except requests.RequestException as e:
            print(f"[*] GROBID connection failed: {e}")
            return False

    def process_pdf(self, pdf_path: str) -> str:
        """
        Process a PDF and return TEI XML with full document structure.

        Args:
            pdf_path: Path to the PDF file

        Returns:
            TEI XML string containing parsed document
        """
        url = f"{self.grobid_url}/api/processFulltextDocument"
        print(f"[*] Sending PDF to GROBID...")

        with open(pdf_path, 'rb') as pdf_file:
            files = {'input': pdf_file}
            params = {
                'consolidateCitations': '1',  # Consolidate with external APIs
                'includeRawCitations': '1',   # Include raw citation strings
            }
            response = requests.post(url, files=files, data=params, timeout=300)

        print(f"[*] GROBID processing complete: {response.status_code}")
        if response.status_code != 200:
            raise Exception(f"GROBID error: {response.status_code} - {response.text}")

        return response.text

    def process_references_only(self, pdf_path: str) -> str:
        """
        Process only the references section of a PDF.
        Faster than full document processing.

        Args:
            pdf_path: Path to the PDF file

        Returns:
            TEI XML string containing parsed references
        """
        url = f"{self.grobid_url}/api/processReferences"

        with open(pdf_path, 'rb') as pdf_file:
            files = {'input': pdf_file}
            params = {'consolidateCitations': '1'}
            response = requests.post(url, files=files, data=params, timeout=60)

        if response.status_code != 200:
            raise Exception(f"GROBID error: {response.status_code} - {response.text}")

        return response.text


def parse_citations_from_tei(tei_xml: str) -> list[Citation]:
    """
    Parse citations from GROBID TEI XML output.

    Args:
        tei_xml: TEI XML string from GROBID

    Returns:
        List of Citation objects
    """
    root = ET.fromstring(tei_xml)
    citations = []

    # Find all bibliographic entries in the back matter
    for bibl in root.findall('.//tei:listBibl/tei:biblStruct', TEI_NS):
        citation = _parse_bibl_struct(bibl)
        if citation:
            citations.append(citation)

    return citations


def _parse_bibl_struct(bibl: ET.Element) -> Optional[Citation]:
    """Parse a single biblStruct element into a Citation object."""

    # Get citation ID
    cite_id = bibl.get('{http://www.w3.org/XML/1998/namespace}id', '')

    # Parse title
    title = None
    title_elem = bibl.find('.//tei:analytic/tei:title', TEI_NS)
    if title_elem is None:
        title_elem = bibl.find('.//tei:monogr/tei:title', TEI_NS)
    if title_elem is not None and title_elem.text:
        title = title_elem.text.strip()

    # Parse authors
    authors = []
    for author in bibl.findall('.//tei:analytic/tei:author', TEI_NS):
        name = _extract_author_name(author)
        if name:
            authors.append(name)
    # If no analytic authors, try monogr
    if not authors:
        for author in bibl.findall('.//tei:monogr/tei:author', TEI_NS):
            name = _extract_author_name(author)
            if name:
                authors.append(name)

    # Parse year
    year = None
    date_elem = bibl.find('.//tei:imprint/tei:date', TEI_NS)
    if date_elem is not None:
        year = date_elem.get('when', date_elem.text)
        if year:
            year = year[:4]  # Extract just the year

    # Parse journal/venue
    journal = None
    journal_elem = bibl.find('.//tei:monogr/tei:title[@level="j"]', TEI_NS)
    if journal_elem is not None and journal_elem.text:
        journal = journal_elem.text.strip()

    # Parse volume and pages
    volume = None
    volume_elem = bibl.find('.//tei:imprint/tei:biblScope[@unit="volume"]', TEI_NS)
    if volume_elem is not None and volume_elem.text:
        volume = volume_elem.text.strip()

    pages = None
    page_elem = bibl.find('.//tei:imprint/tei:biblScope[@unit="page"]', TEI_NS)
    if page_elem is not None:
        from_page = page_elem.get('from', '')
        to_page = page_elem.get('to', '')
        if from_page and to_page:
            pages = f"{from_page}-{to_page}"
        elif from_page:
            pages = from_page
        elif page_elem.text:
            pages = page_elem.text.strip()

    # Parse DOI
    doi = None
    for idno in bibl.findall('.//tei:idno', TEI_NS):
        if idno.get('type') == 'DOI' and idno.text:
            doi = idno.text.strip()
            break

    # Parse arXiv ID
    arxiv_id = None
    for idno in bibl.findall('.//tei:idno', TEI_NS):
        if idno.get('type') == 'arXiv' and idno.text:
            arxiv_id = idno.text.strip()
            break

    # Get raw citation text if available
    raw_text = None
    note_elem = bibl.find('.//tei:note[@type="raw_reference"]', TEI_NS)
    if note_elem is not None and note_elem.text:
        raw_text = note_elem.text.strip()

    return Citation(
        id=cite_id,
        title=title,
        authors=authors,
        year=year,
        journal=journal,
        volume=volume,
        pages=pages,
        doi=doi,
        arxiv_id=arxiv_id,
        raw_text=raw_text
    )


def _extract_author_name(author_elem: ET.Element) -> Optional[str]:
    """Extract author name from TEI author element."""
    persname = author_elem.find('tei:persName', TEI_NS)
    if persname is None:
        return None

    forename = persname.find('tei:forename', TEI_NS)
    surname = persname.find('tei:surname', TEI_NS)

    parts = []
    if forename is not None and forename.text:
        parts.append(forename.text.strip())
    if surname is not None and surname.text:
        parts.append(surname.text.strip())

    return ' '.join(parts) if parts else None


@dataclass
class ExtractionResult:
    """Result of PDF citation extraction containing citations and their contexts."""
    citations: list[Citation]
    contexts: dict[str, list[str]]  # citation_id -> list of context paragraphs
    marker_to_id: dict[str, str]  # marker text -> citation_id (e.g., "[1]" -> "b0")


def _parse_marker_mapping(root: ET.Element, citation_ids: list[str]) -> tuple[dict[str, str], set[str]]:
    """
    Extract mapping from in-text citation markers to citation IDs.
    Infers missing numeric markers based on the pattern.
    e.g., {"[1]": "b0", "[2]": "b1", "Smith et al., 2020": "b5"}

    Returns:
        (marker_to_id, direct_targets) — direct_targets is the set of citation
        IDs that GROBID's body parser actually emitted as ref targets, before
        any inference. Useful for spotting hallucinated bib entries that no
        body text points to.
    """
    marker_to_id = {}
    direct_targets = set()

    for ref in root.findall('.//tei:body//tei:ref[@type="bibr"]', TEI_NS):
        target = ref.get('target', '').lstrip('#')
        text = ''.join(ref.itertext()).strip()

        if target:
            direct_targets.add(target)
        if target and text and text not in marker_to_id:
            marker_to_id[text] = target

    # Infer missing numeric markers
    # Check if we're using numeric markers like [1], [2], etc.
    numeric_markers = {}
    for marker, cid in marker_to_id.items():
        if marker.startswith('[') and marker.endswith(']'):
            try:
                num = int(marker[1:-1])
                numeric_markers[num] = cid
            except ValueError:
                pass

    if numeric_markers:
        # Find the pattern: typically [n] -> b(n-1)
        # Infer missing markers based on citation_ids
        for i, cid in enumerate(citation_ids):
            marker = f"[{i + 1}]"
            if marker not in marker_to_id:
                marker_to_id[marker] = cid
                print(f"[*] Inferred missing marker: {marker} -> {cid}")

    return marker_to_id, direct_targets


def _parse_contexts_from_tei(root: ET.Element, marker_to_id: dict[str, str]) -> dict[str, list[str]]:
    """
    Extract in-text citation contexts from parsed TEI XML.
    Also searches for missing marker contexts in raw paragraph text.
    Includes abstract since citations may only appear there.
    """
    contexts = {}

    # Get all paragraphs from body
    paragraphs = []
    for para in root.findall('.//tei:body//tei:p', TEI_NS):
        para_text = ''.join(para.itertext()).strip()
        paragraphs.append(para_text)

        # Extract contexts from explicit refs
        for ref in para.findall('.//tei:ref[@type="bibr"]', TEI_NS):
            target = ref.get('target', '').lstrip('#')
            if target:
                if target not in contexts:
                    contexts[target] = []
                if para_text not in contexts[target]:
                    contexts[target].append(para_text)

    # Also get abstract text (citations sometimes only appear there)
    abstract_elem = root.find('.//tei:profileDesc//tei:abstract', TEI_NS)
    if abstract_elem is not None:
        # Get all paragraphs in abstract
        abstract_paras = abstract_elem.findall('.//tei:p', TEI_NS)
        if abstract_paras:
            for para in abstract_paras:
                para_text = ''.join(para.itertext()).strip()
                if para_text:
                    paragraphs.append(para_text)
        else:
            # Only use full abstract text if no nested paragraphs
            abstract_text = ''.join(abstract_elem.itertext()).strip()
            if abstract_text:
                paragraphs.append(abstract_text)

    # Search for missing marker contexts in raw text (body + abstract)
    for marker, cid in marker_to_id.items():
        if cid not in contexts:
            # Extract the number from marker like "[1]" -> "1"
            marker_num = None
            if marker.startswith('[') and marker.endswith(']'):
                try:
                    marker_num = marker[1:-1]
                    int(marker_num)  # Validate it's a number
                except ValueError:
                    marker_num = None

            # Search paragraphs for this marker
            for para_text in paragraphs:
                found = False

                # Check exact marker match
                if marker in para_text:
                    found = True
                # Check combined citation patterns like [1,2], [1, 2], [1-3]
                elif marker_num:
                    import re
                    pattern = r'\[[\d,\s\-]*\b' + re.escape(marker_num) + r'\b[\d,\s\-]*\]'
                    if re.search(pattern, para_text):
                        found = True

                if found:
                    if cid not in contexts:
                        contexts[cid] = []
                    if para_text not in contexts[cid]:
                        contexts[cid].append(para_text)

    return contexts


def extract_citations_with_contexts(
    pdf_path: str,
    grobid_url: str = "http://localhost:8070"
) -> ExtractionResult:
    """
    Extract citations and their in-text contexts from a PDF in a single GROBID call.

    Args:
        pdf_path: Path to the PDF file
        grobid_url: URL of the GROBID service

    Returns:
        ExtractionResult containing citations and their contexts
    """
    client = GrobidClient(grobid_url)

    if not client.is_alive():
        raise ConnectionError(
            f"GROBID service not available at {grobid_url}. "
            "Please start GROBID with: docker run -p 8070:8070 lfoppiano/grobid:0.8.0"
        )

    total_start = time.perf_counter()

    t0 = time.perf_counter()
    tei_xml = client.process_pdf(pdf_path)
    grobid_elapsed = time.perf_counter() - t0
    print(f"[*] GROBID processing: {grobid_elapsed:.2f}s")

    t0 = time.perf_counter()
    print("[*] Parsing TEI XML...")
    root = ET.fromstring(tei_xml)
    print(f"[*] TEI parsing: {time.perf_counter() - t0:.2f}s")

    t0 = time.perf_counter()
    print("[*] Extracting citations...")
    citations = []
    for bibl in root.findall('.//tei:listBibl/tei:biblStruct', TEI_NS):
        citation = _parse_bibl_struct(bibl)
        if citation:
            citations.append(citation)
    print(f"[*] Found {len(citations)} citations ({time.perf_counter() - t0:.2f}s)")

    t0 = time.perf_counter()
    print("[*] Extracting marker mappings...")
    citation_ids = [c.id for c in citations]
    marker_to_id, direct_targets = _parse_marker_mapping(root, citation_ids)
    print(f"[*] Found {len(marker_to_id)} unique markers ({time.perf_counter() - t0:.2f}s)")

    t0 = time.perf_counter()
    print("[*] Extracting contexts...")
    contexts = _parse_contexts_from_tei(root, marker_to_id)
    print(f"[*] Found contexts for {len(contexts)} citations ({time.perf_counter() - t0:.2f}s)")

    # Drop bib entries that GROBID's body parser never linked to and that
    # the context fallback also failed to find — almost always hallucinated
    # splits of a real reference.
    hallucinated = {
        c.id for c in citations
        if c.id not in direct_targets and not contexts.get(c.id)
    }
    if hallucinated:
        print(f"[*] Removing {len(hallucinated)} likely hallucinated citations: {sorted(hallucinated)}")
        citations = [c for c in citations if c.id not in hallucinated]
        contexts = {k: v for k, v in contexts.items() if k not in hallucinated}
        marker_to_id = {m: cid for m, cid in marker_to_id.items() if cid not in hallucinated}

    print(f"[*] Total extraction time: {time.perf_counter() - total_start:.2f}s")
    return ExtractionResult(citations=citations, contexts=contexts, marker_to_id=marker_to_id)


# Example usage
if __name__ == "__main__":
    import sys
    import json

    if len(sys.argv) < 2:
        print("Usage: python extract_citation.py <pdf_path>")
        print("\nMake sure GROBID is running:")
        print("  https://grobid.readthedocs.io/en/latest/Grobid-docker/")
        sys.exit(1)

    pdf_path = sys.argv[1]

    try:
        result = extract_citations_with_contexts(pdf_path)

        print(f"\nExtracted {len(result.citations)} citations:\n")
        # for i, cite in enumerate(result.citations, 1):
        #     print(f"[{i}] {cite.title or 'No title'}")
        #     if cite.authors:
        #         print(f"    Authors: {', '.join(cite.authors)}")
        #     if cite.year:
        #         print(f"    Year: {cite.year}")
        #     if cite.journal:
        #         print(f"    Journal: {cite.journal}")
        #     if cite.doi:
        #         print(f"    DOI: {cite.doi}")
        #     if cite.arxiv_id:
        #         print(f"    arXiv: {cite.arxiv_id}")
        #     # Show contexts if available
        #     if cite.id in result.contexts:
        #         print(f"    Contexts: {len(result.contexts[cite.id])} occurrence(s)")
        #     print()

        # Also output as JSON for programmatic use
        output = {
            'citations': [
                {
                    'id': c.id,
                    'title': c.title,
                    'authors': c.authors,
                    'year': c.year,
                    'journal': c.journal,
                    'volume': c.volume,
                    'pages': c.pages,
                    'doi': c.doi,
                    'arxiv_id': c.arxiv_id,
                    'raw_text': c.raw_text,
                    'contexts': result.contexts.get(c.id, [])
                }
                for c in result.citations
            ]
        }

        with open('citations_output.json', 'w') as f:
            json.dump(output, f, indent=2)
        print(f"JSON output saved to citations_output.json")

    except ConnectionError as e:
        print(f"Error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Error processing PDF: {e}")
        sys.exit(1)
