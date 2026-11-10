import React from 'react';
import {
  Bot,
  MessageSquare,
  Zap,
  PanelRightOpen,
  PanelRightClose,
  SlidersHorizontal,
  Wifi,
  WifiOff,
} from 'lucide-react';

interface HeaderProps {
  companionName: string;
  mode: 'companion' | 'agent';
  setMode: (mode: 'companion' | 'agent') => void;
  isBackendConnected: boolean;
  ollamaConnected: boolean;
  drawerOpen: boolean;
  onToggleDrawer: () => void;
  onOpenCustomize: () => void;
}

export const Header: React.FC<HeaderProps> = ({
  companionName,
  mode,
  setMode,
  isBackendConnected,
  ollamaConnected,
  drawerOpen,
  onToggleDrawer,
  onOpenCustomize,
}) => {
  return (
    <header className="app-header">
      <div className="brand">
        <div className="brand-logo">
          <Bot className="w-5 h-5 text-slate-950" />
        </div>
        <div className="brand-copy">
          <span className="brand-title">{companionName || 'NyxAI'}</span>
          <span className="brand-sub">Desktop AI Companion</span>
        </div>

        <div className="status-badge" title={ollamaConnected ? 'Backend & Ollama Ready' : 'Ollama Offline / Degraded'}>
          {isBackendConnected ? (
            <Wifi className="w-3.5 h-3.5 text-emerald-400" />
          ) : (
            <WifiOff className="w-3.5 h-3.5 text-rose-400" />
          )}
          <span>
            {!isBackendConnected ? 'Connecting...' : ollamaConnected ? 'AI Ready' : 'Model Offline'}
          </span>
        </div>
      </div>

      <div className="header-right-controls">
        <div className="mode-toggle">
          <button
            type="button"
            className={`mode-btn ${mode === 'companion' ? 'active' : ''}`}
            onClick={() => setMode('companion')}
          >
            <MessageSquare className="w-3.5 h-3.5" />
            <span>Companion</span>
          </button>
          <button
            type="button"
            className={`mode-btn ${mode === 'agent' ? 'active' : ''}`}
            onClick={() => setMode('agent')}
          >
            <Zap className="w-3.5 h-3.5" />
            <span>Desktop Agent</span>
          </button>
        </div>

        <button
          type="button"
          className="header-icon-btn"
          onClick={onOpenCustomize}
          title="Customize Girl Photo, 3D Model & Voice"
        >
          <SlidersHorizontal className="w-4 h-4" />
        </button>

        <button
          type="button"
          className={`header-icon-btn ${drawerOpen ? 'active' : ''}`}
          onClick={onToggleDrawer}
          title={drawerOpen ? 'Focus Girl Stage' : 'Open Chat, Memory & History Drawer'}
        >
          {drawerOpen ? <PanelRightClose className="w-4 h-4" /> : <PanelRightOpen className="w-4 h-4" />}
        </button>
      </div>
    </header>
  );
};
