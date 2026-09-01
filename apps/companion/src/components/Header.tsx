import React from 'react';
import { Bot, Zap, MessageSquare } from 'lucide-react';

interface HeaderProps {
  mode: 'companion' | 'agent';
  setMode: (mode: 'companion' | 'agent') => void;
  isBackendConnected: boolean;
}

export const Header: React.FC<HeaderProps> = ({ mode, setMode, isBackendConnected }) => {
  return (
    <header className="app-header">
      <div className="brand">
        <div className="brand-logo">
          <Bot className="w-5 h-5 text-black" />
        </div>
        <span className="brand-title">NyxAI</span>
        <div className="status-badge">
          <div className={`status-dot ${isBackendConnected ? '' : 'offline'}`} />
          <span>{isBackendConnected ? 'Connected' : 'Offline'}</span>
        </div>
      </div>

      <div className="mode-toggle">
        <button
          className={`mode-btn ${mode === 'companion' ? 'active' : ''}`}
          onClick={() => setMode('companion')}
        >
          <MessageSquare className="w-3.5 h-3.5" />
          <span>Companion</span>
        </button>
        <button
          className={`mode-btn ${mode === 'agent' ? 'active' : ''}`}
          onClick={() => setMode('agent')}
        >
          <Zap className="w-3.5 h-3.5" />
          <span>Agent Mode</span>
        </button>
      </div>
    </header>
  );
};
