import React, { useState } from 'react';
import { 
  Database, 
  Terminal, 
  ShieldAlert, 
  ShieldCheck, 
  Play, 
  Table, 
  Copy, 
  Check, 
  HelpCircle,
  Lock
} from 'lucide-react';
import { askQuestion } from '../../services/api';

export default function SqlView() {
  const [query, setQuery] = useState('How many open tickets are there grouped by department?');
  const [accessScope, setAccessScope] = useState(['engineering', 'support']);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [copied, setCopied] = useState(false);

  const sampleQueries = [
    "How many tickets are open grouped by status?",
    "Show urgent tickets for engineering department",
    "List all resolved tickets with priority high",
    "Count of tickets created in the last quarter"
  ];

  const handleExecute = async (qText = null) => {
    const q = qText || query;
    if (!q.trim() || loading) return;
    setLoading(true);
    try {
      const res = await askQuestion(q, 'hybrid', accessScope, 'structured');
      setResult(res);
    } catch (err) {
      console.error("SQL query error:", err);
    } finally {
      setLoading(false);
    }
  };

  const handleCopy = (text) => {
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="flex flex-col max-w-7xl mx-auto w-full gap-6 pb-12">
      
      {/* Header Banner */}
      <div className="p-6 rounded-3xl glass-card border-emerald-500/20 shadow-glass-card">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 text-xs font-mono mb-2">
              <Database className="w-3.5 h-3.5" />
              <span>Phase 8: Sandboxed Natural Language to SQL + Programmatic ACL</span>
            </div>
            <h2 className="text-2xl font-bold text-white tracking-tight">
              Relational NL2SQL Studio
            </h2>
            <p className="text-slate-300 text-sm mt-1 max-w-2xl">
              Convert business questions into verified read-only SQL queries executed in an AST-sandboxed environment with programmatic Row-Level Access Control (ACL).
            </p>
          </div>

          {/* Department ACL Selector */}
          <div className="p-3 rounded-2xl bg-dark-950/80 border border-slate-800 flex flex-col gap-2">
            <div className="flex items-center gap-1.5 text-xs text-slate-400 font-mono">
              <Lock className="w-3 h-3 text-emerald-400" />
              <span>Row-Level ACL Scope:</span>
            </div>
            <div className="flex flex-wrap gap-1.5">
              {['engineering', 'support', 'billing', 'executive', 'logistics'].map(scope => {
                const active = accessScope.includes(scope);
                return (
                  <button
                    key={scope}
                    onClick={() => {
                      if (active) {
                        setAccessScope(accessScope.filter(s => s !== scope));
                      } else {
                        setAccessScope([...accessScope, scope]);
                      }
                    }}
                    className={`px-2.5 py-1 rounded-lg text-xs font-mono font-medium transition-all border ${
                      active
                        ? 'bg-emerald-500/20 border-emerald-500/50 text-emerald-300 shadow-green-glow-subtle'
                        : 'bg-dark-900 border-slate-800 text-slate-500 hover:text-slate-300'
                    }`}
                  >
                    {scope}
                  </button>
                );
              })}
            </div>
          </div>
        </div>

        {/* Query Input */}
        <div className="mt-6 flex flex-col sm:flex-row gap-3">
          <div className="relative flex-1">
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Ask a question about database records..."
              className="w-full bg-dark-950 border border-emerald-500/30 rounded-2xl pl-4 pr-10 py-3.5 text-sm text-slate-100 placeholder-slate-500 focus:outline-none focus:border-emerald-400"
            />
          </div>
          <button
            onClick={() => handleExecute()}
            disabled={loading}
            className="px-6 py-3.5 rounded-2xl bg-emerald-500 hover:bg-emerald-400 disabled:opacity-50 text-dark-950 font-bold text-sm flex items-center justify-center gap-2 shadow-green-glow transition-all cursor-pointer"
          >
            {loading ? (
              <div className="w-4 h-4 border-2 border-dark-950 border-t-transparent rounded-full animate-spin"></div>
            ) : (
              <Play className="w-4 h-4 fill-dark-950" />
            )}
            <span>Generate & Execute</span>
          </button>
        </div>

        {/* Sample questions */}
        <div className="mt-3 flex flex-wrap items-center gap-2">
          <span className="text-xs text-slate-400 flex items-center gap-1">
            <HelpCircle className="w-3 h-3 text-emerald-400" />
            <span>Sample Queries:</span>
          </span>
          {sampleQueries.map((sq, i) => (
            <button
              key={i}
              onClick={() => { setQuery(sq); handleExecute(sq); }}
              className="text-xs text-slate-300 bg-dark-900 hover:bg-emerald-950/40 border border-slate-800 hover:border-emerald-500/40 px-2.5 py-1 rounded-lg transition-all"
            >
              {sq}
            </button>
          ))}
        </div>
      </div>

      {/* Results Container */}
      {result && (
        <div className="space-y-6">
          
          {/* Answer & SQL Code Card */}
          <div className="p-6 rounded-3xl glass-card border-emerald-500/30 shadow-glass-card">
            
            {/* Natural language summary */}
            <div className="text-xs font-mono uppercase text-emerald-400 font-bold mb-2">
              Synthesized Database Insight:
            </div>
            <div className="p-4 rounded-2xl bg-dark-950/70 border border-emerald-500/20 text-slate-200 text-sm leading-relaxed">
              {result.answer}
            </div>

            {/* Generated SQL Code Box */}
            {result.sql_query && (
              <div className="mt-4">
                <div className="flex items-center justify-between text-xs font-mono text-slate-400 mb-1.5">
                  <span className="flex items-center gap-1.5 text-emerald-300">
                    <Terminal className="w-3.5 h-3.5" />
                    <span>AST-Validated Sandboxed SQL:</span>
                  </span>
                  <button
                    onClick={() => handleCopy(result.sql_query)}
                    className="flex items-center gap-1 text-slate-400 hover:text-white"
                  >
                    {copied ? <Check className="w-3 h-3 text-emerald-400" /> : <Copy className="w-3 h-3" />}
                    <span>{copied ? 'Copied' : 'Copy'}</span>
                  </button>
                </div>
                <pre className="p-3.5 rounded-xl bg-dark-950 text-emerald-300 font-mono text-xs overflow-x-auto border border-emerald-500/30 shadow-inner">
                  {result.sql_query}
                </pre>
              </div>
            )}

            {/* Programmatic ACL Verification Badge */}
            <div className="mt-4 flex items-center justify-between p-3 rounded-xl bg-emerald-950/30 border border-emerald-500/30 text-xs font-mono">
              <div className="flex items-center gap-2 text-emerald-300">
                <ShieldCheck className="w-4 h-4 text-emerald-400" />
                <span>Programmatic ACL Filter Applied: <strong>[{accessScope.join(', ')}]</strong></span>
              </div>
              <span className="text-slate-400">Strict Read-Only AST Protection · Zero DDL/DML Allowed</span>
            </div>

          </div>

          {/* Tabular Rows */}
          {result.sql_rows && result.sql_rows.length > 0 && (
            <div className="p-6 rounded-3xl glass-card border-slate-800">
              <div className="flex items-center gap-2 mb-4 text-sm font-bold text-white font-mono">
                <Table className="w-4 h-4 text-emerald-400" />
                <span>Returned Records ({result.sql_rows.length} rows):</span>
              </div>
              <div className="overflow-x-auto rounded-2xl border border-slate-800">
                <table className="min-w-full text-xs font-mono text-left">
                  <thead className="bg-dark-950 text-slate-400 border-b border-slate-800">
                    <tr>
                      {Object.keys(result.sql_rows[0]).map(col => (
                        <th key={col} className="px-4 py-3 uppercase tracking-wider text-[11px] font-semibold">
                          {col}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-800/60 bg-dark-900/50">
                    {result.sql_rows.map((row, rIdx) => (
                      <tr key={rIdx} className="hover:bg-slate-900/60 transition-colors">
                        {Object.values(row).map((val, cIdx) => (
                          <td key={cIdx} className="px-4 py-2.5 text-slate-200">
                            {String(val)}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

        </div>
      )}

    </div>
  );
}
