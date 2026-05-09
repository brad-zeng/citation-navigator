import os
import json
import uuid
import argparse
from flask import Flask, request, jsonify
from flask_cors import CORS
from werkzeug.utils import secure_filename

from extract_citation import extract_citations_with_contexts
from openalex import enrich_citation, enrich_citations_bulk
from summarize import summarize_citation

app = Flask(__name__)
CORS(app)

# Configure folders
UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), 'uploads')
DATA_FOLDER = os.path.join(os.path.dirname(__file__), 'data')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(DATA_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['DATA_FOLDER'] = DATA_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024


def save_document_data(doc_id: str, data: dict):
    """Save document citation data to JSON file."""
    path = os.path.join(app.config['DATA_FOLDER'], f"{doc_id}.json")
    with open(path, 'w') as f:
        json.dump(data, f, indent=2)


def load_document_data(doc_id: str) -> dict | None:
    """Load document citation data from JSON file."""
    path = os.path.join(app.config['DATA_FOLDER'], f"{doc_id}.json")
    if os.path.exists(path):
        with open(path, 'r') as f:
            return json.load(f)
    return None


@app.route('/')
def home():
    return jsonify({"status": "ok"})


@app.route('/api/upload', methods=['POST'])
def upload_pdf():
    """Upload a PDF and extract citations. Returns document_id for future queries."""
    if 'file' not in request.files:
        return jsonify({"error": "No file provided"}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No file selected"}), 400

    if not file.filename.lower().endswith('.pdf'):
        return jsonify({"error": "File must be a PDF"}), 400

    # Save PDF with unique filename
    filename = secure_filename(file.filename)
    doc_id = str(uuid.uuid4())
    save_path = os.path.join(app.config['UPLOAD_FOLDER'], f"{doc_id}.pdf")
    file.save(save_path)

    try:
        result = extract_citations_with_contexts(save_path)

        citations = [
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

        # Enrich with OpenAlex metadata
        print("[*] Fetching OpenAlex metadata...")
        citations = enrich_citations_bulk(citations)
        print(f"[*] Enriched {sum(1 for c in citations if 'metadata' in c)} citations with metadata")

        # Store citation data
        doc_data = {
            "document_id": doc_id,
            "filename": filename,
            "citation_count": len(citations),
            "citations": {c['id']: c for c in citations},  # Index by citation ID
            "marker_to_id": result.marker_to_id  # e.g., {"[1]": "b0", "[2]": "b1"}
        }
        save_document_data(doc_id, doc_data)

        return jsonify({
            "document_id": doc_id,
            "filename": filename,
            "citation_count": len(citations),
            "marker_to_id": result.marker_to_id
        })

    except ConnectionError as e:
        return jsonify({"error": str(e)}), 503
    except Exception as e:
        return jsonify({"error": f"Failed to process PDF: {str(e)}"}), 500


@app.route('/api/documents/<doc_id>/citations', methods=['GET'])
def get_citations(doc_id):
    """Get all citations for a document."""
    data = load_document_data(doc_id)
    if not data:
        return jsonify({"error": "Document not found"}), 404

    return jsonify({
        "document_id": doc_id,
        "citation_count": data["citation_count"],
        "citations": list(data["citations"].values()),
        "marker_to_id": data.get("marker_to_id", {})
    })


@app.route('/api/documents/<doc_id>/citations/<cite_id>', methods=['GET'])
def get_citation(doc_id, cite_id):
    """Get a specific citation with full details. Lazily fetches metadata and summary."""
    data = load_document_data(doc_id)
    if not data:
        return jsonify({"error": "Document not found"}), 404

    citation = data["citations"].get(cite_id)
    if not citation:
        return jsonify({"error": "Citation not found"}), 404

    updated = False

    # Lazy metadata lookup if not already fetched
    if 'metadata' not in citation:
        citation = enrich_citation(citation)
        updated = True

    # Lazy summary generation if not already done
    llm_provider = app.config.get('LLM_PROVIDER')
    if 'summary' not in citation and llm_provider:
        citation['summary'] = summarize_citation(citation, provider=llm_provider)
        updated = True

    # Cache results
    if updated:
        data["citations"][cite_id] = citation
        save_document_data(doc_id, data)

    return jsonify(citation)


def clean_folders():
    """Remove all files from uploads and data folders."""
    for folder in [UPLOAD_FOLDER, DATA_FOLDER]:
        for filename in os.listdir(folder):
            filepath = os.path.join(folder, filename)
            if os.path.isfile(filepath):
                os.remove(filepath)
                print(f"[*] Removed {filepath}")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Citation Navigator API')
    parser.add_argument('--llm', choices=['anthropic', 'groq'], default=None, help='LLM provider for summaries (default: none)')
    parser.add_argument('--port', type=int, default=3001, help='Port to run on')
    parser.add_argument('--no-clean', action='store_true', help='Skip cleaning uploads/data folders on start')
    args = parser.parse_args()

    if not args.no_clean:
        print("[*] Cleaning uploads and data folders...")
        clean_folders()

    app.config['LLM_PROVIDER'] = args.llm
    print(f"[*] LLM provider: {args.llm or 'disabled'}")

    app.run(debug=True, port=args.port)