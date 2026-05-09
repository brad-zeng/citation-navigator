"""
LLM-powered citation summarization.
Supports Claude (Anthropic) and Groq APIs.
Generates contextual summaries explaining why a paper was cited.
"""

import os

# LLM provider: "anthropic" or "groq"
LLM_PROVIDER = os.environ.get('LLM_PROVIDER', 'anthropic').lower()

# Initialize clients lazily
_anthropic_client = None
_groq_client = None


def _get_anthropic_client():
    global _anthropic_client
    if _anthropic_client is None:
        from anthropic import Anthropic
        _anthropic_client = Anthropic()
    return _anthropic_client


def _get_groq_client():
    global _groq_client
    if _groq_client is None:
        from groq import Groq
        _groq_client = Groq()
    return _groq_client


def summarize_citation(citation: dict, provider: str | None = None) -> str | None:
    """
    Generate a contextual summary of a citation.

    Args:
        citation: Citation dict with metadata and contexts
        provider: LLM provider ("anthropic" or "groq"), defaults to LLM_PROVIDER env var

    Returns:
        A concise summary explaining the citation's relevance, or None on failure
    """
    provider = provider or LLM_PROVIDER
    # Build context for the prompt
    cited_title = citation.get('title') or 'Unknown'
    cited_authors = ', '.join(citation.get('authors', [])[:3])
    if len(citation.get('authors', [])) > 3:
        cited_authors += ' et al.'
    cited_year = citation.get('year') or ''

    # Get abstract from metadata if available
    abstract = None
    if citation.get('metadata'):
        abstract = citation['metadata'].get('abstract')

    # Get contexts where this citation appears
    contexts = citation.get('contexts', [])

    # Need at least some information to summarize
    if not contexts and not abstract:
        return None

    # Build the prompt
    prompt_parts = [
        f"Cited paper: \"{cited_title}\"",
    ]
    if cited_authors:
        prompt_parts.append(f"Authors: {cited_authors}")
    if cited_year:
        prompt_parts.append(f"Year: {cited_year}")

    if abstract:
        truncated_abstract = abstract[:1000] + "..." if len(abstract) > 1000 else abstract
        prompt_parts.append(f"\nAbstract of cited paper:\n{truncated_abstract}")

    if contexts:
        prompt_parts.append("\nContexts where this paper is cited:")
        for i, ctx in enumerate(contexts[:3], 1):
            truncated_ctx = ctx[:500] + "..." if len(ctx) > 500 else ctx
            prompt_parts.append(f"{i}. \"{truncated_ctx}\"")

    context_text = "\n".join(prompt_parts)

    system_prompt = """You are a research assistant helping readers understand citations in academic papers.
Given information about a cited paper and the context in which it was cited, provide a brief summary that explains:
1. What the cited paper is about (1-2 sentences)
2. Why it was cited / its relevance (1-2 sentences)

Note: The metadata (title, authors, abstract) may be incorrect due to automated lookup. Trust the citation context from the paper over the metadata if they conflict.

Be concise. No preamble."""

    user_prompt = f"""{context_text}

Summarize this citation in 2-4 sentences."""

    try:
        if provider == 'groq':
            client = _get_groq_client()
            response = client.chat.completions.create(
                model="llama-3.1-8b-instant",
                max_tokens=200,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ]
            )
            return response.choices[0].message.content
        else:
            # Default to Anthropic
            client = _get_anthropic_client()
            response = client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=200,
                system=system_prompt,
                messages=[
                    {"role": "user", "content": user_prompt}
                ]
            )
            return response.content[0].text
    except Exception as e:
        print(f"[!] LLM API error ({provider}): {e}")
        return None


if __name__ == "__main__":
    test_citation = {
        'title': 'Attention Is All You Need',
        'authors': ['Ashish Vaswani', 'Noam Shazeer', 'Niki Parmar'],
        'year': '2017',
        'contexts': [
            'The Transformer architecture [1] has become the foundation for modern NLP, replacing recurrent models with self-attention mechanisms.',
        ],
        'metadata': {
            'abstract': 'We propose a new simple network architecture, the Transformer, based solely on attention mechanisms, dispensing with recurrence and convolutions entirely.'
        }
    }

    summary = summarize_citation(test_citation)
    print("Summary:", summary)
