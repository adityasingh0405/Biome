import React, { useState } from 'react';
import { 
  BarChart3, 
  Award, 
  Layers, 
  Filter, 
  ArrowDownUp, 
  Zap,
  Activity,
  CheckCircle2
} from 'lucide-react';
import { ABLATION_STUDY } from '../../data/ablationData';

export default function AblationView() {
  const [filterMode, setFilterMode] = useState('all');
  const [filterRerank, setFilterRerank] = useState('all');
  const [filterK, setFilterK] = useState('all');

  const filteredArms = ABLATION_STUDY.arms.filter(arm => {
    if (filterMode !== 'all' && arm.mode !== filterMode) return false;
    if (filterRerank === 'yes' && !arm.rerank) return false;
    if (filterRerank === 'no' && arm.rerank) return false;
    if (filterK !== 'all' && arm.top_k !== parseInt(filterK, 10)) return false;
    return true;
  });

  return (
    <div className="flex flex-col max-w-7xl mx-auto w-full gap-6 pb-12">
      
      {/* Top Banner */}
      <div className="p-6 rounded-3xl glass-card border-emerald-500/20 shadow-glass-card">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 text-xs font-mono mb-2">
              <Award className="w-3.5 h-3.5" />
              <span>Phase 7 Benchmark: 18 Architectural Variations Evaluated</span>
            </div>
            <h2 className="text-2xl font-bold text-white tracking-tight">
              18-Arm Empirical Ablation Study
            </h2>
            <p className="text-slate-300 text-sm mt-1 max-w-2xl">
              Quantitative comparison across RAGAS/DeepEval metrics: Faithfulness, Context Precision, Recall, Hallucination penalty, and Latency on <code className="text-emerald-400 font-mono">eval/golden_dataset.json</code>.
            </p>
          </div>

          {/* Winner Pill */}
          <div className="p-4 rounded-2xl bg-emerald-950/40 border border-emerald-500/40 shadow-green-glow flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-emerald-500/20 border border-emerald-500/40 flex items-center justify-center text-emerald-400">
              <Award className="w-5 h-5" />
            </div>
            <div>
              <div className="text-[11px] font-mono text-emerald-400 font-bold uppercase tracking-wider">Winning Architecture</div>
              <div className="text-sm font-bold text-white font-mono">{ABLATION_STUDY.winner}</div>
              <div className="text-xs text-emerald-300 font-mono">Composite Score: <strong>{ABLATION_STUDY.winnerComposite}</strong></div>
            </div>
          </div>
        </div>

        {/* Filter Controls */}
        <div className="mt-6 flex flex-wrap items-center gap-4 pt-4 border-t border-slate-800 text-xs font-mono">
          <div className="flex items-center gap-2">
            <Filter className="w-3.5 h-3.5 text-emerald-400" />
            <span className="text-slate-400">Mode:</span>
            <select
              value={filterMode}
              onChange={(e) => setFilterMode(e.target.value)}
              className="bg-dark-950 border border-slate-800 rounded-lg px-2.5 py-1 text-slate-200 focus:outline-none focus:border-emerald-500/50"
            >
              <option value="all">All Modes (18)</option>
              <option value="hybrid">Hybrid Only</option>
              <option value="dense">Dense Only</option>
              <option value="sparse">Sparse Only</option>
            </select>
          </div>

          <div className="flex items-center gap-2">
            <span className="text-slate-400">Reranker:</span>
            <select
              value={filterRerank}
              onChange={(e) => setFilterRerank(e.target.value)}
              className="bg-dark-950 border border-slate-800 rounded-lg px-2.5 py-1 text-slate-200 focus:outline-none focus:border-emerald-500/50"
            >
              <option value="all">All</option>
              <option value="yes">With Reranker (✓)</option>
              <option value="no">Without Reranker (✗)</option>
            </select>
          </div>

          <div className="flex items-center gap-2">
            <span className="text-slate-400">Top-K:</span>
            <select
              value={filterK}
              onChange={(e) => setFilterK(e.target.value)}
              className="bg-dark-950 border border-slate-800 rounded-lg px-2.5 py-1 text-slate-200 focus:outline-none focus:border-emerald-500/50"
            >
              <option value="all">All (3, 5, 10)</option>
              <option value="3">Top-3</option>
              <option value="5">Top-5</option>
              <option value="10">Top-10</option>
            </select>
          </div>

          <div className="ml-auto text-slate-400">
            Showing <strong className="text-emerald-400">{filteredArms.length}</strong> of 18 arms
          </div>
        </div>
      </div>

      {/* Axis Breakdown Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {ABLATION_STUDY.axes.retrieval_mode.map((axis, i) => (
          <div key={i} className="p-4 rounded-2xl glass-card border-slate-800 flex items-center justify-between">
            <div>
              <div className="text-xs text-slate-400 font-medium">{axis.name}</div>
              <div className="text-lg font-bold text-white font-mono mt-1">
                {axis.composite} <span className="text-xs text-slate-500 font-normal">composite</span>
              </div>
            </div>
            <div className="text-right font-mono text-xs">
              <div className="text-emerald-400 font-semibold">{Math.round(axis.faithfulness * 100)}%</div>
              <div className="text-[10px] text-slate-500 uppercase">Faithfulness</div>
            </div>
          </div>
        ))}
      </div>

      {/* Full Results Table */}
      <div className="rounded-3xl glass-card border-slate-800 overflow-hidden shadow-glass-card">
        <div className="overflow-x-auto">
          <table className="min-w-full text-xs font-mono text-left">
            <thead className="bg-dark-950 text-slate-400 border-b border-slate-800 uppercase tracking-wider text-[10px]">
              <tr>
                <th className="px-4 py-3.5">Rank</th>
                <th className="px-4 py-3.5">Arm Identifier</th>
                <th className="px-4 py-3.5">Mode</th>
                <th className="px-4 py-3.5">Top-K</th>
                <th className="px-4 py-3.5">Rerank</th>
                <th className="px-4 py-3.5">Faithfulness</th>
                <th className="px-4 py-3.5">Ctx-Precision</th>
                <th className="px-4 py-3.5">Hallucination↓</th>
                <th className="px-4 py-3.5 text-right">Composite</th>
                <th className="px-4 py-3.5 text-right">Latency</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60 bg-dark-900/40">
              {filteredArms.map((arm) => {
                const isWinner = arm.rank === 1;
                return (
                  <tr 
                    key={arm.id}
                    className={`transition-colors ${
                      isWinner 
                        ? 'bg-emerald-950/30 hover:bg-emerald-950/40' 
                        : 'hover:bg-slate-900/60'
                    }`}
                  >
                    <td className="px-4 py-3 font-bold">
                      {isWinner ? (
                        <span className="inline-flex items-center gap-1 text-emerald-400 font-mono">
                          🏆 #1
                        </span>
                      ) : (
                        <span className="text-slate-500">#{arm.rank}</span>
                      )}
                    </td>
                    <td className="px-4 py-3 font-semibold text-slate-200">
                      <code className={`${isWinner ? 'text-emerald-300 font-bold' : 'text-slate-300'}`}>
                        {arm.id}
                      </code>
                    </td>
                    <td className="px-4 py-3 capitalize">
                      <span className={`px-2 py-0.5 rounded text-[11px] border ${
                        arm.mode === 'hybrid'
                          ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-300'
                          : arm.mode === 'dense'
                          ? 'bg-cyan-500/10 border-cyan-500/30 text-cyan-300'
                          : 'bg-slate-800 border-slate-700 text-slate-300'
                      }`}>
                        {arm.mode}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-slate-300">{arm.top_k}</td>
                    <td className="px-4 py-3">
                      {arm.rerank ? (
                        <span className="text-emerald-400 font-bold">✓</span>
                      ) : (
                        <span className="text-slate-600">✗</span>
                      )}
                    </td>
                    <td className="px-4 py-3 text-slate-300">{(arm.faithfulness * 100).toFixed(1)}%</td>
                    <td className="px-4 py-3 text-slate-300">{(arm.ctx_p * 100).toFixed(1)}%</td>
                    <td className="px-4 py-3 text-amber-400/90">{arm.hall}</td>
                    <td className="px-4 py-3 text-right">
                      <span className={`font-bold ${isWinner ? 'text-emerald-400 text-sm' : 'text-slate-200'}`}>
                        {arm.composite.toFixed(4)}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-right text-slate-400">
                      {(arm.latency_ms / 1000).toFixed(1)}s
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>

    </div>
  );
}
