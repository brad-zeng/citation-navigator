import React, { useState, useCallback } from 'react';
import { Document, Page, pdfjs } from 'react-pdf';
import 'react-pdf/dist/Page/AnnotationLayer.css';
import 'react-pdf/dist/Page/TextLayer.css';

// Set up PDF.js worker
pdfjs.GlobalWorkerOptions.workerSrc = `//unpkg.com/pdfjs-dist@${pdfjs.version}/build/pdf.worker.min.mjs`;

const API_URL = 'http://localhost:3001';

interface Citation {
  id: string;
  title: string | null;
  authors: string[];
  year: string | null;
  journal: string | null;
  doi: string | null;
  arxiv_id: string | null;
  raw_text: string | null;
  contexts: string[];
  metadata?: {
    title: string;
    authors: string[];
    abstract: string | null;
    year: number | null;
    venue: string | null;
    citation_count: number | null;
    doi: string | null;
    arxiv_id: string | null;
    url: string | null;
    pdf_url: string | null;
  };
  summary?: string | null;
}

interface DocumentData {
  document_id: string;
  filename: string;
  citation_count: number;
  marker_to_id: Record<string, string>;
}

function App() {
  const [file, setFile] = useState<File | null>(null);
  const [pdfUrl, setPdfUrl] = useState<string | null>(null);
  const [numPages, setNumPages] = useState<number>(0);
  const [docData, setDocData] = useState<DocumentData | null>(null);
  const [citations, setCitations] = useState<Citation[]>([]);
  const [selectedCitation, setSelectedCitation] = useState<Citation | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [abstractOpen, setAbstractOpen] = useState(false);
  const [contextOpen, setContextOpen] = useState(false);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const selectedFile = e.target.files?.[0];
    if (selectedFile) {
      setFile(selectedFile);
      setPdfUrl(URL.createObjectURL(selectedFile));
      setDocData(null);
      setCitations([]);
      setSelectedCitation(null);
      setError(null);
    }
  };

  const handleUpload = async () => {
    if (!file) return;

    setLoading(true);
    setError(null);

    const formData = new FormData();
    formData.append('file', file);

    try {
      const uploadRes = await fetch(`${API_URL}/api/upload`, {
        method: 'POST',
        body: formData,
      });

      if (!uploadRes.ok) {
        const err = await uploadRes.json();
        throw new Error(err.error || 'Upload failed');
      }

      const data: DocumentData = await uploadRes.json();
      setDocData(data);

      const citationsRes = await fetch(`${API_URL}/api/documents/${data.document_id}/citations`);
      const citationsData = await citationsRes.json();
      setCitations(citationsData.citations);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An error occurred');
    } finally {
      setLoading(false);
    }
  };

  const handleCitationClick = async (citation: Citation) => {
    if (!docData) return;

    try {
      const res = await fetch(`${API_URL}/api/documents/${docData.document_id}/citations/${citation.id}`);
      const fullCitation = await res.json();
      setSelectedCitation(fullCitation);
      setAbstractOpen(false);
      setContextOpen(false);
    } catch (err) {
      setSelectedCitation(citation);
      setAbstractOpen(false);
      setContextOpen(false);
    }
  };

  const onDocumentLoadSuccess = useCallback(({ numPages }: { numPages: number }) => {
    setNumPages(numPages);
  }, []);

  return (
    <div className="min-h-screen bg-gray-100">
      {/* Header */}
      <header className="bg-slate-800 text-white px-6 py-4">
        <h1 className="text-xl font-medium">Citation Navigator</h1>
      </header>

      <div className="p-4">
        {/* Upload Section */}
        <div className="flex items-center gap-4 p-4 bg-white rounded-lg shadow-sm mb-4">
          <input
            type="file"
            accept=".pdf"
            onChange={handleFileChange}
            id="file-input"
            className="hidden"
          />
          <label
            htmlFor="file-input"
            className="px-4 py-2 bg-gray-100 rounded cursor-pointer hover:bg-gray-200 transition"
          >
            {file ? file.name : 'Choose PDF'}
          </label>
          <button
            onClick={handleUpload}
            disabled={!file || loading}
            className="px-6 py-2 bg-blue-500 text-white rounded hover:bg-blue-600 disabled:bg-gray-300 disabled:cursor-not-allowed transition"
          >
            {loading ? 'Processing...' : 'Extract Citations'}
          </button>
          {error && <p className="text-red-500">{error}</p>}
          {docData && <p className="text-green-600">Found {docData.citation_count} citations</p>}
        </div>

        {/* Main Content */}
        <div className="grid grid-cols-1 lg:grid-cols-[1fr_350px] gap-4">
          {/* PDF Viewer */}
          <div className="bg-white rounded-lg shadow-sm p-4 max-h-[calc(100vh-200px)] overflow-y-auto">
            {pdfUrl ? (
              <Document
                file={pdfUrl}
                onLoadSuccess={onDocumentLoadSuccess}
                loading={<p className="text-gray-500">Loading PDF...</p>}
                className="flex flex-col items-center"
              >
                {Array.from(new Array(numPages), (_, index) => (
                  <Page
                    key={`page_${index + 1}`}
                    pageNumber={index + 1}
                    width={600}
                    className="mb-4 shadow-lg"
                  />
                ))}
              </Document>
            ) : (
              <p className="text-gray-400 text-center py-20">Select a PDF to view</p>
            )}
          </div>

          {/* Citations Panel */}
          <div className="bg-white rounded-lg shadow-sm p-4 max-h-[calc(100vh-200px)] overflow-y-auto">
            <h2 className="text-lg font-medium text-slate-700 mb-4">Citations</h2>
            {citations.length === 0 && !loading && (
              <p className="text-gray-400 italic">Upload a PDF to see citations</p>
            )}
            <ul className="space-y-1">
              {citations.map((citation, index) => (
                <li
                  key={citation.id}
                  onClick={() => handleCitationClick(citation)}
                  className={`flex gap-2 p-3 rounded cursor-pointer transition border-l-2 ${
                    selectedCitation?.id === citation.id
                      ? 'bg-blue-50 border-blue-500'
                      : 'hover:bg-gray-50 border-transparent'
                  }`}
                >
                  <span className="text-blue-500 font-semibold shrink-0">[{index + 1}]</span>
                  <span className="text-slate-700 text-sm line-clamp-2">
                    {citation.title || citation.raw_text?.slice(0, 100) || 'Unknown title'}
                  </span>
                </li>
              ))}
            </ul>
          </div>
        </div>

        {/* Citation Details Modal */}
        {selectedCitation && (
          <div className="fixed right-4 top-20 w-96 max-h-[calc(100vh-100px)] overflow-y-auto bg-white rounded-lg shadow-xl p-6 z-50">
            <div className="flex justify-between items-start mb-4">
              <h2 className="text-sm text-gray-500">Citation Details</h2>
              <button
                onClick={() => setSelectedCitation(null)}
                className="text-gray-400 hover:text-gray-600 text-2xl leading-none"
              >
                &times;
              </button>
            </div>

            <h3 className="text-lg font-medium text-slate-800 mb-4 leading-snug">
              {selectedCitation.title || 'Unknown Title'}
            </h3>

            {selectedCitation.summary && (
              <div className="mb-4 p-3 bg-blue-50 rounded-lg border border-blue-100">
                <p className="text-sm text-slate-700 leading-relaxed">
                  {selectedCitation.summary}
                </p>
              </div>
            )}

            {selectedCitation.authors?.length > 0 && (
              <p className="text-sm text-slate-600 mb-2">
                <span className="font-medium">Authors:</span> {selectedCitation.authors.join(', ')}
              </p>
            )}

            {selectedCitation.year && (
              <p className="text-sm text-slate-600 mb-2">
                <span className="font-medium">Year:</span> {selectedCitation.year}
              </p>
            )}

            {selectedCitation.journal && (
              <p className="text-sm text-slate-600 mb-2">
                <span className="font-medium">Journal:</span> {selectedCitation.journal}
              </p>
            )}

            {selectedCitation.doi && (
              <p className="text-sm text-slate-600 mb-2">
                <span className="font-medium">DOI:</span>{' '}
                <a
                  href={`https://doi.org/${selectedCitation.doi}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-blue-500 hover:underline"
                >
                  {selectedCitation.doi}
                </a>
              </p>
            )}

            {(selectedCitation.arxiv_id || selectedCitation.metadata?.arxiv_id) && (
              <p className="text-sm text-slate-600 mb-2">
                <span className="font-medium">arXiv:</span>{' '}
                <a
                  href={`https://arxiv.org/abs/${selectedCitation.arxiv_id || selectedCitation.metadata?.arxiv_id}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-blue-500 hover:underline"
                >
                  {selectedCitation.arxiv_id || selectedCitation.metadata?.arxiv_id}
                </a>
              </p>
            )}

            {selectedCitation.metadata?.citation_count != null && (
              <p className="text-sm text-slate-600 mb-2">
                <span className="font-medium">Citations:</span> {selectedCitation.metadata.citation_count}
              </p>
            )}

            {selectedCitation.metadata?.url && (
              <p className="text-sm text-slate-600 mb-2">
                <a
                  href={selectedCitation.metadata.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-blue-500 hover:underline"
                >
                  View on OpenAlex
                </a>
              </p>
            )}

            {selectedCitation.metadata?.abstract && (
              <div className="mt-4 pt-4 border-t border-gray-100">
                <button
                  onClick={() => setAbstractOpen(!abstractOpen)}
                  className="flex items-center justify-between w-full text-left"
                >
                  <span className="font-medium text-sm text-slate-700">Abstract</span>
                  <span className="text-gray-400 text-lg">{abstractOpen ? '−' : '+'}</span>
                </button>
                {abstractOpen && (
                  <p className="mt-2 text-sm text-gray-600 leading-relaxed">
                    {selectedCitation.metadata.abstract}
                  </p>
                )}
              </div>
            )}

            {selectedCitation.contexts?.length > 0 && (
              <div className="mt-4 pt-4 border-t border-gray-100">
                <button
                  onClick={() => setContextOpen(!contextOpen)}
                  className="flex items-center justify-between w-full text-left"
                >
                  <span className="font-medium text-sm text-slate-700">
                    Cited in context ({selectedCitation.contexts.length})
                  </span>
                  <span className="text-gray-400 text-lg">{contextOpen ? '−' : '+'}</span>
                </button>
                {contextOpen && selectedCitation.contexts.map((ctx, i) => (
                  <blockquote
                    key={i}
                    className="mt-2 p-3 bg-gray-50 border-l-2 border-blue-400 text-sm text-gray-600 leading-relaxed"
                  >
                    {ctx}
                  </blockquote>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

export default App;
