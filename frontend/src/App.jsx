import React, { useState, useEffect } from 'react';
import Navbar from './components/Navbar';
import LandingPage from './components/LandingPage';
import Workspace from './components/Workspace';
import DemoModal from './components/DemoModal';
import { fetchHealth } from './services/api';

export default function App() {
  // 'landing' or 'workspace'
  const [currentView, setCurrentView] = useState('landing');
  const [isDemoModalOpen, setIsDemoModalOpen] = useState(false);
  const [health, setHealth] = useState({
    status: 'ok',
    chunks_indexed: 148,
    storage_dir: 'data/index',
    processed_dir: 'data/processed'
  });

  useEffect(() => {
    // Initial health check
    const checkHealth = async () => {
      try {
        const data = await fetchHealth();
        setHealth(data);
      } catch (err) {
        console.warn("Health check error:", err);
      }
    };
    checkHealth();
    const interval = setInterval(checkHealth, 30000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="min-h-screen bg-[#030508] text-slate-100 flex flex-col font-sans selection:bg-emerald-500/30 selection:text-emerald-300">
      
      {/* Top Navbar */}
      <Navbar 
        currentView={currentView} 
        setCurrentView={setCurrentView} 
        health={health}
        onRequestDemo={() => setIsDemoModalOpen(true)}
      />

      {/* Main Content Area */}
      <main className="flex-1 flex flex-col">
        {currentView === 'landing' ? (
          <LandingPage 
            onLaunchWorkspace={() => setCurrentView('workspace')} 
            onRequestDemo={() => setIsDemoModalOpen(true)}
          />
        ) : (
          <Workspace onHealthUpdate={(h) => setHealth(h)} />
        )}
      </main>

      {/* Enterprise Demo / PoC Modal */}
      <DemoModal 
        isOpen={isDemoModalOpen}
        onClose={() => setIsDemoModalOpen(false)}
        onLaunchStudio={() => {
          setIsDemoModalOpen(false);
          setCurrentView('workspace');
        }}
      />

    </div>
  );
}
