import React, { useState } from 'react';
import { motion, useScroll, useSpring } from 'framer-motion';
import { 
  Sparkles, 
  ArrowRight, 
  ShieldCheck, 
  Zap, 
  Calculator, 
  Layers, 
  Cpu, 
  Database, 
  CheckCircle2, 
  Lock, 
  Clock, 
  Activity,
  Server,
  FileText,
  MessageSquare,
  AlertTriangle,
  Search,
  Check,
  Network,
  Eye,
  Crosshair,
  Sliders,
  XCircle,
  Terminal,
  Radio,
  BarChart3
} from 'lucide-react';
import NetworkMesh from './interactive/NetworkMesh';
import ComparisonSlider from './interactive/ComparisonSlider';
import PipelineVisualizer from './interactive/PipelineVisualizer';

export default function LandingPage({ onLaunchWorkspace, onRequestDemo }) {
  // Scroll progress for top laser line
  const { scrollYProgress } = useScroll();
  const scaleX = useSpring(scrollYProgress, {
    stiffness: 120,
    damping: 30,
    restDelta: 0.001
  });

  // Hero scenario toggle
  const [activeScenario, setActiveScenario] = useState(0);

  const scenarios = [
    {
      label: "AUTH TIMEOUT",
      query: "Why is the API returning ERR-AUTH-401?",
      sources: [
        { type: "CHAT", name: "#eng-platform", note: "Token cache resets every 3600s" },
        { type: "DB", name: "tickets_db", note: "Ticket #104: In_Progress" },
        { type: "DOC", name: "security_sop.pdf", note: "ERR-AUTH-401 = signature mismatch" }
      ],
      output: "Tokens expire at 3600s [1✓ CHAT, 2✓ DOC]. Ticket #104 resolving cache sync [3✓ DB].",
      speed: "74MS",
      confidence: "98%"
    },
    {
      label: "INFRA OUTAGE",
      query: "How many critical infrastructure tickets are open?",
      sources: [
        { type: "DB", name: "tickets_db", note: "3 critical tickets open" },
        { type: "CHAT", name: "#incidents", note: "2 database shard migrations pending" },
        { type: "DOC", name: "sla_policy.pdf", note: "SLA window: 4-hour max resolution" }
      ],
      output: "3 critical tickets in database [1✓ DB]. 2 shard migrations pending [2✓ CHAT], within 4h SLA [3✓ DOC].",
      speed: "52MS",
      confidence: "99%"
    },
    {
      label: "KEY ROTATION",
      query: "What is the emergency API key rotation procedure?",
      sources: [
        { type: "DOC", name: "runbook.pdf", note: "Zero-downtime dual key activation" },
        { type: "CHAT", name: "#secops", note: "Update vault prior to primary termination" },
        { type: "DB", name: "audit_log", note: "All previous key rotations verified" }
      ],
      output: "Activate secondary key in vault before terminating primary for zero downtime [1✓ DOC, 2✓ CHAT, 3✓ DB].",
      speed: "86MS",
      confidence: "97%"
    }
  ];

  // 4 Solution Pillars (Sharp & Minimal)
  const [activeTab, setActiveTab] = useState(0);
  const solutionPoints = [
    {
      num: "01",
      title: "CONNECT",
      tagline: "UNIFIED MESH",
      cue: "Chats + DBs + Cloud Docs in one active index.",
      icon: Network,
      metric: "ZERO DUPLICATION"
    },
    {
      num: "02",
      title: "UNDERSTAND",
      tagline: "LAYOUT-AWARE",
      cue: "Preserves tables, OCR scans & multi-column hierarchies.",
      icon: Eye,
      metric: "ZERO BLEED"
    },
    {
      num: "03",
      title: "RETRIEVE",
      tagline: "HYBRID FUSION",
      cue: "Dense vectors + exact keywords for obscure codes.",
      icon: Crosshair,
      metric: "SUB-50MS"
    },
    {
      num: "04",
      title: "ANSWER",
      tagline: "100% GROUNDED",
      cue: "Every claim backed by verbatim source proof.",
      icon: CheckCircle2,
      metric: "ZERO GUESSWORK"
    }
  ];

  // ROI Calculator states & presets
  const [teamSize, setTeamSize] = useState(75);
  const [hourlyRate, setHourlyRate] = useState(70);

  const applyPreset = (size, rate) => {
    setTeamSize(size);
    setHourlyRate(rate);
  };

  const annualSavings = Math.round(teamSize * 1.44 * 21 * hourlyRate * 12 + 8 * 12 * 3500);
  const hoursReclaimed = Math.round(teamSize * 1.44 * 21);

  return (
    <div className="flex flex-col w-full bg-[#020408] text-slate-100 relative overflow-hidden font-sans selection:bg-emerald-500/30 selection:text-emerald-300">
      
      {/* 1. Global Scroll Laser Indicator (Framer Motion) */}
      <motion.div 
        style={{ scaleX }}
        className="fixed top-0 left-0 right-0 h-[2.5px] bg-gradient-to-r from-emerald-500 via-emerald-400 to-emerald-200 z-50 origin-left shadow-green-glow"
      />

      {/* 2. Floating Persistent Telemetry HUD Tracker (Bottom-Right) */}
      <div className="hidden lg:flex fixed bottom-6 right-6 z-40 items-center gap-2.5 px-3.5 py-1.5 bg-[#03060c]/90 border border-emerald-500/40 font-tech text-xs text-emerald-400 backdrop-blur-md shadow-green-glow-subtle select-none">
        <span className="w-1.5 h-1.5 bg-emerald-400 animate-ping"></span>
        <span>HUD TELEMETRY</span>
        <span className="text-slate-600">|</span>
        <span className="text-white font-mono">&lt;80MS SUB-SECOND</span>
      </div>

      {/* Top Telemetry Marquee & Sharp Signal Visualizer */}
      <div className="w-full bg-[#03060c] border-b border-emerald-500/20 py-2 px-4 text-xs font-tech select-none">
        <div className="max-w-7xl mx-auto flex items-center justify-between">
          
          <div className="flex items-center gap-3">
            {/* Dynamic Soundwave Equalizer */}
            <div className="flex items-end gap-[3px] h-4 w-6 px-1">
              <span className="w-[3px] bg-emerald-400 animate-eq-1"></span>
              <span className="w-[3px] bg-emerald-400 animate-eq-2"></span>
              <span className="w-[3px] bg-emerald-400 animate-eq-3"></span>
              <span className="w-[3px] bg-emerald-400 animate-eq-4"></span>
              <span className="w-[3px] bg-emerald-400 animate-eq-5"></span>
            </div>
            <span className="text-emerald-400 font-bold tracking-widest uppercase">// RETRIEVAL ENGINE ONLINE</span>
            <span className="text-slate-700">|</span>
            <span className="text-slate-400 font-semibold tracking-wider">LATENCY: &lt;58MS</span>
          </div>

          <div className="hidden md:flex items-center gap-6 text-slate-500 text-[11px] tracking-wider uppercase">
            <span className="flex items-center gap-1.5">
              <span className="w-1.5 h-1.5 bg-emerald-400"></span>
              <span>HYBRID FUSION: SYNCED</span>
            </span>
            <span className="flex items-center gap-1.5">
              <span className="w-1.5 h-1.5 bg-emerald-400"></span>
              <span>ACL HARDENING: ZERO-LEAK</span>
            </span>
            <span className="text-emerald-400 font-bold">VERIFICATION: 100%</span>
          </div>

          <div className="flex items-center gap-2">
            <span className="px-2 py-0.5 rounded-none bg-emerald-500/10 border border-emerald-500/40 text-emerald-400 font-bold text-[10px] tracking-widest uppercase">
              ENTERPRISE TIER
            </span>
          </div>

        </div>
      </div>

      {/* ========================================================================= */}
      {/* 1. HERO SECTION: MOTION ENTRANCE & INTERACTIVE MESH */}
      {/* ========================================================================= */}
      <motion.section 
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ duration: 0.6 }}
        className="relative pt-12 pb-16 md:pt-20 md:pb-24 px-4 sm:px-6 lg:px-8 max-w-7xl mx-auto w-full z-10"
      >
        
        {/* Dynamic Interactive Network Mesh */}
        <div className="absolute inset-0 pointer-events-none">
          <NetworkMesh />
        </div>

        {/* Ambient Emerald Aura */}
        <div className="absolute top-1/4 left-1/2 -translate-x-1/2 w-[700px] h-[350px] bg-emerald-500/[0.08] blur-[150px] pointer-events-none"></div>

        <div className="relative z-10 flex flex-col items-center text-center max-w-4xl mx-auto">
          
          {/* Eyebrow Badge with Fade & Slide */}
          <motion.div 
            initial={{ opacity: 0, y: -15 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, delay: 0.1 }}
            className="inline-flex items-center gap-2 px-3 py-1 rounded-none bg-[#040810] border border-emerald-500/40 text-emerald-400 text-xs font-tech tracking-wider uppercase mb-6 shadow-green-glow-subtle"
          >
            <span className="w-1.5 h-1.5 bg-emerald-400 animate-ping"></span>
            <span className="font-bold">// ENTERPRISE INTELLIGENCE LAYER</span>
          </motion.div>

          {/* Monumental Headline in Non-Normal Font (Syne) */}
          <motion.h1 
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, delay: 0.2 }}
            className="text-5xl sm:text-7xl lg:text-8xl font-black font-display text-white uppercase tracking-tight leading-[0.92]"
          >
            Stop Searching. <br />
            <span className="neon-gradient-text">Start Knowing.</span>
          </motion.h1>

          {/* Minimal 1-line punchy subhead */}
          <motion.p 
            initial={{ opacity: 0, y: 15 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, delay: 0.3 }}
            className="mt-5 text-sm sm:text-base text-slate-300 max-w-xl font-sans font-light"
          >
            Instant, verified answers across your team chats, databases, and enterprise documents.
          </motion.p>

          {/* Sharp Floating Micro-Badges */}
          <motion.div 
            initial={{ opacity: 0, y: 15 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, delay: 0.4 }}
            className="mt-6 flex flex-wrap justify-center gap-2 font-tech text-xs uppercase tracking-wider"
          >
            <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-none bg-[#03060c] border border-emerald-500/40 text-emerald-300">
              <Zap className="w-3.5 h-3.5 text-emerald-400" />
              <span>&lt;80MS LATENCY</span>
            </span>
            <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-none bg-[#03060c] border border-emerald-500/40 text-emerald-300">
              <ShieldCheck className="w-3.5 h-3.5 text-emerald-400" />
              <span>ZERO-LEAK ACL</span>
            </span>
            <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-none bg-[#03060c] border border-emerald-500/40 text-emerald-300">
              <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
              <span>100% VERBATIM PROOF</span>
            </span>
          </motion.div>

          {/* Sharp Action CTAs */}
          <motion.div 
            initial={{ opacity: 0, y: 15 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, delay: 0.5 }}
            className="mt-8 flex flex-col sm:flex-row items-center gap-3 w-full sm:w-auto font-tech"
          >
            <motion.button
              whileHover={{ scale: 1.02 }}
              whileTap={{ scale: 0.98 }}
              onClick={onRequestDemo}
              className="w-full sm:w-auto px-8 py-3.5 rounded-none bg-emerald-400 hover:bg-emerald-300 text-dark-950 font-black text-xs uppercase tracking-widest flex items-center justify-center gap-2 shadow-green-glow transition-all cursor-pointer border border-white"
            >
              <span>REQUEST DEMO</span>
              <ArrowRight className="w-4 h-4 text-dark-950" />
            </motion.button>

            <motion.button
              whileHover={{ scale: 1.02 }}
              whileTap={{ scale: 0.98 }}
              onClick={onLaunchWorkspace}
              className="w-full sm:w-auto px-7 py-3.5 rounded-none bg-[#040810] border border-emerald-500/40 hover:border-emerald-400 text-slate-200 font-bold text-xs uppercase tracking-widest flex items-center justify-center gap-2 hover:bg-emerald-950/30 transition-all cursor-pointer"
            >
              <Sparkles className="w-4 h-4 text-emerald-400" />
              <span>LAUNCH STUDIO</span>
            </motion.button>
          </motion.div>

        </div>

        {/* Dynamic Interactive Demonstration (Sharp HUD Console) */}
        <motion.div 
          initial={{ opacity: 0, y: 30 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.4 }}
          className="mt-12 max-w-5xl mx-auto w-full relative z-10"
        >
          <div className="hud-panel p-5 sm:p-6 bg-[#040810] shadow-green-glow">
            
            {/* Header with live scenario selector */}
            <div className="flex flex-wrap items-center justify-between gap-3 pb-3 border-b border-emerald-500/20 font-tech">
              <div className="flex items-center gap-2">
                <Network className="w-4 h-4 text-emerald-400" />
                <span className="text-xs font-bold uppercase tracking-widest text-emerald-400">
                  // MULTI-SOURCE RETRIEVAL DEMO
                </span>
              </div>
              
              <div className="flex flex-wrap gap-1 text-xs">
                {scenarios.map((sc, i) => (
                  <button
                    key={i}
                    onClick={() => setActiveScenario(i)}
                    className={`px-3 py-1 rounded-none border transition-all cursor-pointer uppercase tracking-wider ${
                      activeScenario === i 
                        ? 'bg-emerald-400 text-dark-950 font-black border-white shadow-green-glow-subtle' 
                        : 'bg-[#020408] border-slate-800 text-slate-400 hover:text-white hover:border-emerald-500/40'
                    }`}
                  >
                    {sc.label}
                  </button>
                ))}
              </div>
            </div>

            {/* 3 Sharp Input Bus Feeds */}
            <div className="mt-3.5 grid grid-cols-1 sm:grid-cols-3 gap-2 font-tech">
              {scenarios[activeScenario].sources.map((s, idx) => (
                <div key={idx} className="p-3 rounded-none bg-[#020408] border border-slate-800 hover:border-emerald-500/40 transition-all text-xs">
                  <div className="flex items-center justify-between text-[10px] mb-1">
                    <span className="text-emerald-400 font-bold uppercase tracking-widest">{s.type}</span>
                    <span className="text-slate-500">{s.name}</span>
                  </div>
                  <div className="text-slate-300 truncate text-xs font-sans">
                    "{s.note}"
                  </div>
                </div>
              ))}
            </div>

            {/* Synthesized Output Result (Sharp Bar) */}
            <div className="mt-3 p-3.5 rounded-none bg-[#020408] border border-emerald-500/40 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
              <div className="text-xs sm:text-sm text-slate-100 font-sans flex-1 flex items-start gap-2">
                <span className="text-emerald-400 font-tech font-bold">&gt;</span>
                <span>{scenarios[activeScenario].output}</span>
              </div>
              <div className="flex items-center gap-2 text-xs font-tech flex-shrink-0 uppercase">
                <span className="px-2 py-0.5 rounded-none bg-emerald-500/10 border border-emerald-500/40 text-emerald-400 font-bold">
                  ⚡ {scenarios[activeScenario].speed}
                </span>
                <span className="px-2 py-0.5 rounded-none bg-emerald-400 text-dark-950 font-black">
                  ✓ {scenarios[activeScenario].confidence}
                </span>
              </div>
            </div>

          </div>
        </motion.div>

      </motion.section>

      {/* ========================================================================= */}
      {/* 2. THE PROBLEM: SCROLL IN-VIEW REVEAL & STAGGERED RED TILES */}
      {/* ========================================================================= */}
      <motion.section 
        id="business-value"
        initial={{ opacity: 0, y: 35 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true, margin: "-60px" }}
        transition={{ duration: 0.55 }}
        className="py-16 px-4 sm:px-6 lg:px-8 max-w-7xl mx-auto w-full border-t border-emerald-500/15 z-10"
      >
        
        <div className="max-w-3xl mb-10">
          <div className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-none bg-red-500/10 border border-red-500/40 text-red-400 text-xs font-tech tracking-wider uppercase mb-2">
            <AlertTriangle className="w-3.5 h-3.5" />
            <span>// THE BOTTLENECK</span>
          </div>
          <h2 className="text-3xl sm:text-5xl font-black font-display text-white tracking-tight uppercase leading-tight">
            Knowledge Fragmentation <br />
            <span className="text-red-400">Is Costly.</span>
          </h2>
        </div>

        {/* 3 Staggered Sharp Red Tiles */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          
          <motion.div 
            initial={{ opacity: 0, y: 25 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.45, delay: 0.1 }}
            whileHover={{ y: -3, borderColor: "rgba(248, 113, 113, 0.6)" }}
            className="p-6 rounded-none hud-panel-red flex flex-col justify-between transition-all"
          >
            <div>
              <div className="text-5xl font-black font-display text-red-400 tracking-tight mb-1">
                80%
              </div>
              <div className="text-sm font-bold font-tech text-white mb-2 uppercase tracking-wider">
                TRAPPED IN SILOS
              </div>
              <div className="flex flex-wrap gap-1 mb-3 font-tech text-[10px]">
                <span className="px-2 py-0.5 rounded-none bg-[#020408] border border-slate-800 text-slate-400">CHATS</span>
                <span className="px-2 py-0.5 rounded-none bg-[#020408] border border-slate-800 text-slate-400">DATABASES</span>
                <span className="px-2 py-0.5 rounded-none bg-[#020408] border border-slate-800 text-slate-400">PDF SOPS</span>
              </div>
              <p className="text-xs text-slate-400 font-sans">
                Vital product decisions lost in disconnected systems.
              </p>
            </div>
            <div className="mt-5 pt-2.5 border-t border-red-900/40 flex items-center justify-between text-xs font-tech text-red-400 uppercase">
              <span>STATUS:</span>
              <span className="font-bold">SEVERE FRICTION</span>
            </div>
          </motion.div>

          <motion.div 
            initial={{ opacity: 0, y: 25 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.45, delay: 0.2 }}
            whileHover={{ y: -3, borderColor: "rgba(248, 113, 113, 0.6)" }}
            className="p-6 rounded-none hud-panel-red flex flex-col justify-between transition-all"
          >
            <div>
              <div className="text-5xl font-black font-display text-red-400 tracking-tight mb-1">
                60–80%
              </div>
              <div className="text-sm font-bold font-tech text-white mb-2 uppercase tracking-wider">
                SEARCH OVERHEAD
              </div>
              <div className="flex flex-wrap gap-1 mb-3 font-tech text-[10px]">
                <span className="px-2 py-0.5 rounded-none bg-[#020408] border border-slate-800 text-slate-400">HUNTING DMS</span>
                <span className="px-2 py-0.5 rounded-none bg-[#020408] border border-slate-800 text-slate-400">INTERRUPTIONS</span>
              </div>
              <p className="text-xs text-slate-400 font-sans">
                Employees spend majority of search time hunting manually.
              </p>
            </div>
            <div className="mt-5 pt-2.5 border-t border-red-900/40 flex items-center justify-between text-xs font-tech text-red-400 uppercase">
              <span>IMPACT:</span>
              <span className="font-bold">ENDLESS PINGS</span>
            </div>
          </motion.div>

          <motion.div 
            initial={{ opacity: 0, y: 25 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.45, delay: 0.3 }}
            whileHover={{ y: -3, borderColor: "rgba(248, 113, 113, 0.6)" }}
            className="p-6 rounded-none hud-panel-red flex flex-col justify-between transition-all"
          >
            <div>
              <div className="text-5xl font-black font-display text-red-400 tracking-tight mb-1">
                35%
              </div>
              <div className="text-sm font-bold font-tech text-white mb-2 uppercase tracking-wider">
                BLIND SPOTS
              </div>
              <div className="flex flex-wrap gap-1 mb-3 font-tech text-[10px]">
                <span className="px-2 py-0.5 rounded-none bg-[#020408] border border-slate-800 text-slate-400">MISSED NUANCE</span>
                <span className="px-2 py-0.5 rounded-none bg-[#020408] border border-slate-800 text-slate-400">UNSEEN ERRORS</span>
              </div>
              <p className="text-xs text-slate-400 font-sans">
                Traditional keyword queries fail on cross-silo context.
              </p>
            </div>
            <div className="mt-5 pt-2.5 border-t border-red-900/40 flex items-center justify-between text-xs font-tech text-red-400 uppercase">
              <span>RISK:</span>
              <span className="font-bold">HALLUCINATED OUTPUT</span>
            </div>
          </motion.div>

        </div>

        {/* Sharp Draggable Comparison Slider */}
        <motion.div 
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.5, delay: 0.2 }}
          className="mt-12"
        >
          <ComparisonSlider />
        </motion.div>

      </motion.section>

      {/* ========================================================================= */}
      {/* 3. THE SOLUTION: STAGGERED PILLARS ON SCROLL */}
      {/* ========================================================================= */}
      <motion.section 
        initial={{ opacity: 0, y: 35 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true, margin: "-60px" }}
        transition={{ duration: 0.55 }}
        className="py-16 px-4 sm:px-6 lg:px-8 max-w-7xl mx-auto w-full border-t border-emerald-500/15 z-10"
      >
        
        <div className="max-w-3xl mb-10">
          <div className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-none bg-emerald-500/10 border border-emerald-500/40 text-emerald-400 text-xs font-tech tracking-wider uppercase mb-2">
            <Sparkles className="w-3.5 h-3.5" />
            <span>// THE PLATFORM</span>
          </div>
          <h2 className="text-3xl sm:text-5xl font-black font-display text-white tracking-tight uppercase leading-tight">
            Meet Biome. <br />
            <span className="text-emerald-400">Grounded Enterprise Truth.</span>
          </h2>
        </div>

        {/* 4 Staggered Sharp Visual Pillars */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {solutionPoints.map((p, idx) => {
            const Icon = p.icon;
            const isSelected = activeTab === idx;
            return (
              <motion.div
                key={p.num}
                initial={{ opacity: 0, y: 25 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ duration: 0.4, delay: idx * 0.1 }}
                whileHover={{ y: -4, borderColor: "#00ff87" }}
                onClick={() => setActiveTab(idx)}
                className={`p-5 rounded-none transition-all cursor-pointer border flex flex-col justify-between ${
                  isSelected
                    ? 'bg-[#040810] border-emerald-400 shadow-green-glow'
                    : 'bg-[#03060c] border-slate-800 hover:border-slate-700'
                }`}
              >
                <div>
                  <div className="flex items-center justify-between mb-3 font-tech">
                    <div className={`w-9 h-9 rounded-none flex items-center justify-center border ${
                      isSelected ? 'bg-emerald-400 text-dark-950 border-white' : 'bg-dark-950 text-emerald-400 border-slate-800'
                    }`}>
                      <Icon className="w-4 h-4" />
                    </div>
                    <span className="text-xs text-slate-500 font-bold">{p.num}</span>
                  </div>
                  
                  <div className="text-base font-bold font-display text-white mb-1 uppercase tracking-tight">
                    {p.title}
                  </div>
                  <div className="text-xs font-tech text-emerald-400 mb-2 font-bold uppercase tracking-wider">
                    {p.tagline}
                  </div>
                  <p className="text-xs text-slate-400 font-sans">
                    {p.cue}
                  </p>
                </div>

                <div className="mt-5 pt-2.5 border-t border-slate-800 flex items-center justify-between text-xs font-tech uppercase">
                  <span className="text-slate-500">METRIC:</span>
                  <span className="text-emerald-400 font-bold">{p.metric}</span>
                </div>
              </motion.div>
            );
          })}
        </div>

      </motion.section>

      {/* ========================================================================= */}
      {/* 4. WHY ENTERPRISES CHOOSE US: SHARP VISUAL BENTO REVEAL */}
      {/* ========================================================================= */}
      <motion.section 
        initial={{ opacity: 0, y: 35 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true, margin: "-60px" }}
        transition={{ duration: 0.55 }}
        className="py-16 px-4 sm:px-6 lg:px-8 max-w-7xl mx-auto w-full border-t border-emerald-500/15 z-10"
      >
        
        <div className="max-w-2xl mb-10">
          <div className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-none bg-emerald-500/10 border border-emerald-500/40 text-emerald-400 text-xs font-tech tracking-wider uppercase mb-2">
            <ShieldCheck className="w-3.5 h-3.5" />
            <span>// PROVEN OUTCOMES</span>
          </div>
          <h2 className="text-3xl sm:text-5xl font-black font-display text-white tracking-tight uppercase">
            Why Enterprises Choose Us
          </h2>
        </div>

        {/* Sharp Bento Grid with Micro-Elevations */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-12 gap-4">
          
          {/* Tile 1: Velocity Meter */}
          <motion.div 
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.45 }}
            whileHover={{ y: -3, borderColor: "rgba(0, 255, 135, 0.5)" }}
            className="lg:col-span-7 p-6 rounded-none hud-panel flex flex-col justify-between transition-all"
          >
            <div>
              <div className="flex items-center gap-2 text-emerald-400 text-xs font-tech font-bold uppercase tracking-wider mb-2">
                <Clock className="w-4 h-4" />
                <span>VELOCITY ACCELERATION</span>
              </div>
              <h3 className="text-xl font-bold font-display text-white mb-2 uppercase">
                Hours to Sub-Seconds
              </h3>
              
              {/* Sharp Velocity Comparison Bar */}
              <div className="mt-3 p-3.5 rounded-none bg-[#020408] border border-slate-800 space-y-2 font-tech text-xs uppercase">
                <div className="flex justify-between text-slate-400">
                  <span>LEGACY SEARCH:</span>
                  <span className="text-red-400">4.2 HOURS AVG</span>
                </div>
                <div className="w-full bg-slate-900 h-[3px]">
                  <div className="bg-red-500/60 h-full w-[85%]" />
                </div>

                <div className="flex justify-between text-slate-200 pt-1">
                  <span className="text-emerald-400 font-bold">WITH BIOME:</span>
                  <span className="text-emerald-400 font-bold">0.04 SECONDS</span>
                </div>
                <div className="w-full bg-slate-900 h-[3px]">
                  <div className="bg-emerald-400 h-full w-[100%] shadow-green-glow" />
                </div>
              </div>
            </div>

            <div className="mt-4 flex items-center justify-between font-tech text-xs pt-2.5 border-t border-slate-800 uppercase">
              <span className="text-slate-500">ACCELERATION:</span>
              <span className="text-emerald-400 font-bold">72% OVERHEAD ELIMINATED</span>
            </div>
          </motion.div>

          {/* Tile 2: Interruption Shield */}
          <motion.div 
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.45, delay: 0.1 }}
            whileHover={{ y: -3, borderColor: "rgba(0, 255, 135, 0.5)" }}
            className="lg:col-span-5 p-6 rounded-none hud-panel flex flex-col justify-between transition-all"
          >
            <div>
              <div className="flex items-center gap-2 text-emerald-400 text-xs font-tech font-bold uppercase tracking-wider mb-2">
                <MessageSquare className="w-4 h-4" />
                <span>INTERRUPTION SHIELD</span>
              </div>
              <h3 className="text-xl font-bold font-display text-white mb-2 uppercase">
                Zero Interruptions
              </h3>
              <p className="text-slate-400 text-xs font-sans">
                Stop the endless <em>"Where is that doc?"</em> messages. Employees self-serve.
              </p>
            </div>

            <div className="mt-5 p-3 rounded-none bg-[#020408] border border-emerald-500/40 flex items-center justify-between font-tech text-xs uppercase">
              <span className="text-slate-400">DAILY INTERRUPTIONS:</span>
              <span className="text-emerald-400 font-bold">14/DAY ➔ 0/DAY</span>
            </div>
          </motion.div>

          {/* Tile 3: Cross-Silo Synthesis */}
          <motion.div 
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.45, delay: 0.15 }}
            whileHover={{ y: -3, borderColor: "rgba(0, 255, 135, 0.5)" }}
            className="lg:col-span-5 p-6 rounded-none hud-panel flex flex-col justify-between transition-all"
          >
            <div>
              <div className="flex items-center gap-2 text-emerald-400 text-xs font-tech font-bold uppercase tracking-wider mb-2">
                <Search className="w-4 h-4" />
                <span>SYNTHESIS</span>
              </div>
              <h3 className="text-xl font-bold font-display text-white mb-2 uppercase">
                Chats ⋈ DB Metrics
              </h3>
              <p className="text-slate-400 text-xs font-sans">
                Seamlessly bridges informal team chatter with hard relational records.
              </p>
            </div>

            <div className="mt-5 p-3 rounded-none bg-[#020408] border border-slate-800 font-tech text-xs text-emerald-300 uppercase">
              CROSS-POLLINATES CHAT WITH SQL
            </div>
          </motion.div>

          {/* Tile 4: 100% Verbatim Proof */}
          <motion.div 
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.45, delay: 0.2 }}
            whileHover={{ y: -3, borderColor: "rgba(0, 255, 135, 0.5)" }}
            className="lg:col-span-7 p-6 rounded-none hud-panel flex flex-col justify-between transition-all"
          >
            <div>
              <div className="flex items-center gap-2 text-emerald-400 text-xs font-tech font-bold uppercase tracking-wider mb-2">
                <CheckCircle2 className="w-4 h-4" />
                <span>AUDIT-READY</span>
              </div>
              <h3 className="text-xl font-bold font-display text-white mb-2 uppercase">
                100% Grounded Citations
              </h3>
              <p className="text-slate-400 text-xs font-sans">
                Zero hallucinated facts. Every single answer maps back to verbatim source proof.
              </p>
            </div>

            <div className="mt-5 p-3 rounded-none bg-[#020408] border border-emerald-500/40 flex items-center justify-between font-tech text-xs uppercase">
              <span className="text-slate-400">GROUNDING PROOF:</span>
              <span className="text-emerald-400 font-bold">100% SUBSTRING VERIFICATION</span>
            </div>
          </motion.div>

        </div>

      </motion.section>

      {/* ========================================================================= */}
      {/* 5. UNDER THE HOOD: SCROLL IN-VIEW ARCHITECTURE */}
      {/* ========================================================================= */}
      <motion.section 
        id="architecture"
        initial={{ opacity: 0, y: 35 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true, margin: "-60px" }}
        transition={{ duration: 0.55 }}
        className="py-16 px-4 sm:px-6 lg:px-8 max-w-7xl mx-auto w-full border-t border-emerald-500/15 z-10"
      >
        
        <div className="max-w-3xl mb-8">
          <div className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-none bg-emerald-500/10 border border-emerald-500/40 text-emerald-400 text-xs font-tech tracking-wider uppercase mb-2">
            <Cpu className="w-3.5 h-3.5" />
            <span>// ARCHITECTURE</span>
          </div>
          <h2 className="text-3xl sm:text-5xl font-black font-display text-white tracking-tight uppercase leading-tight">
            Under The Hood. <br />
            <span className="text-emerald-400">Engineered for CTOs.</span>
          </h2>
          <p className="mt-2 text-slate-400 text-xs font-tech uppercase tracking-wider">
            Click any processing stage to inspect real-time telemetry & latency
          </p>
        </div>

        {/* Dynamic Interactive Pipeline Architecture */}
        <PipelineVisualizer />

      </motion.section>

      {/* ========================================================================= */}
      {/* 6. ECONOMIC IMPACT: SCROLL IN-VIEW ROI SIMULATOR */}
      {/* ========================================================================= */}
      <motion.section 
        id="roi-calculator"
        initial={{ opacity: 0, y: 35 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true, margin: "-60px" }}
        transition={{ duration: 0.55 }}
        className="py-16 px-4 sm:px-6 lg:px-8 max-w-7xl mx-auto w-full border-t border-emerald-500/15 z-10"
      >
        
        <div className="flex flex-col md:flex-row md:items-end justify-between gap-4 mb-8">
          <div>
            <div className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-none bg-emerald-500/10 border border-emerald-500/40 text-emerald-400 text-xs font-tech tracking-wider uppercase mb-2">
              <Calculator className="w-3.5 h-3.5" />
              <span>// ECONOMIC SIMULATOR</span>
            </div>
            <h2 className="text-3xl sm:text-4xl font-black font-display text-white tracking-tight uppercase">
              Quantify Your ROI
            </h2>
          </div>

          {/* Quick Presets (Sharp Tech Buttons) */}
          <div className="flex items-center gap-2 font-tech text-xs uppercase">
            <span className="text-slate-500 text-[10px] mr-1">PRESETS:</span>
            <button
              onClick={() => applyPreset(25, 60)}
              className="px-2.5 py-1 rounded-none bg-[#03060c] border border-slate-800 text-slate-400 hover:text-emerald-400 hover:border-emerald-500/40 cursor-pointer transition-all"
            >
              25 USERS
            </button>
            <button
              onClick={() => applyPreset(100, 75)}
              className="px-2.5 py-1 rounded-none bg-[#03060c] border border-slate-800 text-slate-400 hover:text-emerald-400 hover:border-emerald-500/40 cursor-pointer transition-all"
            >
              100 USERS
            </button>
            <button
              onClick={() => applyPreset(500, 85)}
              className="px-2.5 py-1 rounded-none bg-[#03060c] border border-slate-800 text-slate-400 hover:text-emerald-400 hover:border-emerald-500/40 cursor-pointer transition-all"
            >
              500 USERS
            </button>
          </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-center">
          
          {/* Sliders (Sharp HUD) */}
          <div className="lg:col-span-6 p-6 rounded-none hud-panel space-y-5">
            <div className="space-y-1.5">
              <div className="flex justify-between text-xs font-tech uppercase">
                <span className="text-slate-300">KNOWLEDGE WORKERS:</span>
                <span className="text-emerald-400 font-bold text-sm">{teamSize}</span>
              </div>
              <input
                type="range"
                min="10"
                max="500"
                step="5"
                value={teamSize}
                onChange={(e) => setTeamSize(parseInt(e.target.value, 10))}
                className="w-full accent-emerald-500 bg-slate-800 rounded-none cursor-pointer h-1.5"
              />
            </div>

            <div className="space-y-1.5">
              <div className="flex justify-between text-xs font-tech uppercase">
                <span className="text-slate-300">HOURLY COST ($/HR):</span>
                <span className="text-emerald-400 font-bold text-sm">${hourlyRate}/HR</span>
              </div>
              <input
                type="range"
                min="30"
                max="180"
                step="5"
                value={hourlyRate}
                onChange={(e) => setHourlyRate(parseInt(e.target.value, 10))}
                className="w-full accent-emerald-500 bg-slate-800 rounded-none cursor-pointer h-1.5"
              />
            </div>

            <div className="pt-1 text-[10px] font-tech text-slate-500 flex items-center gap-1.5 uppercase">
              <span className="w-1.5 h-1.5 bg-emerald-400 animate-pulse"></span>
              <span>Based on 1.44h search waste eliminated daily</span>
            </div>
          </div>

          {/* Metric Outputs (Giant Numbers, Sharp Frame) */}
          <div className="lg:col-span-6 p-7 rounded-none hud-panel shadow-green-glow bg-[#040810]">
            <div className="text-[10px] font-tech uppercase text-emerald-400 font-bold tracking-widest mb-1">
              PROJECTED ANNUAL VALUE PRESERVED
            </div>
            <div className="text-4xl sm:text-6xl font-black text-white font-display tracking-tight my-1">
              ${annualSavings.toLocaleString()}
              <span className="text-sm font-normal text-emerald-400 font-tech ml-2 uppercase">/ YR</span>
            </div>

            <div className="mt-5 pt-4 border-t border-slate-800 grid grid-cols-2 gap-4 font-tech">
              <div>
                <div className="text-[10px] text-slate-500 uppercase">HOURS RECLAIMED</div>
                <div className="text-xl sm:text-2xl font-bold text-emerald-300 font-display mt-0.5">
                  {hoursReclaimed.toLocaleString()}H<span className="text-xs text-slate-500 font-normal font-tech">/MO</span>
                </div>
              </div>
              <div>
                <div className="text-[10px] text-slate-500 uppercase">HALLUCINATION RISK</div>
                <div className="text-xl sm:text-2xl font-bold text-emerald-400 font-display mt-0.5">
                  -99.4%
                </div>
              </div>
            </div>
          </div>

        </div>

      </motion.section>

      {/* ========================================================================= */}
      {/* 7. FINAL CALL TO ACTION (SCROLL IN-VIEW) */}
      {/* ========================================================================= */}
      <motion.section 
        initial={{ opacity: 0, scale: 0.97 }}
        whileInView={{ opacity: 1, scale: 1 }}
        viewport={{ once: true, margin: "-60px" }}
        transition={{ duration: 0.55 }}
        className="py-16 px-4 sm:px-6 lg:px-8 max-w-7xl mx-auto w-full border-t border-emerald-500/15 z-10"
      >
        <div className="p-8 sm:p-12 rounded-none hud-panel shadow-green-glow text-center bg-[#040810] relative overflow-hidden tech-crosshair">
          <div className="max-w-lg mx-auto space-y-3.5">
            
            <h2 className="text-3xl sm:text-5xl font-black font-display text-white tracking-tight uppercase leading-tight">
              Break Down Your <br />
              <span className="neon-gradient-text">Knowledge Silos.</span>
            </h2>
            
            <p className="text-slate-300 text-xs sm:text-sm font-light">
              Zero third-party cloud data egress. Self-hosted on your own infrastructure.
            </p>

            <div className="pt-3 flex flex-col sm:flex-row items-center justify-center gap-3 font-tech">
              <motion.button
                whileHover={{ scale: 1.02 }}
                whileTap={{ scale: 0.98 }}
                onClick={onRequestDemo}
                className="w-full sm:w-auto px-8 py-3.5 rounded-none bg-emerald-400 hover:bg-emerald-300 text-dark-950 font-black text-xs uppercase tracking-widest flex items-center justify-center gap-2 shadow-green-glow transition-all cursor-pointer border border-white"
              >
                <span>START FREE PROOF OF CONCEPT</span>
                <ArrowRight className="w-4 h-4 text-dark-950" />
              </motion.button>

              <motion.button
                whileHover={{ scale: 1.02 }}
                whileTap={{ scale: 0.98 }}
                onClick={onLaunchWorkspace}
                className="w-full sm:w-auto px-6 py-3.5 rounded-none bg-[#020408] border border-slate-800 hover:border-emerald-400 text-slate-200 text-xs uppercase tracking-widest transition-all cursor-pointer"
              >
                LAUNCH STUDIO
              </motion.button>
            </div>

          </div>
        </div>
      </motion.section>

      {/* Sharp Minimal Footer */}
      <footer className="py-6 px-4 sm:px-6 lg:px-8 border-t border-slate-900 text-xs text-slate-500 font-tech">
        <div className="max-w-7xl mx-auto flex flex-col sm:flex-row items-center justify-between gap-3 uppercase tracking-wider">
          <div className="flex items-center gap-2 text-slate-400">
            <span>🌿 BIOME</span>
            <span>·</span>
            <span>ENTERPRISE INTELLIGENCE LAYER</span>
          </div>
          <div>
            BUILT FOR ENTERPRISE PRIVACY, VERIFIED CITATIONS & ZERO HALLUCINATION.
          </div>
        </div>
      </footer>

    </div>
  );
}
