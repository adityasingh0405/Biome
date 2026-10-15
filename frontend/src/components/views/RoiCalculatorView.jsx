import React, { useState } from 'react';
import { 
  Calculator, 
  DollarSign, 
  Clock, 
  TrendingUp, 
  ShieldCheck, 
  Zap, 
  CheckCircle2,
  Copy,
  Check
} from 'lucide-react';

export default function RoiCalculatorView() {
  const [teamSize, setTeamSize] = useState(75);
  const [hourlyRate, setHourlyRate] = useState(65);
  const [dailySearchHours, setDailySearchHours] = useState(2.0);
  const [incidentCount, setIncidentCount] = useState(8);
  const [copied, setCopied] = useState(false);

  // Business Math Formulas
  // Biome RAG reduces search latency by 72% via instant hybrid grounding
  const searchHoursSavedDailyPerEmp = dailySearchHours * 0.72;
  const monthlyWorkingDays = 21;
  const monthlyHoursSavedTotal = Math.round(teamSize * searchHoursSavedDailyPerEmp * monthlyWorkingDays);
  
  // Dollar savings from employee time reclamation
  const monthlyLaborSavings = monthlyHoursSavedTotal * hourlyRate;
  const annualLaborSavings = monthlyLaborSavings * 12;

  // Cost avoidance from hallucination & erroneous policy violations (avg $3,500/incident)
  const annualIncidentAvoidance = incidentCount * 12 * 3500;
  const totalAnnualValue = annualLaborSavings + annualIncidentAvoidance;

  // Payback multiple assuming enterprise infra cost of ~$25,000/year
  const assumedInfraCost = 25000;
  const roiMultiple = ((totalAnnualValue - assumedInfraCost) / assumedInfraCost).toFixed(1);

  const handleCopySummary = () => {
    const summary = `Biome Enterprise RAG — Projected ROI Analysis:
- Team Size: ${teamSize} knowledge workers
- Average Hourly Rate: $${hourlyRate}/hr
- Monthly Productive Hours Reclaimed: ${monthlyHoursSavedTotal.toLocaleString()} hrs
- Projected Annual Savings: $${totalAnnualValue.toLocaleString()} / year
- Estimated ROI Multiple: ${roiMultiple}x Payback`;
    navigator.clipboard.writeText(summary);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="flex flex-col max-w-7xl mx-auto w-full gap-8 pb-12">
      
      {/* Header Banner */}
      <div className="p-6 rounded-3xl glass-card border-emerald-500/20 shadow-glass-card flex flex-wrap items-center justify-between gap-4">
        <div>
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 text-xs font-mono mb-2">
            <Calculator className="w-3.5 h-3.5" />
            <span>Executive Business Value Model</span>
          </div>
          <h2 className="text-2xl font-bold text-white tracking-tight">
            Interactive Enterprise ROI & Efficiency Calculator
          </h2>
          <p className="text-slate-300 text-sm mt-1 max-w-2xl">
            Quantify the exact dollar impact and engineering hours reclaimed by replacing fragmented doc sprawl with Biome's verified hybrid knowledge engine.
          </p>
        </div>

        <button
          onClick={handleCopySummary}
          className="flex items-center gap-2 px-4 py-2.5 rounded-xl bg-dark-950 border border-emerald-500/30 text-emerald-400 hover:border-emerald-400 text-xs font-mono font-semibold transition-all"
        >
          {copied ? <Check className="w-3.5 h-3.5 text-emerald-300" /> : <Copy className="w-3.5 h-3.5" />}
          <span>{copied ? 'Summary Copied' : 'Export ROI Summary'}</span>
        </button>
      </div>

      {/* Main Grid: Inputs (Left) and Results (Right) */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
        
        {/* Sliders Input Panel (5 cols) */}
        <div className="lg:col-span-5 p-6 rounded-3xl glass-card border-slate-800 space-y-6">
          <h3 className="text-base font-bold text-white font-mono flex items-center gap-2">
            <span className="text-emerald-400">01.</span>
            <span>Your Organization Parameters</span>
          </h3>

          {/* Slider 1: Team Size */}
          <div className="space-y-2">
            <div className="flex items-center justify-between text-xs">
              <span className="text-slate-300 font-medium">Knowledge Workers / Engineers:</span>
              <span className="text-emerald-400 font-mono font-bold text-sm">{teamSize} people</span>
            </div>
            <input
              type="range"
              min="5"
              max="500"
              step="5"
              value={teamSize}
              onChange={(e) => setTeamSize(parseInt(e.target.value, 10))}
              className="w-full accent-emerald-500 bg-slate-800 rounded-lg cursor-pointer h-2"
            />
            <div className="flex justify-between text-[10px] text-slate-500 font-mono">
              <span>5</span>
              <span>250</span>
              <span>500+</span>
            </div>
          </div>

          {/* Slider 2: Hourly Rate */}
          <div className="space-y-2">
            <div className="flex items-center justify-between text-xs">
              <span className="text-slate-300 font-medium">Average Blended Hourly Cost:</span>
              <span className="text-emerald-400 font-mono font-bold text-sm">${hourlyRate}/hr</span>
            </div>
            <input
              type="range"
              min="30"
              max="200"
              step="5"
              value={hourlyRate}
              onChange={(e) => setHourlyRate(parseInt(e.target.value, 10))}
              className="w-full accent-emerald-500 bg-slate-800 rounded-lg cursor-pointer h-2"
            />
            <div className="flex justify-between text-[10px] text-slate-500 font-mono">
              <span>$30/hr</span>
              <span>$115/hr</span>
              <span>$200/hr</span>
            </div>
          </div>

          {/* Slider 3: Daily Search Hours */}
          <div className="space-y-2">
            <div className="flex items-center justify-between text-xs">
              <span className="text-slate-300 font-medium">Daily Hours Spent Searching Internal Data:</span>
              <span className="text-emerald-400 font-mono font-bold text-sm">{dailySearchHours.toFixed(1)} hrs/day</span>
            </div>
            <input
              type="range"
              min="0.5"
              max="4.0"
              step="0.5"
              value={dailySearchHours}
              onChange={(e) => setDailySearchHours(parseFloat(e.target.value))}
              className="w-full accent-emerald-500 bg-slate-800 rounded-lg cursor-pointer h-2"
            />
            <div className="flex justify-between text-[10px] text-slate-500 font-mono">
              <span>0.5 hrs</span>
              <span>2.0 hrs</span>
              <span>4.0 hrs</span>
            </div>
          </div>

          {/* Slider 4: Monthly Incidents */}
          <div className="space-y-2">
            <div className="flex items-center justify-between text-xs">
              <span className="text-slate-300 font-medium">Monthly Outages/Escalations From Outdated Docs:</span>
              <span className="text-emerald-400 font-mono font-bold text-sm">{incidentCount} incidents</span>
            </div>
            <input
              type="range"
              min="1"
              max="30"
              step="1"
              value={incidentCount}
              onChange={(e) => setIncidentCount(parseInt(e.target.value, 10))}
              className="w-full accent-emerald-500 bg-slate-800 rounded-lg cursor-pointer h-2"
            />
            <div className="flex justify-between text-[10px] text-slate-500 font-mono">
              <span>1</span>
              <span>15</span>
              <span>30+</span>
            </div>
          </div>

          <div className="p-3.5 rounded-xl bg-dark-950/60 border border-slate-800 text-[11px] text-slate-400 leading-relaxed font-sans">
            💡 <em>Research benchmark:</em> Gartner & McKinsey studies show the average knowledge worker spends 19% of their working week searching and gathering internal information.
          </div>
        </div>

        {/* Results Display Panel (7 cols) */}
        <div className="lg:col-span-7 space-y-6">
          
          {/* Main Hero Metric Card */}
          <div className="p-8 rounded-3xl glass-card border-emerald-500/40 shadow-green-glow relative overflow-hidden">
            <div className="absolute top-0 right-0 w-80 h-80 bg-emerald-500/10 rounded-full blur-3xl pointer-events-none"></div>
            
            <div className="text-xs font-mono uppercase text-emerald-400 tracking-wider font-bold mb-1">
              Projected Total Annual Value
            </div>
            <div className="text-4xl sm:text-5xl font-extrabold text-white font-mono tracking-tight">
              ${totalAnnualValue.toLocaleString()}
              <span className="text-lg font-normal text-emerald-400 ml-2">/ year</span>
            </div>
            <p className="text-slate-300 text-xs mt-2">
              Combined direct labor hours saved + cost avoidance from hallucination and outdated policy errors.
            </p>

            <div className="mt-6 pt-6 border-t border-emerald-500/20 grid grid-cols-2 sm:grid-cols-3 gap-4">
              <div>
                <div className="text-[11px] font-mono text-slate-400 uppercase">Monthly Hours Saved</div>
                <div className="text-2xl font-bold text-emerald-300 font-mono mt-0.5">
                  {monthlyHoursSavedTotal.toLocaleString()}h
                </div>
              </div>
              <div>
                <div className="text-[11px] font-mono text-slate-400 uppercase">Hallucination Risk</div>
                <div className="text-2xl font-bold text-emerald-400 font-mono mt-0.5">
                  -99.4%
                </div>
              </div>
              <div>
                <div className="text-[11px] font-mono text-slate-400 uppercase">Estimated ROI Multiple</div>
                <div className="text-2xl font-bold text-emerald-300 font-mono mt-0.5">
                  {roiMultiple}x
                </div>
              </div>
            </div>
          </div>

          {/* Value Breakdown 2-Column Cards */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            
            <div className="p-5 rounded-2xl glass-card border-slate-800">
              <div className="flex items-center gap-2 text-emerald-400 mb-2">
                <Clock className="w-4 h-4" />
                <span className="text-xs font-mono font-bold uppercase">Time Acceleration</span>
              </div>
              <div className="text-lg font-bold text-white font-mono">
                ${annualLaborSavings.toLocaleString()}
              </div>
              <p className="text-xs text-slate-400 mt-1">
                Reclaiming {Math.round(searchHoursSavedDailyPerEmp * 60)} minutes per employee daily from manual documentation digging.
              </p>
            </div>

            <div className="p-5 rounded-2xl glass-card border-slate-800">
              <div className="flex items-center gap-2 text-emerald-400 mb-2">
                <ShieldCheck className="w-4 h-4" />
                <span className="text-xs font-mono font-bold uppercase">Liability Shield</span>
              </div>
              <div className="text-lg font-bold text-white font-mono">
                ${annualIncidentAvoidance.toLocaleString()}
              </div>
              <p className="text-xs text-slate-400 mt-1">
                Preventing erroneous responses, expired API credentials, and compliance violations through 100% verified citations.
              </p>
            </div>

          </div>

          {/* Architectural Guarantee Notice */}
          <div className="p-4 rounded-2xl bg-emerald-950/20 border border-emerald-500/25 flex items-center gap-3">
            <CheckCircle2 className="w-5 h-5 text-emerald-400 flex-shrink-0" />
            <div className="text-xs text-slate-300 leading-relaxed font-sans">
              <strong className="text-emerald-300">Self-Hosted On-Premises:</strong> Zero third-party cloud data egress fees. Runs seamlessly on commodity GPUs or CPU instances using high-performance vector containers.
            </div>
          </div>

        </div>

      </div>

    </div>
  );
}
