import React, { useState } from 'react';
import confetti from 'canvas-confetti';
import { 
  CheckCircle2, 
  X, 
  Sparkles, 
  ArrowRight, 
  Building2, 
  Mail, 
  Users, 
  Database,
  Lock,
  MessageSquare
} from 'lucide-react';

export default function DemoModal({ isOpen, onClose, onLaunchStudio }) {
  const [submitted, setSubmitted] = useState(false);
  const [formData, setFormData] = useState({
    email: '',
    company: '',
    teamSize: '50-200',
    dataSources: ['chat', 'databases', 'docs']
  });

  if (!isOpen) return null;

  const handleSubmit = (e) => {
    e.preventDefault();
    setSubmitted(true);
    confetti({
      particleCount: 60,
      spread: 70,
      origin: { y: 0.6 },
      colors: ['#10B981', '#00FF87', '#34D399', '#FFFFFF', '#059669']
    });
  };

  const toggleSource = (src) => {
    setFormData(prev => ({
      ...prev,
      dataSources: prev.dataSources.includes(src)
        ? prev.dataSources.filter(s => s !== src)
        : [...prev.dataSources, src]
    }));
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/85 backdrop-blur-md">
      <div className="relative w-full max-w-xl hud-panel rounded-none border border-emerald-500/40 p-6 sm:p-8 shadow-green-glow bg-[#040810] overflow-hidden">
        
        {/* Close Button - Sharp */}
        <button 
          onClick={onClose}
          className="absolute top-4 right-4 text-slate-400 hover:text-white p-1 rounded-none hover:bg-slate-800 transition-colors cursor-pointer border border-transparent hover:border-slate-700"
        >
          <X className="w-5 h-5" />
        </button>

        {!submitted ? (
          <div>
            <div className="inline-flex items-center gap-2 px-2.5 py-0.5 rounded-none bg-emerald-500/10 border border-emerald-500/40 text-emerald-400 text-xs font-tech tracking-wider uppercase mb-3">
              <Sparkles className="w-3.5 h-3.5" />
              <span>// ENTERPRISE PROOF OF CONCEPT</span>
            </div>

            <h3 className="text-2xl font-display font-bold text-white tracking-tight uppercase">
              Start Your Free Proof of Concept
            </h3>
            <p className="text-slate-400 text-xs mt-1.5 leading-relaxed font-sans">
              Connect your team chats, databases, and enterprise documents into a private, self-hosted intelligence layer.
            </p>

            <form onSubmit={handleSubmit} className="mt-5 space-y-3.5">
              <div>
                <label className="block text-[11px] font-tech text-slate-400 uppercase tracking-wider mb-1">
                  WORK EMAIL:
                </label>
                <div className="relative">
                  <Mail className="w-4 h-4 text-slate-500 absolute left-3.5 top-3" />
                  <input
                    type="email"
                    required
                    value={formData.email}
                    onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                    placeholder="sarah.chen@enterprise.com"
                    className="w-full bg-[#020408] border border-slate-800 rounded-none pl-10 pr-4 py-2 text-xs text-slate-200 placeholder-slate-600 focus:outline-none focus:border-emerald-400 font-tech uppercase"
                  />
                </div>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div>
                  <label className="block text-[11px] font-tech text-slate-400 uppercase tracking-wider mb-1">
                    COMPANY NAME:
                  </label>
                  <div className="relative">
                    <Building2 className="w-4 h-4 text-slate-500 absolute left-3.5 top-3" />
                    <input
                      type="text"
                      required
                      value={formData.company}
                      onChange={(e) => setFormData({ ...formData, company: e.target.value })}
                      placeholder="ACME CORP"
                      className="w-full bg-[#020408] border border-slate-800 rounded-none pl-10 pr-4 py-2 text-xs text-slate-200 placeholder-slate-600 focus:outline-none focus:border-emerald-400 font-tech uppercase"
                    />
                  </div>
                </div>

                <div>
                  <label className="block text-[11px] font-tech text-slate-400 uppercase tracking-wider mb-1">
                    TEAM SIZE:
                  </label>
                  <select
                    value={formData.teamSize}
                    onChange={(e) => setFormData({ ...formData, teamSize: e.target.value })}
                    className="w-full bg-[#020408] border border-slate-800 rounded-none px-3 py-2 text-xs text-slate-200 focus:outline-none focus:border-emerald-400 font-tech uppercase cursor-pointer"
                  >
                    <option value="10-50">10 – 50 WORKERS</option>
                    <option value="50-200">50 – 200 WORKERS</option>
                    <option value="200-1000">200 – 1,000 WORKERS</option>
                    <option value="1000+">1,000+ ENTERPRISE</option>
                  </select>
                </div>
              </div>

              <div>
                <label className="block text-[11px] font-tech text-slate-400 uppercase tracking-wider mb-1.5">
                  TARGET KNOWLEDGE CONNECTORS:
                </label>
                <div className="grid grid-cols-3 gap-2 text-xs font-tech">
                  {[
                    { id: 'chat', label: 'TEAM CHATS' },
                    { id: 'databases', label: 'RELATIONAL DBS' },
                    { id: 'docs', label: 'DOCS & SOPS' }
                  ].map(item => {
                    const active = formData.dataSources.includes(item.id);
                    return (
                      <button
                        type="button"
                        key={item.id}
                        onClick={() => toggleSource(item.id)}
                        className={`p-2 rounded-none border text-center transition-all cursor-pointer uppercase text-[10px] tracking-wider font-bold ${
                          active 
                            ? 'bg-emerald-950/60 border-emerald-500/60 text-emerald-300 shadow-green-glow-subtle' 
                            : 'bg-[#020408] border-slate-800 text-slate-500 hover:text-slate-300'
                        }`}
                      >
                        {item.label}
                      </button>
                    );
                  })}
                </div>
              </div>

              <div className="pt-2">
                <button
                  type="submit"
                  className="w-full py-3 rounded-none bg-emerald-400 hover:bg-emerald-300 text-dark-950 font-black text-xs font-tech uppercase tracking-wider shadow-green-glow flex items-center justify-center gap-2 cursor-pointer transition-all border border-white"
                >
                  <span>REQUEST DEPLOYMENT & POC</span>
                  <ArrowRight className="w-4 h-4 text-dark-950" />
                </button>
              </div>

              <div className="text-center pt-1">
                <button
                  type="button"
                  onClick={() => { onClose(); onLaunchStudio(); }}
                  className="text-xs text-slate-400 hover:text-emerald-400 transition-colors font-tech uppercase tracking-wider underline cursor-pointer"
                >
                  Jump directly into live studio ➔
                </button>
              </div>

            </form>
          </div>
        ) : (
          <div className="text-center py-6 space-y-4 font-tech">
            <div className="w-12 h-12 rounded-none bg-emerald-500/20 border border-emerald-500/50 flex items-center justify-center text-emerald-400 mx-auto shadow-green-glow">
              <CheckCircle2 className="w-7 h-7 text-emerald-400" />
            </div>
            <h3 className="text-2xl font-display font-bold text-white tracking-tight uppercase">
              REQUEST PROVISIONED
            </h3>
            <p className="text-slate-300 text-xs max-w-md mx-auto leading-relaxed">
              Sandbox credentials assigned for <strong>{formData.email}</strong>. Our enterprise team will reach out with your private container bundle.
            </p>
            <div className="pt-3 flex flex-col sm:flex-row items-center justify-center gap-2.5">
              <button
                onClick={() => { onClose(); onLaunchStudio(); }}
                className="w-full sm:w-auto px-5 py-2.5 rounded-none bg-emerald-400 text-dark-950 font-black text-xs uppercase tracking-wider shadow-green-glow flex items-center justify-center gap-2 cursor-pointer border border-white"
              >
                <Sparkles className="w-3.5 h-3.5" />
                <span>LAUNCH STUDIO NOW</span>
              </button>
              <button
                onClick={onClose}
                className="w-full sm:w-auto px-4 py-2.5 rounded-none border border-slate-800 text-slate-400 hover:text-white text-xs uppercase tracking-wider cursor-pointer bg-[#020408]"
              >
                CLOSE
              </button>
            </div>
          </div>
        )}

      </div>
    </div>
  );
}
