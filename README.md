# Citation Navigator

A web application that extracts and analyzes citations from research papers. Upload a PDF and get structured citation data with metadata from Semantic Scholar.

## Prerequisites

- Python 3.10+
- Node.js 20+
- Docker
- Anthropic or Groq API key (optional, for AI summaries)

## Setup

### 1. Start GROBID (PDF parsing service)

For macOS ARM64:
```bash
docker run --ulimit core=0 --platform linux/amd64 --init -p 8070:8070 --name grobid lfoppiano/grobid:0.9.0-crf
```

For other platforms, see [GROBID Docker documentation](https://grobid.readthedocs.io/en/latest/Grobid-docker/).

Wait ~30 seconds for GROBID to initialize. Verify it's running:

```bash
curl http://localhost:8070/api/isalive
```

### 2. Backend Setup

```bash
# Create and activate virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run the backend server
python app.py
```

Backend runs on http://localhost:3001

### Backend Options

```bash
# No LLM summaries (default)
python app.py

# Enable LLM summaries with Anthropic Claude
export ANTHROPIC_API_KEY=your-key-here
python app.py --llm anthropic

# Enable LLM summaries with Groq
export GROQ_API_KEY=your-key-here
python app.py --llm groq

# Keep cached data between restarts
python app.py --no-clean

# Custom port
python app.py --port 5000
```

### 3. Frontend Setup

```bash
cd frontend

# Install dependencies
npm install

# Run the development server
npm start
```

Frontend runs on http://localhost:3000

## Usage

1. Open http://localhost:3000 in your browser
2. Click "Choose PDF" and select a research paper
3. Click "Extract Citations" to process the paper
4. Browse citations in the right panel
5. Click a citation to see metadata, abstract, and in-context quotes (plus AI summary if `--llm` enabled)

## API Endpoints

- `POST /api/upload` - Upload PDF and extract citations
- `GET /api/documents/<doc_id>/citations` - Get all citations for a document
- `GET /api/documents/<doc_id>/citations/<cite_id>` - Get single citation with Semantic Scholar metadata

## Project Structure

```
final_project/
├── app.py                 # Flask backend
├── extract_citation.py    # GROBID PDF parsing
├── semantic_scholar.py    # Semantic Scholar API client
├── summarize.py           # LLM-powered citation summaries (Anthropic/Groq)
├── uploads/               # Uploaded PDFs
├── data/                  # Cached citation data
└── frontend/              # React frontend
    └── src/
        └── App.tsx        # Main React component
```
