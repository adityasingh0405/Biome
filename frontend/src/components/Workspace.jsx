import React, { useState } from 'react';
import { 
  MessageSquare, 
  GitCompare, 
  Database, 
  FolderGit2, 
  BarChart2, 
  Calculator 
} from 'lucide-react';
import ChatView from './views/ChatView';
import CompareView from './views/CompareView';
import SqlView from './views/SqlView';
import KnowledgeBaseView from './views/KnowledgeBaseView';
import AblationView from './views/AblationView';
import RoiCalculatorView from './views/RoiCalculatorView';

export default function Workspace({ onHealthUpdate }) {
  const [activeTab, setActiveTab] = useState('chat');

  const tabs = [
    { id: 'chat', label: 'Knowledge Assistant', icon: MessageSquare, badge: 'Live' },
    { id: 'compare', label: 'Hybrid vs Dense', icon: GitCompare },
    { id: 'sql', label: 'NL2SQL & ACL', icon: Database, badge: 'Phase 8' },
    { id: 'docs', label: 'Knowledge Base', icon: FolderGit2 },
    { id: 'ablation', label: '18-Arm Benchmarks', icon: BarChart2 },
    { id: 'roi', label: 'ROI Calculator', icon: Calculator },
  ];

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6 w-full flex flex-col gap-6">
      
      {/* Sharp Workspace Tabs Navigation */}
      <div className="flex items-center gap-1.5 p-1.5 rounded-none hud-panel overflow-x-auto scrollbar-none font-tech uppercase text-xs">
        {tabs.map((tab) => {
          const Icon = tab.icon;
          const isActive = activeTab === tab.id;
          return (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`flex items-center gap-2 px-3.5 py-2 rounded-none tracking-wider whitespace-nowrap transition-all duration-200 cursor-pointer ${
                isActive
                  ? 'bg-emerald-950/80 text-emerald-300 border border-emerald-500/50 shadow-green-glow-subtle font-bold'
                  : 'text-slate-400 hover:text-slate-200 hover:bg-[#020408]'
              }`}
            >
              <Icon className={`w-4 h-4 ${isActive ? 'text-emerald-400' : 'text-slate-500'}`} />
              <span>{tab.label}</span>
              {tab.badge && (
                <span className={`text-[9px] font-tech px-1.5 py-0.2 rounded-none font-bold uppercase tracking-wider ${
                  isActive 
                    ? 'bg-emerald-400 text-dark-950' 
                    : 'bg-[#020408] text-slate-500 border border-slate-800'
                }`}>
                  {tab.badge}
                </span>
              )}
            </button>
          );
        })}
      </div>

      {/* Active Workspace View */}
      <main className="w-full">
        {activeTab === 'chat' && <ChatView />}
        {activeTab === 'compare' && <CompareView />}
        {activeTab === 'sql' && <SqlView />}
        {activeTab === 'docs' && <KnowledgeBaseView onHealthUpdate={onHealthUpdate} />}
        {activeTab === 'ablation' && <AblationView />}
        {activeTab === 'roi' && <RoiCalculatorView />}
      </main>

    </div>
  );
}
