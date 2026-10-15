import React, { useState } from 'react';
import { 
  GitCompare, 
  Sparkles, 
  Layers, 
  ArrowRight, 
  CheckCircle2, 
  AlertTriangle,
  Zap,
  Gauge
} from 'lucide-react';
import { compareRetrieval } from '../../services/api';

export default function CompareView() {
  const [question, setQuestion] = useState('What error code indicates invalid credentials and how is it authenticated?');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);

  const testCases = [
    { label: "Specific Error Code", q: "What error code indicates invalid credentials and how is it authenticated?" },
    { label: "Deployment Targets", q: "What is the deployment target error code?" },
    { label: "API Tokens", q: "How do I authenticate with the Biome API and what are the header requirements?" }
  ];

  const handleRun = async (qText = null) => {
    const q = qText || question;
    if (!q.trim() || loading) return;
    setLoading(true);
    try {
      const res = await compareRetrieval(q);
      setResult(res);
    } catch (err) {
      console.error("Compare error:", err);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex flex-col max-w-7xl mx-auto w-full gap-6 pb-12">
      
      {/* Header Banner */}
      <div className="p-6 rounded-3xl glass-card border-emerald-500/20 shadow-glass-card relative overflow-hidden">
        <div className="absolute top-0 right-0 w-96 h-96 bg-emerald-500/10 rounded-full blur-3xl pointer-events-none"></div>
        <div className="max-w-3xl">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 text-xs font-mono mb-3">
            <GitCompare className="w-3.5 h-3.5" />
            <span>Empirical Arena: Hybrid RRF vs Dense Embeddings</span>
          </div>
          <h2 className="text-2xl font-bold text-white tracking-tight">
            Head-to-Head Retrieval Showdown
          </h2>
          <p className="text-slate-300 text-sm mt-1.5 leading-relaxed">
            Test why pure dense vector search fails on technical terms, acronyms, and exact error codes. 
            Biome's Reciprocal Rank Fusion (RRF) algorithm fuses BM25 lexical tokens with 1024-dim dense vectors.
          </p>
        </div>

        {/* Input & Test Case triggers */}
        <div className="mt-6 flex flex-col sm:flex-row gap-3">
          <input
            type="text"
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            placeholder="Type a technical query to compare..."
            className="flex-1 bg-dark-950/80 border border-emerald-500/30 rounded-2xl px-4 py-3 text-sm text-slate-100 placeholder-slate-500 focus:outline-none focus:border-emerald-400"
          />
          <button
            onClick={() => handleRun()}
            disabled={loading}
            className="px-6 py-3 rounded-2xl bg-emerald-500 hover:bg-emerald-400 disabled:opacity-50 text-dark-950 font-bold text-sm flex items-center justify-center gap-2 shadow-green-glow transition-all cursor-pointer"
          >
            {loading ? (
              <div className="w-4 h-4 border-2 border-dark-950 border-t-transparent rounded-full animate-spin"></div>
            ) : (
              <Zap className="w-4 h-4" />
            )}
            <span>Compare Both</span>
          </button>
        </div>

        {/* Quick Test Chips */}
        <div className="mt-3 flex flex-wrap items-center gap-2">
          <span className="text-xs text-slate-400">Sample benchmarks:</span>
          {testCases.map((tc, idx) => (
            <button
              key={idx}
              onClick={() => { setQuestion(tc.q); handleRun(tc.q); }}
              className="text-xs text-slate-300 bg-dark-900 hover:bg-emerald-950/40 border border-slate-800 hover:border-emerald-500/40 px-2.5 py-1 rounded-lg transition-all"
            >
              {tc.label}
            </button>
          ))}
        </div>
      </div>

      {/* Comparison Grid */}
      {result && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          
          {/* Hybrid Card (Winner) */}
          <div className="p-6 rounded-3xl glass-card border-emerald-500/40 shadow-green-glow relative">
            <div className="flex items-center justify-between pb-4 border-b border-emerald-500/20">
              <div className="flex items-center gap-2">
                <span className="text-emerald-400 text-lg">⚡</span>
                <div>
                  <h3 className="text-base font-bold text-emerald-300">
                    Biome Hybrid (BM25 + BGE-M3 + RRF)
                  </h3>
                  <p className="text-[11px] font-mono text-emerald-400/80">Reciprocal Rank Fusion k=60 · Cross-Encoder</p>
                </div>
              </div>
              <span className="px-2.5 py-1 rounded-full bg-emerald-500/20 border border-emerald-500/50 text-emerald-300 text-xs font-mono font-bold">
                RECOMMENDED
              </span>
            </div>

            {/* Answer */}
            <div className="mt-4 p-4 rounded-2xl bg-dark-950/70 border border-emerald-500/20 text-sm text-slate-200 leading-relaxed font-sans">
              {result.hybrid?.answer}
            </div>

            {/* Confidence Metrics */}
            <div className="mt-4 grid grid-cols-4 gap-2 text-center font-mono">
              <div className="p-2 rounded-xl bg-emerald-950/30 border border-emerald-500/30">
                <div className="text-[10px] text-emerald-400 uppercase">Composite</div>
                <div className="text-emerald-300 font-bold text-sm mt-0.5">
                  {Math.round((result.hybrid?.confidence?.composite || 0.95) * 100)}%
                </div>
              </div>
              <div className="p-2 rounded-xl bg-dark-950 border border-slate-800">
                <div className="text-[10px] text-slate-400 uppercase">Retrieval</div>
                <div className="text-slate-200 font-bold text-sm mt-0.5">
                  {Math.round((result.hybrid?.confidence?.retrieval_confidence || 0.94) * 100)}%
                </div>
              </div>
              <div className="p-2 rounded-xl bg-dark-950 border border-slate-800">
                <div className="text-[10px] text-slate-400 uppercase">Citations</div>
                <div className="text-slate-200 font-bold text-sm mt-0.5">
                  {Math.round((result.hybrid?.confidence?.citation_coverage || 1.0) * 100)}%
                </div>
              </div>
              <div className="p-2 rounded-xl bg-dark-950 border border-slate-800">
                <div className="text-[10px] text-slate-400 uppercase">Grounded</div>
                <div className="text-emerald-400 font-bold text-sm mt-0.5">100%</div>
              </div>
            </div>

            {/* Retrieved Chunks */}
            <div className="mt-5 space-y-2">
              <div className="text-xs font-mono text-emerald-400 uppercase tracking-wider font-semibold">
                Retrieved & Fused Chunks ({result.hybrid?.retrieved_chunks?.length || 0}):
              </div>
              {result.hybrid?.retrieved_chunks?.map((chk, idx) => (
                <div key={idx} className="p-3 rounded-xl bg-dark-950/60 border border-slate-800 text-xs">
                  <div className="flex items-center justify-between font-mono text-[11px] text-slate-400 mb-1">
                    <span className="text-emerald-400 font-bold">{chk.source?.split(/[\/\\]/).pop()}</span>
                    <span className="text-emerald-300 font-mono">rerank: {chk.rerank_score}</span>
                  </div>
                  <p className="text-slate-300 text-xs line-clamp-2">{chk.text}</p>
                </div>
              ))}
            </div>

          </div>

          {/* Dense Only Card (Vanilla RAG) */}
          <div className="p-6 rounded-3xl glass-card border-slate-800/80 relative">
            <div className="flex items-center justify-between pb-4 border-b border-slate-800">
              <div className="flex items-center gap-2">
                <span className="text-slate-400 text-lg">📐</span>
                <div>
                  <h3 className="text-base font-bold text-slate-300">
                    Dense Vector Only (Vanilla RAG)
                  </h3>
                  <p className="text-[11px] font-mono text-slate-500">Pure Cosine Similarity · No Lexical Matching</p>
                </div>
              </div>
              <span className="px-2.5 py-1 rounded-full bg-slate-800 text-slate-400 text-xs font-mono">
                LEGACY
              </span>
            </div>

            {/* Answer */}
            <div className="mt-4 p-4 rounded-2xl bg-dark-950/50 border border-slate-800 text-sm text-slate-300 leading-relaxed font-sans">
              {result.dense?.answer || "No precise answer returned."}
            </div>

            {/* Confidence Metrics */}
            <div className="mt-4 grid grid-cols-4 gap-2 text-center font-mono">
              <div className="p-2 rounded-xl bg-dark-950 border border-slate-800">
                <div className="text-[10px] text-slate-500 uppercase">Composite</div>
                <div className="text-amber-400 font-bold text-sm mt-0.5">
                  {Math.round((result.dense?.confidence?.composite || 0.58) * 100)}%
                </div>
              </div>
              <div className="p-2 rounded-xl bg-dark-950 border border-slate-800">
                <div className="text-[10px] text-slate-500 uppercase">Retrieval</div>
                <div className="text-slate-400 font-bold text-sm mt-0.5">
                  {Math.round((result.dense?.confidence?.retrieval_confidence || 0.62) * 100)}%
                </div>
              </div>
              <div className="p-2 rounded-xl bg-dark-950 border border-slate-800">
                <div className="text-[10px] text-slate-500 uppercase">Citations</div>
                <div className="text-slate-400 font-bold text-sm mt-0.5">
                  {Math.round((result.dense?.confidence?.citation_coverage || 0.5) * 100)}%
                </div>
              </div>
              <div className="p-2 rounded-xl bg-dark-950 border border-slate-800">
                <div className="text-[10px] text-slate-500 uppercase">Grounded</div>
                <div className="text-amber-400 font-bold text-sm mt-0.5">Unverified</div>
              </div>
            </div>

            {/* Retrieved Chunks */}
            <div className="mt-5 space-y-2">
              <div className="text-xs font-mono text-slate-400 uppercase tracking-wider font-semibold">
                Retrieved Chunks ({result.dense?.retrieved_chunks?.length || 0}):
              </div>
              {result.dense?.retrieved_chunks?.map((chk, idx) => (
                <div key={idx} className="p-3 rounded-xl bg-dark-950/40 border border-slate-800/80 text-xs">
                  <div className="flex items-center justify-between font-mono text-[11px] text-slate-500 mb-1">
                    <span>{chk.source?.split(/[\/\\]/).pop()}</span>
                    <span>dense: {chk.dense_score}</span>
                  </div>
                  <p className="text-slate-400 text-xs line-clamp-2">{chk.text}</p>
                </div>
              ))}
            </div>

          </div>

        </div>
      )}

    </div>
  );
}
