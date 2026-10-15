import React, { useState, useRef, useEffect } from 'react';
import { 
  Send, 
  Trash2, 
  CheckCircle2, 
  AlertCircle, 
  ChevronDown, 
  ChevronUp, 
  Sparkles, 
  Database, 
  FileText, 
  Shield, 
  Cpu,
  Layers,
  HelpCircle,
  Copy,
  Check
} from 'lucide-react';
import { sendChatMessage, clearSession } from '../../services/api';

export default function ChatView() {
  const [messages, setMessages] = useState([
    {
      role: 'assistant',
      content: 'Welcome to Biome Enterprise Search. Ask any question across your indexed documentation, architecture guides, and relational records.',
      citations: [],
      confidence: null,
      retrieved_chunks: [],
      route: 'semantic',
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    }
  ]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [sessionId, setSessionId] = useState(() => 'sess_' + Math.random().toString(36).substring(2, 9));
  const [retrievalMode, setRetrievalMode] = useState('hybrid');
  const [routeOverride, setRouteOverride] = useState('auto');
  const [accessScope, setAccessScope] = useState(['engineering']);
  const [selectedCitation, setSelectedCitation] = useState(null);
  const [copiedSql, setCopiedSql] = useState(false);
  const messagesEndRef = useRef(null);

  const sampleQuestions = [
    "How do I authenticate with the Biome API?",
    "What error code indicates invalid credentials?",
    "How many open tickets are currently logged?",
    "What is the deployment target error code?"
  ];

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, loading]);

  const handleSend = async (questionText = null) => {
    const query = questionText || input;
    if (!query.trim() || loading) return;

    const userMsg = {
      role: 'user',
      content: query,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    };

    setMessages(prev => [...prev, userMsg]);
    if (!questionText) setInput('');
    setLoading(true);

    try {
      const res = await sendChatMessage(
        query,
        sessionId,
        retrievalMode,
        accessScope,
        routeOverride === 'auto' ? null : routeOverride
      );

      const assistantMsg = {
        role: 'assistant',
        content: res.answer,
        citations: res.citations || [],
        confidence: res.confidence || null,
        retrieved_chunks: res.retrieved_chunks || [],
        route: res.route || 'semantic',
        sql_query: res.sql_query || null,
        sql_rows: res.sql_rows || null,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      };

      setMessages(prev => [...prev, assistantMsg]);
    } catch (err) {
      console.error("Chat error:", err);
      setMessages(prev => [
        ...prev,
        {
          role: 'assistant',
          content: 'An error occurred while querying the retrieval engine. Please check your backend connection.',
          citations: [],
          confidence: null,
          retrieved_chunks: [],
          route: 'semantic',
          timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        }
      ]);
    } finally {
      setLoading(false);
    }
  };

  const handleClear = async () => {
    await clearSession(sessionId);
    const newId = 'sess_' + Math.random().toString(36).substring(2, 9);
    setSessionId(newId);
    setMessages([
      {
        role: 'assistant',
        content: 'Session memory cleared. You can start a fresh conversation context.',
        citations: [],
        confidence: null,
        retrieved_chunks: [],
        route: 'semantic',
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      }
    ]);
  };

  const handleCopySql = (sql) => {
    navigator.clipboard.writeText(sql);
    setCopiedSql(true);
    setTimeout(() => setCopiedSql(false), 2000);
  };

  // Helper to parse [n] or [n✓] citations inside text
  const renderTextWithCitations = (text, citations = []) => {
    if (!citations || citations.length === 0) return text;

    const parts = text.split(/(\[\d+(?:[✓~])?\])/g);
    return parts.map((part, i) => {
      const match = part.match(/\[(\d+)(?:[✓~])?\]/);
      if (match) {
        const num = parseInt(match[1], 10);
        const cit = citations.find(c => c.chunk_index + 1 === num) || citations[num - 1];
        const isVerified = cit ? cit.verified : true;

        return (
          <button
            key={i}
            onClick={() => setSelectedCitation(cit || { chunk_index: num - 1, text: "Source citation passage.", verified: isVerified })}
            className={`inline-flex items-center gap-0.5 px-1.5 py-0.2 mx-0.5 text-[11px] font-mono font-semibold rounded transition-all cursor-pointer ${
              isVerified 
                ? 'bg-emerald-500/15 border border-emerald-500/40 text-emerald-300 hover:bg-emerald-500/30' 
                : 'bg-amber-500/15 border border-amber-500/40 text-amber-300 hover:bg-amber-500/30'
            }`}
            title={`Citation [${num}] — ${isVerified ? 'Verified Grounded' : 'Unverified'}`}
          >
            <span>[{num}{isVerified ? '✓' : '~'}]</span>
          </button>
        );
      }
      return part;
    });
  };

  return (
    <div className="flex flex-col h-[calc(100vh-8.5rem)] max-w-7xl mx-auto w-full gap-4">
      
      {/* Settings Bar */}
      <div className="flex flex-wrap items-center justify-between gap-3 p-3 rounded-2xl bg-dark-900/80 border border-emerald-500/20 backdrop-blur-xl">
        <div className="flex flex-wrap items-center gap-4 text-xs">
          
          {/* Mode selector */}
          <div className="flex items-center gap-2">
            <span className="text-slate-400 font-medium">Retrieval:</span>
            <div className="flex rounded-lg bg-dark-950 p-0.5 border border-slate-800">
              {['hybrid', 'dense', 'sparse'].map(m => (
                <button
                  key={m}
                  onClick={() => setRetrievalMode(m)}
                  className={`px-2.5 py-1 rounded-md capitalize font-medium transition-all ${
                    retrievalMode === m 
                      ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/40 shadow-green-glow-subtle' 
                      : 'text-slate-400 hover:text-slate-200'
                  }`}
                >
                  {m}
                </button>
              ))}
            </div>
          </div>

          {/* Route override */}
          <div className="flex items-center gap-2">
            <span className="text-slate-400 font-medium">Route:</span>
            <select
              value={routeOverride}
              onChange={(e) => setRouteOverride(e.target.value)}
              className="bg-dark-950 border border-slate-800 rounded-lg px-2.5 py-1 text-slate-200 text-xs focus:outline-none focus:border-emerald-500/50"
            >
              <option value="auto">Auto Router (Phase 8)</option>
              <option value="structured">Force SQL (Structured)</option>
              <option value="semantic">Force RAG (Semantic)</option>
            </select>
          </div>

          {/* ACL Scope */}
          <div className="flex items-center gap-2">
            <span className="text-slate-400 font-medium">Scope:</span>
            {['engineering', 'support', 'billing', 'executive'].map(s => {
              const active = accessScope.includes(s);
              return (
                <button
                  key={s}
                  onClick={() => {
                    if (active) {
                      setAccessScope(accessScope.filter(x => x !== s));
                    } else {
                      setAccessScope([...accessScope, s]);
                    }
                  }}
                  className={`px-2 py-0.5 rounded text-[11px] font-mono transition-all border ${
                    active 
                      ? 'bg-emerald-950/40 border-emerald-500/40 text-emerald-300' 
                      : 'bg-dark-950/50 border-slate-800 text-slate-500 hover:text-slate-300'
                  }`}
                >
                  {s}
                </button>
              );
            })}
          </div>

        </div>

        {/* Right Session Action */}
        <div className="flex items-center gap-2">
          <span className="text-[11px] font-mono text-slate-500 hidden sm:inline">Session: {sessionId.slice(0, 10)}</span>
          <button
            onClick={handleClear}
            className="flex items-center gap-1 text-xs text-slate-400 hover:text-red-400 px-2.5 py-1 rounded-lg border border-slate-800 hover:border-red-500/30 transition-all"
            title="Clear Redis multi-turn session memory"
          >
            <Trash2 className="w-3.5 h-3.5" />
            <span>Reset</span>
          </button>
        </div>
      </div>

      {/* Messages Stream */}
      <div className="flex-1 overflow-y-auto space-y-4 pr-2">
        {messages.map((msg, idx) => (
          <div 
            key={idx} 
            className={`flex flex-col ${msg.role === 'user' ? 'items-end' : 'items-start'}`}
          >
            <div className="flex items-center gap-2 mb-1 px-1">
              <span className="text-[11px] font-mono text-slate-500 uppercase tracking-wider">
                {msg.role === 'user' ? 'You' : 'Biome Assistant'}
              </span>
              <span className="text-[10px] text-slate-600">{msg.timestamp}</span>
              {msg.route && msg.role === 'assistant' && (
                <span className={`text-[10px] font-mono px-1.5 py-0.2 rounded border ${
                  msg.route === 'structured' 
                    ? 'bg-cyan-500/10 border-cyan-500/30 text-cyan-400' 
                    : 'bg-emerald-500/10 border-emerald-500/30 text-emerald-400'
                }`}>
                  {msg.route === 'structured' ? '🗄️ SQL Route' : '⚡ Semantic RAG'}
                </span>
              )}
            </div>

            <div className={`rounded-2xl p-4.5 max-w-3xl leading-relaxed text-sm backdrop-blur-xl ${
              msg.role === 'user' 
                ? 'bg-gradient-to-r from-emerald-600/30 to-emerald-700/20 border border-emerald-500/30 text-emerald-50' 
                : 'glass-card text-slate-200 border-emerald-500/20 shadow-glass-card'
            }`}>
              
              {/* Answer Content */}
              <div className="whitespace-pre-wrap">
                {msg.role === 'assistant' ? renderTextWithCitations(msg.content, msg.citations) : msg.content}
              </div>

              {/* SQL Result Box if Route was Structured */}
              {msg.sql_query && (
                <div className="mt-3.5 pt-3 border-t border-slate-800">
                  <div className="flex items-center justify-between mb-1.5 text-xs text-cyan-400 font-mono">
                    <div className="flex items-center gap-1.5">
                      <Database className="w-3.5 h-3.5 text-cyan-400" />
                      <span>Executed Relational Query:</span>
                    </div>
                    <button
                      onClick={() => handleCopySql(msg.sql_query)}
                      className="hover:text-cyan-300 flex items-center gap-1 text-[11px]"
                    >
                      {copiedSql ? <Check className="w-3 h-3 text-emerald-400" /> : <Copy className="w-3 h-3" />}
                      <span>{copiedSql ? 'Copied' : 'Copy SQL'}</span>
                    </button>
                  </div>
                  <pre className="p-2.5 rounded-lg bg-dark-950 text-cyan-300 font-mono text-xs overflow-x-auto border border-cyan-500/20">
                    {msg.sql_query}
                  </pre>
                  {msg.sql_rows && msg.sql_rows.length > 0 && (
                    <div className="mt-2 overflow-x-auto">
                      <table className="min-w-full text-xs font-mono text-slate-300 border border-slate-800 rounded">
                        <thead className="bg-dark-950 text-slate-400 border-b border-slate-800">
                          <tr>
                            {Object.keys(msg.sql_rows[0]).map(k => (
                              <th key={k} className="px-3 py-1.5 text-left">{k}</th>
                            ))}
                          </tr>
                        </thead>
                        <tbody>
                          {msg.sql_rows.map((row, rIdx) => (
                            <tr key={rIdx} className="border-b border-slate-900/60 hover:bg-slate-900/40">
                              {Object.values(row).map((val, vIdx) => (
                                <td key={vIdx} className="px-3 py-1.5">{String(val)}</td>
                              ))}
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                </div>
              )}

              {/* Confidence Radar Metrics */}
              {msg.confidence && (
                <div className="mt-4 pt-3 border-t border-slate-800/80">
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-center font-mono text-xs">
                    <div className="p-2 rounded-lg bg-dark-950/60 border border-emerald-500/20">
                      <div className="text-slate-400 text-[10px] uppercase">Composite</div>
                      <div className="text-emerald-400 font-bold text-base mt-0.5">
                        {Math.round((msg.confidence.composite || 0) * 100)}%
                      </div>
                    </div>
                    <div className="p-2 rounded-lg bg-dark-950/60 border border-slate-800">
                      <div className="text-slate-400 text-[10px] uppercase">Retrieval</div>
                      <div className="text-slate-200 font-semibold text-base mt-0.5">
                        {Math.round((msg.confidence.retrieval_confidence || 0) * 100)}%
                      </div>
                    </div>
                    <div className="p-2 rounded-lg bg-dark-950/60 border border-slate-800">
                      <div className="text-slate-400 text-[10px] uppercase">Citations</div>
                      <div className="text-slate-200 font-semibold text-base mt-0.5">
                        {Math.round((msg.confidence.citation_coverage || 0) * 100)}%
                      </div>
                    </div>
                    <div className="p-2 rounded-lg bg-dark-950/60 border border-slate-800">
                      <div className="text-slate-400 text-[10px] uppercase">Completeness</div>
                      <div className="text-slate-200 font-semibold text-base mt-0.5">
                        {Math.round((msg.confidence.completeness || 0) * 100)}%
                      </div>
                    </div>
                  </div>
                </div>
              )}

              {/* Retrieved Chunks Accordion */}
              {msg.retrieved_chunks && msg.retrieved_chunks.length > 0 && (
                <details className="mt-3 text-xs group">
                  <summary className="cursor-pointer text-slate-400 hover:text-emerald-400 font-mono flex items-center gap-1.5 select-none py-1">
                    <Layers className="w-3.5 h-3.5 text-emerald-400" />
                    <span>View {msg.retrieved_chunks.length} Retrieved Chunks (Dense + Sparse + RRF)</span>
                  </summary>
                  <div className="mt-2 space-y-2">
                    {msg.retrieved_chunks.map((chk, cIdx) => (
                      <div key={cIdx} className="p-2.5 rounded-lg bg-dark-950/70 border border-slate-800 text-slate-300 text-xs">
                        <div className="flex items-center justify-between font-mono text-[10px] text-slate-400 mb-1.5">
                          <span className="text-emerald-400 font-semibold">#{cIdx + 1} {chk.source?.split(/[\/\\]/).pop()}</span>
                          <div className="flex gap-2">
                            {chk.dense_score !== undefined && <span>dense: {chk.dense_score}</span>}
                            {chk.sparse_score !== undefined && <span>sparse: {chk.sparse_score}</span>}
                            {chk.rerank_score !== undefined && <span className="text-emerald-400 font-semibold">rerank: {chk.rerank_score}</span>}
                          </div>
                        </div>
                        <p className="text-slate-300 font-sans text-xs line-clamp-3 hover:line-clamp-none transition-all">
                          {chk.text}
                        </p>
                      </div>
                    ))}
                  </div>
                </details>
              )}

            </div>
          </div>
        ))}

        {loading && (
          <div className="flex items-center gap-3 p-4 rounded-2xl glass-card max-w-md border-emerald-500/30">
            <div className="w-5 h-5 rounded-full border-2 border-emerald-400 border-t-transparent animate-spin"></div>
            <div className="text-xs text-emerald-300 font-mono animate-pulse">
              Synthesizing response · Checking citations · Computing confidence...
            </div>
          </div>
        )}
        
        <div ref={messagesEndRef} />
      </div>

      {/* Suggested Questions */}
      {messages.length <= 2 && !loading && (
        <div className="flex flex-wrap items-center gap-2 pt-1">
          <span className="text-xs text-slate-400 flex items-center gap-1">
            <HelpCircle className="w-3 h-3 text-emerald-400" />
            <span>Try:</span>
          </span>
          {sampleQuestions.map((q, i) => (
            <button
              key={i}
              onClick={() => handleSend(q)}
              className="text-xs font-medium text-slate-300 bg-dark-900/70 hover:bg-emerald-950/40 border border-slate-800 hover:border-emerald-500/40 rounded-lg px-3 py-1 transition-all"
            >
              {q}
            </button>
          ))}
        </div>
      )}

      {/* Input Bar */}
      <form 
        onSubmit={(e) => { e.preventDefault(); handleSend(); }}
        className="relative flex items-center"
      >
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask any question about enterprise documentation, architecture, or tickets..."
          disabled={loading}
          className="w-full bg-dark-900/90 border border-emerald-500/25 focus:border-emerald-400 rounded-2xl pl-4 pr-24 py-3.5 text-sm text-slate-100 placeholder-slate-500 focus:outline-none focus:ring-1 focus:ring-emerald-400/50 shadow-green-glow-subtle transition-all"
        />
        <div className="absolute right-2 flex items-center gap-1.5">
          <button
            type="submit"
            disabled={!input.trim() || loading}
            className="px-4 py-2 rounded-xl bg-emerald-500 hover:bg-emerald-400 disabled:opacity-40 disabled:hover:bg-emerald-500 text-dark-950 font-bold text-xs flex items-center gap-1.5 transition-all cursor-pointer shadow-green-glow"
          >
            <span>Ask</span>
            <Send className="w-3.5 h-3.5 text-dark-950" />
          </button>
        </div>
      </form>

      {/* Citation Detail Modal */}
      {selectedCitation && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm">
          <div className="glass-card max-w-xl w-full p-6 rounded-2xl border-emerald-500/40 shadow-green-glow">
            <div className="flex items-center justify-between pb-3 border-b border-slate-800">
              <div className="flex items-center gap-2">
                <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                <span className="font-mono text-sm font-semibold text-emerald-400">
                  Verified Citation [{selectedCitation.chunk_index + 1}]
                </span>
              </div>
              <button 
                onClick={() => setSelectedCitation(null)}
                className="text-slate-400 hover:text-white text-xs font-mono"
              >
                ✕ Close
              </button>
            </div>
            <div className="mt-4 p-4 rounded-xl bg-dark-950/80 border border-slate-800 text-sm text-slate-200 leading-relaxed font-sans">
              "{selectedCitation.text}"
            </div>
            <div className="mt-4 flex items-center justify-between text-xs text-slate-400 font-mono">
              <span>Status: <strong className="text-emerald-400">100% Substring Grounded</strong></span>
              <span>Chunk Index: #{selectedCitation.chunk_index}</span>
            </div>
          </div>
        </div>
      )}

    </div>
  );
}
