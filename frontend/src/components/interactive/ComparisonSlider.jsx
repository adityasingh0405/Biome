import React, { useState, useRef } from 'react';
import { AlertCircle, CheckCircle2, ArrowLeftRight, XCircle } from 'lucide-react';

export default function ComparisonSlider() {
  const [sliderPosition, setSliderPosition] = useState(50);
  const containerRef = useRef(null);

  const handleMove = (clientX) => {
    if (!containerRef.current) return;
    const rect = containerRef.current.getBoundingClientRect();
    const x = Math.max(0, Math.min(clientX - rect.left, rect.width));
    const percent = Math.max(10, Math.min((x / rect.width) * 100, 90));
    setSliderPosition(percent);
  };

  const handleTouchMove = (e) => {
    handleMove(e.touches[0].clientX);
  };

  const handleMouseMove = (e) => {
    if (e.buttons === 1) {
      handleMove(e.clientX);
    }
  };

  return (
    <div className="w-full flex flex-col items-center">
      
      {/* Sharp Interactive Frame (Zero Curves) */}
      <div 
        ref={containerRef}
        onMouseMove={handleMouseMove}
        onTouchMove={handleTouchMove}
        onClick={(e) => handleMove(e.clientX)}
        className="relative w-full max-w-5xl h-[360px] sm:h-[300px] rounded-none overflow-hidden select-none cursor-ew-resize hud-panel border border-emerald-500/40 bg-[#03060c]"
      >
        
        {/* Right Pane: WITH BIOME (Sharp Emerald Tech) */}
        <div className="absolute inset-0 bg-gradient-to-br from-emerald-950/40 via-[#040810] to-[#020509] p-6 sm:p-7 flex flex-col justify-between">
          <div className="flex justify-end items-center gap-2">
            <span className="inline-flex items-center gap-1.5 px-3 py-0.5 rounded-none bg-emerald-950/90 border border-emerald-500/50 text-emerald-300 font-tech text-xs tracking-wider font-bold uppercase">
              <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
              <span>WITH BIOME // UNIFIED ENGINE</span>
            </span>
            <span className="px-2 py-0.5 rounded-none bg-emerald-400 text-dark-950 font-tech text-[10px] font-black uppercase tracking-wider">
              100% GROUNDED
            </span>
          </div>

          <div className="max-w-md ml-auto text-right space-y-2.5">
            <div className="text-xl sm:text-2xl font-display font-bold text-white tracking-tight uppercase">
              Sub-Second Verifiable Truth
            </div>
            
            {/* Visual Micro-Tiles (Sharp) */}
            <div className="flex flex-col gap-1.5 items-end font-tech text-xs">
              <div className="inline-flex items-center gap-2 px-3 py-1 rounded-none bg-[#03060c] border border-emerald-500/40 text-emerald-300">
                <span className="w-1.5 h-1.5 bg-emerald-400 animate-pulse"></span>
                <span>&lt;80MS CROSS-SILO RETRIEVAL</span>
                <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
              </div>
              <div className="inline-flex items-center gap-2 px-3 py-1 rounded-none bg-[#03060c] border border-emerald-500/40 text-emerald-300">
                <span className="w-1.5 h-1.5 bg-emerald-400 animate-pulse"></span>
                <span>VERBATIM SENTENCE CITATIONS</span>
                <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
              </div>
              <div className="inline-flex items-center gap-2 px-3 py-1 rounded-none bg-[#03060c] border border-emerald-500/40 text-emerald-300">
                <span className="w-1.5 h-1.5 bg-emerald-400 animate-pulse"></span>
                <span>ZERO COLLEAGUE INTERRUPTIONS</span>
                <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
              </div>
            </div>
          </div>

          <div className="flex items-center justify-end gap-3 font-tech text-xs">
            <span className="text-slate-500 uppercase">SEARCH OVERHEAD:</span>
            <span className="text-emerald-400 font-bold bg-[#040810] px-2.5 py-0.5 rounded-none border border-emerald-500/50">
              -72% ELIMINATED
            </span>
          </div>
        </div>

        {/* Left Pane: WITHOUT BIOME (Red / Chaos) — Clipped & Sharp */}
        <div 
          className="absolute inset-y-0 left-0 bg-gradient-to-br from-red-950/40 via-[#0a0305] to-[#04060a] p-6 sm:p-7 flex flex-col justify-between border-r-2 border-emerald-400 overflow-hidden"
          style={{ width: `${sliderPosition}%` }}
        >
          <div className="flex items-center gap-2">
            <span className="inline-flex items-center gap-1.5 px-3 py-0.5 rounded-none bg-red-950/90 border border-red-500/50 text-red-300 font-tech text-xs tracking-wider font-bold uppercase">
              <AlertCircle className="w-3.5 h-3.5 text-red-400" />
              <span>WITHOUT BIOME // FRAGMENTED SILOS</span>
            </span>
            <span className="px-2 py-0.5 rounded-none bg-red-500 text-white font-tech text-[10px] font-black uppercase tracking-wider">
              HIGH RISK
            </span>
          </div>

          <div className="max-w-md space-y-2.5">
            <div className="text-xl sm:text-2xl font-display font-bold text-white tracking-tight uppercase">
              Lost In Channels & Databases
            </div>

            {/* Visual Chaos Micro-Tiles (Sharp) */}
            <div className="flex flex-col gap-1.5 items-start font-tech text-xs">
              <div className="inline-flex items-center gap-2 px-3 py-1 rounded-none bg-[#080204] border border-red-500/40 text-red-300">
                <XCircle className="w-3.5 h-3.5 text-red-400" />
                <span>60–80% HUNTING DMS & FILES</span>
              </div>
              <div className="inline-flex items-center gap-2 px-3 py-1 rounded-none bg-[#080204] border border-red-500/40 text-red-300">
                <XCircle className="w-3.5 h-3.5 text-red-400" />
                <span>KEY DECISIONS TRAPPED IN CHAT</span>
              </div>
              <div className="inline-flex items-center gap-2 px-3 py-1 rounded-none bg-[#080204] border border-red-500/40 text-red-300">
                <XCircle className="w-3.5 h-3.5 text-red-400" />
                <span>BASIC SEARCH HALLUCINATES SKUS</span>
              </div>
            </div>
          </div>

          <div className="flex items-center gap-3 font-tech text-xs">
            <span className="text-slate-500 uppercase">SEARCH WASTE:</span>
            <span className="text-red-400 font-bold bg-[#080204] px-2.5 py-0.5 rounded-none border border-red-500/50">
              80% LOST TIME
            </span>
          </div>
        </div>

        {/* Sharp Square Divider Handle */}
        <div 
          className="absolute inset-y-0 w-8 -ml-4 flex items-center justify-center pointer-events-none z-20"
          style={{ left: `${sliderPosition}%` }}
        >
          <div className="w-8 h-8 rounded-none bg-emerald-400 text-dark-950 font-bold shadow-green-glow flex items-center justify-center border-2 border-white">
            <ArrowLeftRight className="w-4 h-4 text-dark-950" />
          </div>
        </div>

      </div>

      {/* Sharp Micro-Instruction */}
      <div className="mt-3 flex items-center gap-2 text-slate-500 font-tech text-xs uppercase tracking-wider">
        <ArrowLeftRight className="w-3.5 h-3.5 text-emerald-400" />
        <span>Drag slider horizontally to inspect before vs after reality</span>
      </div>

    </div>
  );
}
