import React from 'react';
import { 
  Sparkles, 
  ArrowRight, 
  Activity,
  Layers,
  Calculator,
  Mail
} from 'lucide-react';

export default function Navbar({ currentView, setCurrentView, health, onRequestDemo }) {
  const isOnline = health?.status === 'ok';
  const chunkCount = health?.chunks_indexed || 0;

  return (
    <header className="sticky top-0 z-40 w-full border-b border-emerald-500/20 bg-[#020408]/90 backdrop-blur-xl transition-all">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
        
        {/* Logo - Sharp Tech Branding */}
        <div 
          onClick={() => setCurrentView('landing')}
          className="flex items-center gap-3 cursor-pointer group select-none"
        >
          <div className="w-9 h-9 rounded-none bg-emerald-950/80 border border-emerald-500/50 flex items-center justify-center text-emerald-400 shadow-green-glow-subtle group-hover:border-emerald-400 transition-all">
            <span className="text-base font-black font-tech">🌿</span>
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="text-base font-extrabold tracking-tight text-white font-display uppercase">
                BIOME<span className="text-emerald-400 font-normal">.AI</span>
              </span>
              <span className="px-1.5 py-0.2 text-[9px] font-tech font-bold rounded-none bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 uppercase tracking-widest">
                ENTERPRISE
              </span>
            </div>
          </div>
        </div>

        {/* Navigation Links for Landing Page (Sharp & Tech) */}
        {currentView === 'landing' ? (
          <nav className="hidden md:flex items-center gap-8 text-xs font-tech uppercase tracking-widest text-slate-400">
            <a href="#business-value" className="hover:text-emerald-400 transition-colors">
              // COST OF SILOS
            </a>
            <a href="#architecture" className="hover:text-emerald-400 transition-colors">
              // ARCHITECTURE
            </a>
            <a href="#roi-calculator" className="hover:text-emerald-400 transition-colors">
              // ROI SIMULATOR
            </a>
          </nav>
        ) : (
          <div className="flex items-center gap-2">
            <button
              onClick={() => setCurrentView('landing')}
              className="text-xs font-tech uppercase tracking-wider text-slate-400 hover:text-emerald-400 px-3 py-1.5 rounded-none border border-slate-800 hover:border-emerald-500/30 transition-all flex items-center gap-1.5"
            >
              <span>← OVERVIEW</span>
            </button>
          </div>
        )}

        {/* Right side actions */}
        <div className="flex items-center gap-3 font-tech text-xs">
          
          {/* Health status badge */}
          <div className="hidden lg:flex items-center gap-2 px-3 py-1 rounded-none bg-[#03060c] border border-slate-800 text-slate-400 uppercase tracking-wider">
            <span className={`w-1.5 h-1.5 rounded-none ${isOnline ? 'bg-emerald-400 animate-ping' : 'bg-emerald-500'}`}></span>
            <span>INDEX: <strong className="text-emerald-400 font-bold">{chunkCount} CHUNKS</strong></span>
          </div>

          {currentView === 'landing' ? (
            <div className="flex items-center gap-2.5">
              <button
                onClick={onRequestDemo}
                className="hidden sm:flex text-xs font-bold font-tech uppercase tracking-wider text-slate-300 hover:text-white px-3.5 py-2 rounded-none border border-slate-800 hover:border-emerald-500/50 transition-all cursor-pointer items-center gap-1.5 bg-[#03060c]"
              >
                <Mail className="w-3.5 h-3.5 text-emerald-400" />
                <span>REQUEST DEMO</span>
              </button>

              <button
                onClick={() => setCurrentView('workspace')}
                className="px-4 py-2 rounded-none text-xs font-bold text-dark-950 bg-emerald-400 hover:bg-emerald-300 shadow-green-glow transition-all flex items-center gap-1.5 cursor-pointer font-tech uppercase tracking-wider border border-white"
              >
                <Sparkles className="w-3.5 h-3.5 text-dark-950" />
                <span>LAUNCH STUDIO</span>
              </button>
            </div>
          ) : (
            <div className="px-3 py-1.5 rounded-none bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 text-xs font-bold flex items-center gap-1.5 font-tech uppercase tracking-wider">
              <Activity className="w-3.5 h-3.5 animate-pulse" />
              <span>STUDIO ACTIVE</span>
            </div>
          )}

        </div>

      </div>
    </header>
  );
}
