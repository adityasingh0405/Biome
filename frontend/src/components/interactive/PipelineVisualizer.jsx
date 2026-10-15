import React, { useState, useEffect } from 'react';
import { 
  Layers, 
  Cpu, 
  Database, 
  ShieldCheck, 
  Activity,
  ArrowRight
} from 'lucide-react';

const stages = [
  {
    id: "ingest",
    step: "01",
    label: "Layout Parsing",
    shortTag: "PARSING",
    cue: "Tables, OCR scans & chat threads preserved intact.",
    icon: Layers,
    stats: [
      { label: "INTEGRITY", val: "100%" },
      { label: "THROUGHPUT", val: "1,400 P/M" },
      { label: "BLEED", val: "0.0%" }
    ],
    signal: "PARSING ACTIVE"
  },
  {
    id: "embed",
    step: "02",
    label: "Dual Encoding",
    shortTag: "ENCODING",
    cue: "Concurrent dense vectors + exact lexical tokens.",
    icon: Cpu,
    stats: [
      { label: "DENSE DIM", val: "1024-D" },
      { label: "LEXICAL", val: "EXACT" },
      { label: "LATENCY", val: "<12MS" }
    ],
    signal: "DUAL SYNCED"
  },
  {
    id: "graph",
    step: "03",
    label: "Graph Traversal",
    shortTag: "TRAVERSAL",
    cue: "Sub-50ms graph search with zero-leak tenant isolation.",
    icon: Database,
    stats: [
      { label: "SEARCH", val: "18MS" },
      { label: "CAPACITY", val: "100M+" },
      { label: "ISOLATION", val: "HARDENED" }
    ],
    signal: "GRAPH ACTIVE"
  },
  {
    id: "rerank",
    step: "04",
    label: "Cross-Attention",
    shortTag: "VERIFICATION",
    cue: "Deep score fusion with 100% sentence-level verbatim proof.",
    icon: ShieldCheck,
    stats: [
      { label: "PROOF", val: "100%" },
      { label: "PRECISION", val: "99.4%" },
      { label: "HALLUCINATION", val: "0.0%" }
    ],
    signal: "100% VERIFIED"
  }
];

export default function PipelineVisualizer() {
  const [activeStage, setActiveStage] = useState(0);
  const [autoPlay, setAutoPlay] = useState(true);

  useEffect(() => {
    if (!autoPlay) return;
    const interval = setInterval(() => {
      setActiveStage((prev) => (prev + 1) % stages.length);
    }, 4000);
    return () => clearInterval(interval);
  }, [autoPlay]);

  const current = stages[activeStage];
  const CurrentIcon = current.icon;

  return (
    <div className="w-full flex flex-col items-center">
      
      {/* Sharp Stepper Nodes */}
      <div className="w-full grid grid-cols-2 md:grid-cols-4 gap-2 mb-4">
        {stages.map((stage, idx) => {
          const Icon = stage.icon;
          const isActive = activeStage === idx;
          return (
            <button
              key={stage.id}
              onClick={() => {
                setActiveStage(idx);
                setAutoPlay(false);
              }}
              className={`p-3.5 rounded-none transition-all text-left relative overflow-hidden border cursor-pointer ${
                isActive
                  ? 'bg-emerald-950/80 border-emerald-400 shadow-green-glow'
                  : 'bg-[#040810] border-slate-800 hover:border-emerald-500/40'
              }`}
            >
              {/* Active top neon line */}
              {isActive && (
                <div className="absolute top-0 left-0 right-0 h-[2px] bg-emerald-400 shadow-green-glow" />
              )}

              <div className="flex items-center justify-between mb-1.5 font-tech text-xs">
                <span className="text-slate-500 font-bold">{stage.step}</span>
                <span className={`px-1.5 py-0.5 text-[9px] font-black uppercase tracking-wider rounded-none ${
                  isActive ? 'bg-emerald-400 text-dark-950' : 'bg-dark-950 text-slate-500 border border-slate-800'
                }`}>
                  {stage.shortTag}
                </span>
              </div>

              <div className="flex items-center gap-2">
                <div className={`w-7 h-7 rounded-none flex items-center justify-center flex-shrink-0 border ${
                  isActive 
                    ? 'bg-emerald-400 text-dark-950 border-emerald-300' 
                    : 'bg-dark-950 text-slate-400 border-slate-800'
                }`}>
                  <Icon className="w-3.5 h-3.5" />
                </div>
                <div className="text-xs font-bold text-white truncate font-tech uppercase tracking-wide">
                  {stage.label}
                </div>
              </div>
            </button>
          );
        })}
      </div>

      {/* Sharp HUD Telemetry Console */}
      <div className="w-full hud-panel p-6 sm:p-7 bg-[#040810] relative overflow-hidden">
        
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-center">
          
          {/* Left: Active Stage Details (Minimal, Sharp) */}
          <div className="lg:col-span-5 flex flex-col items-start space-y-3">
            <div className="inline-flex items-center gap-2 px-2.5 py-0.5 rounded-none bg-emerald-500/10 border border-emerald-500/40 text-emerald-400 text-xs font-tech tracking-wider uppercase">
              <Activity className="w-3 h-3 animate-spin" />
              <span>{current.signal}</span>
            </div>

            <div className="flex items-center gap-3">
              <div className="w-12 h-12 rounded-none bg-emerald-400 text-dark-950 font-black flex items-center justify-center shadow-green-glow border border-white">
                <CurrentIcon className="w-6 h-6" />
              </div>
              <div>
                <div className="text-[10px] font-tech text-slate-500 uppercase tracking-widest">
                  STAGE // {current.step} OF 04
                </div>
                <div className="text-xl sm:text-2xl font-display font-bold text-white uppercase tracking-tight">
                  {current.label}
                </div>
              </div>
            </div>

            <p className="text-xs text-emerald-300 font-tech uppercase tracking-wide">
              &gt; {current.cue}
            </p>
          </div>

          {/* Right: 3 Sharp Metric Tiles */}
          <div className="lg:col-span-7 grid grid-cols-3 gap-2.5">
            {current.stats.map((st, i) => (
              <div 
                key={i} 
                className="p-3.5 rounded-none bg-[#020408] border border-emerald-500/30 flex flex-col justify-between"
              >
                <div className="text-[10px] font-tech text-slate-500 uppercase tracking-wider">
                  {st.label}
                </div>
                <div className="text-xl sm:text-2xl font-display font-bold text-white my-1 tracking-tight">
                  {st.val}
                </div>
                <div className="w-full bg-slate-900 h-[2px] overflow-hidden">
                  <div className="bg-emerald-400 h-full w-full animate-pulse" />
                </div>
              </div>
            ))}
          </div>

        </div>

        {/* Sharp Bottom Telemetry Line */}
        <div className="mt-5 pt-3 border-t border-slate-800 flex flex-wrap items-center justify-between gap-3 text-[11px] font-tech text-slate-400 uppercase tracking-wider">
          <div className="flex items-center gap-2 text-emerald-400">
            <span className="w-1.5 h-1.5 bg-emerald-400 animate-ping"></span>
            <span>PIPELINE LATENCY: &lt;68MS TOTAL</span>
          </div>
          <div className="flex items-center gap-3">
            <span>ZERO-LEAK PAYLOAD ISOLATION</span>
            <span className="text-slate-700">·</span>
            <span className="text-emerald-300 font-bold">100% GROUNDED</span>
          </div>
        </div>

      </div>

    </div>
  );
}
