import React, { useEffect, useState } from 'react';
import {
  Activity,
  Battery,
  Bot,
  CheckCircle2,
  Clock,
  Cpu,
  HardDrive,
  Loader2,
  Play,
  Radio,
  RefreshCw,
  Server,
  Sparkles,
  Terminal,
  Volume2,
  Zap,
} from 'lucide-react';
import { fetchSystemTelemetry, postQuickAction } from '../services/api';
import { SystemTelemetry } from '../types/companion';

interface MultiAgentHUDProps {
  onSendMessage?: (text: string) => void;
}

export const MultiAgentHUD: React.FC<MultiAgentHUDProps> = ({ onSendMessage }) => {
  const [telemetry, setTelemetry] = useState<SystemTelemetry | null>(null);
  const [loading, setLoading] = useState(false);
  const [actionInProgress, setActionInProgress] = useState<string | null>(null);
  const [actionFeedback, setActionFeedback] = useState<string | null>(null);

  const loadTelemetry = async () => {
    setLoading(true);
    const data = await fetchSystemTelemetry();
    if (data) {
      setTelemetry(data);
    }
    setLoading(false);
  };

  useEffect(() => {
    loadTelemetry();
    const interval = window.setInterval(loadTelemetry, 8_000);
    return () => window.clearInterval(interval);
  }, []);

  const handleAction = async (action: string, label: string, params: Record<string, unknown> = {}) => {
    setActionInProgress(action);
    setActionFeedback(null);
    try {
      const res = await postQuickAction(action, params);
      setActionFeedback(res.message || `${label} executed.`);
      // Also optionally feed it to conversational chat if requested
      if (action === 'activate_all_tasks' && onSendMessage) {
        onSendMessage('Activate all tasks');
      }
    } catch (err: any) {
      setActionFeedback(err.message || 'Execution error');
    } finally {
      setActionInProgress(null);
      loadTelemetry();
    }
  };

  const cpuPercent = Math.round(telemetry?.cpu.percent ?? 0);
  const ramPercent = Math.round(telemetry?.ram.percent ?? 0);
  const batteryPercent = Math.round(telemetry?.battery.percent ?? 100);
  const gpuTemp = telemetry?.gpu?.temperature_c;
  const gpuName = telemetry?.gpu?.name || 'NVIDIA RTX GPU / Intel';

  return (
    <div className="telemetry-hud-container">
      {/* Top Bar */}
      <div className="telemetry-topbar">
        <div className="flex items-center gap-2">
          <Radio className="w-4 h-4 text-cyan-400 animate-pulse" />
          <span className="telemetry-title">Multi-Agent Telemetry & Telemetrics</span>
        </div>
        <button
          type="button"
          className="hud-refresh-btn"
          onClick={loadTelemetry}
          title="Refresh hardware sensors"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
          <span>Refresh</span>
        </button>
      </div>

      {actionFeedback && (
        <div className="hud-feedback-banner">
          <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
          <span>{actionFeedback}</span>
        </div>
      )}

      {/* Hardware Diagnostics Grid */}
      <div className="hud-metrics-grid">
        {/* CPU */}
        <div className="metric-card cpu">
          <div className="metric-header">
            <div className="metric-icon-wrap cyan">
              <Cpu className="w-4 h-4" />
            </div>
            <div className="metric-info">
              <span className="metric-label">CPU Utilization</span>
              <span className="metric-sub">{telemetry?.cpu.core_count ?? 16} Cores Active</span>
            </div>
            <span className="metric-value cyan">{cpuPercent}%</span>
          </div>
          <div className="metric-bar-bg">
            <div className="metric-bar-fill cyan" style={{ width: `${Math.min(100, Math.max(5, cpuPercent))}%` }} />
          </div>
        </div>

        {/* RAM */}
        <div className="metric-card ram">
          <div className="metric-header">
            <div className="metric-icon-wrap violet">
              <HardDrive className="w-4 h-4" />
            </div>
            <div className="metric-info">
              <span className="metric-label">System RAM</span>
              <span className="metric-sub">
                {telemetry?.ram.used_gb ?? '?'} / {telemetry?.ram.total_gb ?? '?'} GB
              </span>
            </div>
            <span className="metric-value violet">{ramPercent}%</span>
          </div>
          <div className="metric-bar-bg">
            <div className="metric-bar-fill violet" style={{ width: `${Math.min(100, Math.max(5, ramPercent))}%` }} />
          </div>
        </div>

        {/* Battery */}
        <div className="metric-card battery">
          <div className="metric-header">
            <div className="metric-icon-wrap emerald">
              <Battery className="w-4 h-4" />
            </div>
            <div className="metric-info">
              <span className="metric-label">Battery Level</span>
              <span className="metric-sub">
                {telemetry?.battery.plugged_in ? 'AC Power Plugged' : 'Discharging'}
              </span>
            </div>
            <span className="metric-value emerald">{batteryPercent}%</span>
          </div>
          <div className="metric-bar-bg">
            <div className="metric-bar-fill emerald" style={{ width: `${Math.min(100, Math.max(5, batteryPercent))}%` }} />
          </div>
        </div>

        {/* GPU */}
        <div className="metric-card gpu">
          <div className="metric-header">
            <div className="metric-icon-wrap amber">
              <Server className="w-4 h-4" />
            </div>
            <div className="metric-info">
              <span className="metric-label">Graphics & Thermals</span>
              <span className="metric-sub truncate" title={gpuName}>{gpuName}</span>
            </div>
            <span className="metric-value amber">{gpuTemp !== undefined ? `${gpuTemp}°C` : 'N/A'}</span>
          </div>
          <div className="metric-bar-bg">
            <div
              className="metric-bar-fill amber"
              style={{
                width: `${Math.min(100, Math.max(10, gpuTemp ? Math.round((gpuTemp / 100) * 100) : 40))}%`,
              }}
            />
          </div>
        </div>
      </div>

      {/* JARVIS Quick Action Deck */}
      <div className="hud-section">
        <div className="hud-section-title">
          <Zap className="w-4 h-4 text-cyan-400" />
          <span>JARVIS Master Command Deck</span>
        </div>
        <div className="hud-actions-grid">
          <button
            type="button"
            className="hud-action-card highlight"
            disabled={actionInProgress !== null}
            onClick={() => handleAction('activate_all_tasks', 'Activate All Tasks')}
          >
            <div className="hud-action-icon">
              {actionInProgress === 'activate_all_tasks' ? (
                <Loader2 className="w-4 h-4 animate-spin text-cyan-400" />
              ) : (
                <Zap className="w-4 h-4 text-cyan-400" />
              )}
            </div>
            <div className="hud-action-content">
              <span className="hud-action-name">Activate All Tasks</span>
              <span className="hud-action-desc">Full diagnostics, unread comms & tasks</span>
            </div>
          </button>

          <button
            type="button"
            className="hud-action-card"
            disabled={actionInProgress !== null}
            onClick={() =>
              handleAction('play_youtube', 'Play Lo-Fi Music', {
                query: 'lofi hip hop radio beats to relax study to',
              })
            }
          >
            <div className="hud-action-icon">
              {actionInProgress === 'play_youtube' ? (
                <Loader2 className="w-4 h-4 animate-spin text-violet-400" />
              ) : (
                <Play className="w-4 h-4 text-violet-400" />
              )}
            </div>
            <div className="hud-action-content">
              <span className="hud-action-name">Play Lo-Fi Beats</span>
              <span className="hud-action-desc">YouTube stream in background</span>
            </div>
          </button>

          <button
            type="button"
            className="hud-action-card"
            disabled={actionInProgress !== null}
            onClick={() => handleAction('control_media', 'Toggle Media Play/Pause', { action: 'play_pause' })}
          >
            <div className="hud-action-icon">
              <Volume2 className="w-4 h-4 text-emerald-400" />
            </div>
            <div className="hud-action-content">
              <span className="hud-action-name">Toggle Media</span>
              <span className="hud-action-desc">Playerctl play/pause control</span>
            </div>
          </button>

          <button
            type="button"
            className="hud-action-card"
            disabled={actionInProgress !== null}
            onClick={() =>
              handleAction('run_terminal', 'Check Git Status', { command: 'git status' })
            }
          >
            <div className="hud-action-icon">
              {actionInProgress === 'run_terminal' ? (
                <Loader2 className="w-4 h-4 animate-spin text-slate-300" />
              ) : (
                <Terminal className="w-4 h-4 text-slate-300" />
              )}
            </div>
            <div className="hud-action-content">
              <span className="hud-action-name">Terminal: git status</span>
              <span className="hud-action-desc">Sandboxed shell command</span>
            </div>
          </button>
        </div>
      </div>

      {/* Specialist Sub-Agent Swarm Roster */}
      <div className="hud-section">
        <div className="hud-section-title">
          <Bot className="w-4 h-4 text-violet-400" />
          <span>Active Specialist Sub-Agents</span>
        </div>
        <div className="agents-roster-list">
          {(telemetry?.agents || []).map((agent) => (
            <div key={agent.id} className="agent-roster-card">
              <div className="agent-badge-ring">
                <div className={`agent-status-dot ${agent.status}`} />
              </div>
              <div className="agent-details">
                <div className="flex items-center justify-between">
                  <span className="agent-name">{agent.name}</span>
                  <span className={`agent-state-pill ${agent.status}`}>
                    {agent.status.toUpperCase()}
                  </span>
                </div>
                <span className="agent-role">{agent.role}</span>
              </div>
            </div>
          ))}
        </div>
      </div>

      {telemetry?.uptime && (
        <div className="hud-uptime-strip">
          <Clock className="w-3.5 h-3.5 text-slate-400" />
          <span>System Uptime: {telemetry.uptime}</span>
        </div>
      )}
    </div>
  );
};

