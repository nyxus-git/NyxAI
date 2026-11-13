import React from 'react';
import {
  Activity,
  Bot,
  MessageSquare,
  PanelRightClose,
  PanelRightOpen,
  ShieldCheck,
  SlidersHorizontal,
  Wifi,
  WifiOff,
  Zap,
} from 'lucide-react';

interface HeaderProps {
  companionName: string;
  mode: 'companion' | 'agent';
  setMode: (mode: 'companion' | 'agent') => void;
  autoApprove: boolean;
  onToggleAutoApprove: () => void;
  isBackendConnected: boolean;
  ollamaConnected: boolean;
  drawerOpen: boolean;
  onToggleDrawer: () => void;
  onOpenCustomize: () => void;
  onQuickActivate?: () => void;
  onOpenTelemetry?: () => void;
}

export const Header: React.FC<HeaderProps> = ({
  companionName,
  mode,
  setMode,
  autoApprove,
  onToggleAutoApprove,
  isBackendConnected,
  ollamaConnected,
  drawerOpen,
  onToggleDrawer,
  onOpenCustomize,
  onQuickActivate,
  onOpenTelemetry,
}) => {
  return (
    <header className="app-header">
      <div className="brand">
        <div className="brand-logo">
          <Bot className="w-5 h-5 text-slate-950" />
        </div>
        <div className="brand-copy">
          <span className="brand-title">{companionName || 'NyxAI'}</span>
          <span className="brand-sub">JARVIS Multi-Agent AI</span>
        </div>

        <div className="status-badge" title={ollamaConnected ? 'Backend & Multi-Agent Swarm Ready' : 'Ollama Offline / Degraded'}>
          {isBackendConnected ? (
            <Wifi className="w-3.5 h-3.5 text-emerald-400" />
          ) : (
            <WifiOff className="w-3.5 h-3.5 text-rose-400" />
          )}
          <span>
            {!isBackendConnected ? 'Connecting...' : ollamaConnected ? 'Swarm Ready' : 'Model Offline'}
          </span>
        </div>
      </div>

      <div className="header-right-controls">
        {onQuickActivate && (
          <button
            type="button"
            className="quick-activate-btn"
            onClick={onQuickActivate}
            title="JARVIS Master Routine: Audit hardware, comms and tasks"
          >
            <Zap className="w-3.5 h-3.5 text-cyan-400" />
            <span>Activate Tasks</span>
          </button>
        )}

        {onOpenTelemetry && (
          <button
            type="button"
            className="header-icon-btn telemetry-btn"
            onClick={onOpenTelemetry}
            title="Open Live Multi-Agent Telemetry & Hardware Sensors"
          >
            <Activity className="w-4 h-4 text-cyan-400" />
          </button>
        )}

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

        {mode === 'agent' && (
          <button
            type="button"
            className={`auto-run-pill ${autoApprove ? 'on' : ''}`}
            onClick={onToggleAutoApprove}
            title={
              autoApprove
                ? 'Allowlisted apps and web searches launch automatically'
                : 'Ask before launching apps or web searches'
            }
          >
            <ShieldCheck className="w-3.5 h-3.5" />
            <span>{autoApprove ? 'Auto-Run ON' : 'Ask Confirm'}</span>
          </button>
        )}

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
