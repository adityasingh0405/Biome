import React, { useState, useEffect } from 'react';
import { 
  FolderDown, 
  UploadCloud, 
  FileText, 
  Search, 
  RefreshCw, 
  CheckCircle2, 
  AlertCircle, 
  Database,
  Terminal,
  Layers,
  ArrowUpRight
} from 'lucide-react';
import { 
  fetchDocuments, 
  uploadFiles, 
  ingestDirectory, 
  ingestText, 
  fetchHealth 
} from '../../services/api';

export default function KnowledgeBaseView({ onHealthUpdate }) {
  const [documents, setDocuments] = useState([]);
  const [loadingDocs, setLoadingDocs] = useState(false);
  const [searchFilter, setSearchFilter] = useState('');
  
  // Ingest mode: 'upload' | 'directory' | 'text'
  const [ingestTab, setIngestTab] = useState('upload');
  
  // Form states
  const [uploadFileList, setUploadFileList] = useState([]);
  const [dirPath, setDirPath] = useState('');
  const [dirRecursive, setDirRecursive] = useState(true);
  const [rawTitle, setRawTitle] = useState('');
  const [rawContent, setRawContent] = useState('');
  
  // Progress & feedback
  const [ingesting, setIngesting] = useState(false);
  const [statusMessage, setStatusMessage] = useState(null);

  const loadCatalog = async () => {
    setLoadingDocs(true);
    try {
      const res = await fetchDocuments();
      setDocuments(res.documents || []);
      const h = await fetchHealth();
      if (onHealthUpdate) onHealthUpdate(h);
    } catch (err) {
      console.error("Failed to load document catalog:", err);
    } finally {
      setLoadingDocs(false);
    }
  };

  useEffect(() => {
    loadCatalog();
  }, []);

  const handleUploadSubmit = async (e) => {
    e.preventDefault();
    if (uploadFileList.length === 0) return;
    setIngesting(true);
    setStatusMessage(null);
    try {
      const res = await uploadFiles(uploadFileList);
      setStatusMessage({
        type: 'success',
        text: `Successfully ingested ${uploadFileList.length} file(s)! Created active chunks in Chroma & BM25.`
      });
      setUploadFileList([]);
      await loadCatalog();
    } catch (err) {
      setStatusMessage({
        type: 'error',
        text: `Upload failed: ${err.message || err}`
      });
    } finally {
      setIngesting(false);
    }
  };

  const handleDirSubmit = async (e) => {
    e.preventDefault();
    if (!dirPath.trim()) return;
    setIngesting(true);
    setStatusMessage(null);
    try {
      const res = await ingestDirectory(dirPath.trim(), dirRecursive);
      setStatusMessage({
        type: 'success',
        text: `Crawled directory successfully! Ingested files from ${dirPath}.`
      });
      await loadCatalog();
    } catch (err) {
      setStatusMessage({
        type: 'error',
        text: `Directory crawling failed: ${err.message || err}`
      });
    } finally {
      setIngesting(false);
    }
  };

  const handleTextSubmit = async (e) => {
    e.preventDefault();
    if (!rawTitle.trim() || !rawContent.trim()) return;
    setIngesting(true);
    setStatusMessage(null);
    try {
      await ingestText(rawTitle.trim(), rawContent.trim());
      setStatusMessage({
        type: 'success',
        text: `Ingested document '${rawTitle}' into vector store.`
      });
      setRawTitle('');
      setRawContent('');
      await loadCatalog();
    } catch (err) {
      setStatusMessage({
        type: 'error',
        text: `Text ingestion failed: ${err.message || err}`
      });
    } finally {
      setIngesting(false);
    }
  };

  const filteredDocs = documents.filter(d => 
    d.source?.toLowerCase().includes(searchFilter.toLowerCase())
  );

  return (
    <div className="flex flex-col max-w-7xl mx-auto w-full gap-8 pb-12">
      
      {/* Top Banner */}
      <div className="p-6 rounded-3xl glass-card border-emerald-500/20 shadow-glass-card flex flex-wrap items-center justify-between gap-4">
        <div>
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 text-xs font-mono mb-2">
            <Database className="w-3.5 h-3.5" />
            <span>Hybrid Document Corpus & Ingestion Engine</span>
          </div>
          <h2 className="text-2xl font-bold text-white tracking-tight">
            Knowledge Base Catalog
          </h2>
          <p className="text-slate-300 text-sm mt-1">
            Synchronize enterprise manuals, policies, Markdown wikis, and system directories across dense vector indices and lexical stores.
          </p>
        </div>

        <button
          onClick={loadCatalog}
          disabled={loadingDocs}
          className="flex items-center gap-2 px-4 py-2.5 rounded-xl bg-dark-950 border border-emerald-500/30 text-emerald-400 hover:border-emerald-400 text-xs font-mono font-semibold transition-all"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${loadingDocs ? 'animate-spin' : ''}`} />
          <span>Refresh Catalog</span>
        </button>
      </div>

      {/* Main 2-Column Layout */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
        
        {/* Left Column: Documents Browser (7 cols) */}
        <div className="lg:col-span-7 space-y-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2 text-sm font-bold text-white font-mono">
              <Layers className="w-4 h-4 text-emerald-400" />
              <span>Indexed Sources ({filteredDocs.length})</span>
            </div>
            
            {/* Filter Input */}
            <div className="relative w-48 sm:w-64">
              <Search className="w-3.5 h-3.5 text-slate-500 absolute left-3 top-2.5" />
              <input
                type="text"
                value={searchFilter}
                onChange={(e) => setSearchFilter(e.target.value)}
                placeholder="Filter files..."
                className="w-full bg-dark-950 border border-slate-800 focus:border-emerald-400/50 rounded-xl pl-8 pr-3 py-1.5 text-xs text-slate-200 placeholder-slate-500 focus:outline-none"
              />
            </div>
          </div>

          {/* List of Files */}
          <div className="space-y-2.5">
            {filteredDocs.map((doc, idx) => {
              const fileName = doc.source?.split(/[\/\\]/).pop() || doc.source;
              return (
                <div 
                  key={idx}
                  className="p-4 rounded-2xl glass-card border-slate-800 hover:border-emerald-500/30 transition-all flex items-center justify-between gap-3 group"
                >
                  <div className="flex items-center gap-3 min-w-0">
                    <div className="w-9 h-9 rounded-xl bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center text-emerald-400 flex-shrink-0">
                      <FileText className="w-4 h-4" />
                    </div>
                    <div className="min-w-0">
                      <div className="text-sm font-semibold text-slate-200 truncate group-hover:text-emerald-300 transition-colors">
                        {fileName}
                      </div>
                      <div className="text-[11px] font-mono text-slate-500 truncate">
                        {doc.source}
                      </div>
                    </div>
                  </div>

                  <div className="flex items-center gap-2 flex-shrink-0">
                    <span className="px-2.5 py-1 rounded-lg bg-dark-950 border border-emerald-500/30 text-emerald-400 font-mono text-xs font-semibold">
                      {doc.chunk_count || 0} chunks
                    </span>
                  </div>
                </div>
              );
            })}

            {filteredDocs.length === 0 && !loadingDocs && (
              <div className="p-8 rounded-2xl glass-card text-center text-slate-500 text-xs font-mono">
                No documents matching your search filter.
              </div>
            )}
          </div>
        </div>

        {/* Right Column: Ingest Tools (5 cols) */}
        <div className="lg:col-span-5 space-y-4">
          <div className="text-sm font-bold text-white font-mono flex items-center gap-2">
            <UploadCloud className="w-4 h-4 text-emerald-400" />
            <span>Ingest New Documentation</span>
          </div>

          <div className="p-6 rounded-3xl glass-card border-emerald-500/25 shadow-glass-card space-y-5">
            
            {/* Tabs */}
            <div className="flex rounded-xl bg-dark-950 p-1 border border-slate-800">
              <button
                onClick={() => setIngestTab('upload')}
                className={`flex-1 py-1.5 rounded-lg text-xs font-medium transition-all ${
                  ingestTab === 'upload' 
                    ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/40 shadow-green-glow-subtle' 
                    : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                Upload Files
              </button>
              <button
                onClick={() => setIngestTab('directory')}
                className={`flex-1 py-1.5 rounded-lg text-xs font-medium transition-all ${
                  ingestTab === 'directory' 
                    ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/40 shadow-green-glow-subtle' 
                    : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                Crawl Folder
              </button>
              <button
                onClick={() => setIngestTab('text')}
                className={`flex-1 py-1.5 rounded-lg text-xs font-medium transition-all ${
                  ingestTab === 'text' 
                    ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/40 shadow-green-glow-subtle' 
                    : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                Raw Snippet
              </button>
            </div>

            {/* Tab 1: Upload Files */}
            {ingestTab === 'upload' && (
              <form onSubmit={handleUploadSubmit} className="space-y-4">
                <div className="border-2 border-dashed border-emerald-500/25 hover:border-emerald-400/50 rounded-2xl p-6 text-center transition-all bg-dark-950/50">
                  <UploadCloud className="w-8 h-8 text-emerald-400 mx-auto mb-2" />
                  <div className="text-xs text-slate-300 font-medium">
                    Upload PDF, Markdown, TXT, JSON, CSV, Python
                  </div>
                  <input
                    type="file"
                    multiple
                    onChange={(e) => setUploadFileList(Array.from(e.target.files || []))}
                    className="mt-3 block w-full text-xs text-slate-400 file:mr-4 file:py-2 file:px-4 file:rounded-xl file:border-0 file:text-xs file:font-semibold file:bg-emerald-500/20 file:text-emerald-300 hover:file:bg-emerald-500/30 cursor-pointer"
                  />
                  {uploadFileList.length > 0 && (
                    <div className="mt-2 text-xs text-emerald-400 font-mono">
                      Selected {uploadFileList.length} file(s)
                    </div>
                  )}
                </div>

                <button
                  type="submit"
                  disabled={uploadFileList.length === 0 || ingesting}
                  className="w-full py-3 rounded-xl bg-emerald-500 hover:bg-emerald-400 disabled:opacity-50 text-dark-950 font-bold text-xs flex items-center justify-center gap-2 shadow-green-glow transition-all cursor-pointer"
                >
                  {ingesting ? (
                    <div className="w-3.5 h-3.5 border-2 border-dark-950 border-t-transparent rounded-full animate-spin"></div>
                  ) : (
                    <FolderDown className="w-3.5 h-3.5" />
                  )}
                  <span>Ingest & Index Files</span>
                </button>
              </form>
            )}

            {/* Tab 2: Crawl Directory */}
            {ingestTab === 'directory' && (
              <form onSubmit={handleDirSubmit} className="space-y-4">
                <div>
                  <label className="block text-xs font-mono text-slate-400 mb-1">
                    System Directory Path:
                  </label>
                  <input
                    type="text"
                    value={dirPath}
                    onChange={(e) => setDirPath(e.target.value)}
                    placeholder="e.g. data/raw or /var/docs"
                    className="w-full bg-dark-950 border border-slate-800 rounded-xl px-3 py-2 text-xs text-slate-200 placeholder-slate-600 focus:outline-none focus:border-emerald-400"
                  />
                </div>

                <label className="flex items-center gap-2 text-xs text-slate-300 cursor-pointer select-none">
                  <input
                    type="checkbox"
                    checked={dirRecursive}
                    onChange={(e) => setDirRecursive(e.target.checked)}
                    className="rounded border-slate-800 text-emerald-500 focus:ring-emerald-500 bg-dark-950"
                  />
                  <span>Recursive crawl (include sub-directories)</span>
                </label>

                <button
                  type="submit"
                  disabled={!dirPath.trim() || ingesting}
                  className="w-full py-3 rounded-xl bg-emerald-500 hover:bg-emerald-400 disabled:opacity-50 text-dark-950 font-bold text-xs flex items-center justify-center gap-2 shadow-green-glow transition-all cursor-pointer"
                >
                  {ingesting ? (
                    <div className="w-3.5 h-3.5 border-2 border-dark-950 border-t-transparent rounded-full animate-spin"></div>
                  ) : (
                    <Terminal className="w-3.5 h-3.5" />
                  )}
                  <span>Crawl & Index Directory</span>
                </button>
              </form>
            )}

            {/* Tab 3: Raw Snippet */}
            {ingestTab === 'text' && (
              <form onSubmit={handleTextSubmit} className="space-y-3">
                <div>
                  <label className="block text-xs font-mono text-slate-400 mb-1">
                    Title / Source Identifier:
                  </label>
                  <input
                    type="text"
                    value={rawTitle}
                    onChange={(e) => setRawTitle(e.target.value)}
                    placeholder="e.g. quarterly_compliance_memo"
                    className="w-full bg-dark-950 border border-slate-800 rounded-xl px-3 py-2 text-xs text-slate-200 placeholder-slate-600 focus:outline-none focus:border-emerald-400"
                  />
                </div>
                <div>
                  <label className="block text-xs font-mono text-slate-400 mb-1">
                    Markdown or Plain Text Content:
                  </label>
                  <textarea
                    rows={4}
                    value={rawContent}
                    onChange={(e) => setRawContent(e.target.value)}
                    placeholder="Paste policy, wiki, or release notes..."
                    className="w-full bg-dark-950 border border-slate-800 rounded-xl px-3 py-2 text-xs text-slate-200 placeholder-slate-600 focus:outline-none focus:border-emerald-400 font-mono"
                  ></textarea>
                </div>

                <button
                  type="submit"
                  disabled={!rawTitle.trim() || !rawContent.trim() || ingesting}
                  className="w-full py-3 rounded-xl bg-emerald-500 hover:bg-emerald-400 disabled:opacity-50 text-dark-950 font-bold text-xs flex items-center justify-center gap-2 shadow-green-glow transition-all cursor-pointer"
                >
                  {ingesting ? (
                    <div className="w-3.5 h-3.5 border-2 border-dark-950 border-t-transparent rounded-full animate-spin"></div>
                  ) : (
                    <FileText className="w-3.5 h-3.5" />
                  )}
                  <span>Ingest Text Snippet</span>
                </button>
              </form>
            )}

            {/* Feedback alert */}
            {statusMessage && (
              <div className={`p-3 rounded-xl border text-xs flex items-start gap-2 ${
                statusMessage.type === 'success' 
                  ? 'bg-emerald-950/40 border-emerald-500/40 text-emerald-300' 
                  : 'bg-red-950/40 border-red-500/40 text-red-300'
              }`}>
                {statusMessage.type === 'success' ? (
                  <CheckCircle2 className="w-4 h-4 text-emerald-400 flex-shrink-0 mt-0.5" />
                ) : (
                  <AlertCircle className="w-4 h-4 text-red-400 flex-shrink-0 mt-0.5" />
                )}
                <span>{statusMessage.text}</span>
              </div>
            )}

          </div>
        </div>

      </div>

    </div>
  );
}
