import React, { useEffect, useRef } from 'react';
import {
  Battery,
  CheckCircle,
  Clock,
  Cpu,
  ExternalLink,
  HardDrive,
  Mail,
  MessageSquare,
  Play,
  PlusCircle,
  Search,
  Terminal,
  Volume2,
  Zap,
} from 'lucide-react';
import { ChatMessage } from '../types/companion';

interface ChatFeedProps {
  companionName: string;
  messages: ChatMessage[];
  onReplayAudio?: (msg: ChatMessage) => void;
  onNewChat?: () => void;
}

export const ChatFeed: React.FC<ChatFeedProps> = ({
  companionName,
  messages,
  onReplayAudio,
  onNewChat,
}) => {
  const bottomRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages.length]);

  const renderToolCard = (toolUsed: string, toolResult: Record<string, unknown> | null | undefined) => {
    if (!toolResult) return null;

    if (toolUsed === 'get_battery_status') {
      return (
        <div className="tool-card">
          <div className="tool-card-header">
            <Battery className="w-4 h-4" />
            <span>Battery Status</span>
          </div>
          <div>
            Level: {String(toolResult.percent ?? '?')}% ({String(toolResult.status ?? 'Unknown')})
          </div>
        </div>
      );
    }

    if (toolUsed === 'get_ram_usage') {
      return (
        <div className="tool-card">
          <div className="tool-card-header">
            <HardDrive className="w-4 h-4" />
            <span>Memory Usage</span>
          </div>
          <div>
            Used: {String(toolResult.used_gb ?? '?')} GB / {String(toolResult.total_gb ?? '?')} GB (
            {String(toolResult.percent ?? '?')}%)
          </div>
        </div>
      );
    }

    if (toolUsed === 'get_cpu_usage') {
      return (
        <div className="tool-card">
          <div className="tool-card-header">
            <Cpu className="w-4 h-4" />
            <span>CPU Usage</span>
          </div>
          <div>
            Load: {String(toolResult.percent ?? '?')}% ({String(toolResult.core_count ?? '?')} cores)
          </div>
        </div>
      );
    }

    if (toolUsed === 'open_application') {
      return (
        <div className="tool-card">
          <div className="tool-card-header">
            <Terminal className="w-4 h-4" />
            <span>App Launch</span>
          </div>
          <div>App: {String(toolResult.application || 'App')}</div>
        </div>
      );
    }

    if (toolUsed === 'web_search') {
      return (
        <div className="tool-card">
          <div className="tool-card-header">
            <Search className="w-4 h-4" />
            <span>Web Search</span>
          </div>
          <div>Query: "{String(toolResult.query ?? '')}"</div>
        </div>
      );
    }

    if (toolUsed === 'activate_all_tasks') {
      const hw = (toolResult.hardware as Record<string, unknown>) || {};
      const comms = (toolResult.comms as Record<string, unknown>) || {};
      return (
        <div className="tool-card jarvis-briefing-card">
          <div className="tool-card-header">
            <Zap className="w-4 h-4 text-cyan-400" />
            <span className="text-cyan-300 font-semibold">JARVIS Master Briefing</span>
          </div>
          <div className="jarvis-briefing-grid mt-2">
            <div className="briefing-chip">
              <Cpu className="w-3.5 h-3.5 text-cyan-400" />
              <span>CPU: {String(hw.cpu_percent ?? '?')}%</span>
            </div>
            <div className="briefing-chip">
              <HardDrive className="w-3.5 h-3.5 text-violet-400" />
              <span>RAM: {String(hw.ram_percent ?? '?')}%</span>
            </div>
            <div className="briefing-chip">
              <Battery className="w-3.5 h-3.5 text-emerald-400" />
              <span>Battery: {String(hw.battery_percent ?? '?')}%</span>
            </div>
            <div className="briefing-chip">
              <Mail className="w-3.5 h-3.5 text-amber-400" />
              <span>Emails: {String(comms.unread_emails ?? 0)} unread</span>
            </div>
          </div>
        </div>
      );
    }

    if (toolUsed === 'play_youtube') {
      const url = String(toolResult.url ?? '');
      return (
        <div className="tool-card media-player-card">
          <div className="tool-card-header">
            <Play className="w-4 h-4 text-rose-400" />
            <span>YouTube Stream</span>
          </div>
          <div className="mt-1 flex items-center justify-between">
            <span className="font-medium text-slate-200 truncate">"{String(toolResult.query ?? 'Video')}"</span>
            {url && (
              <a
                href={url}
                target="_blank"
                rel="noreferrer"
                className="text-xs text-cyan-400 hover:underline flex items-center gap-1"
              >
                <span>Watch</span>
                <ExternalLink className="w-3 h-3" />
              </a>
            )}
          </div>
        </div>
      );
    }

    if (toolUsed === 'control_media') {
      return (
        <div className="tool-card">
          <div className="tool-card-header">
            <Volume2 className="w-4 h-4 text-emerald-400" />
            <span>Media Controller</span>
          </div>
          <div>Action: {String(toolResult.action ?? 'play_pause')}</div>
        </div>
      );
    }

    if (toolUsed === 'execute_terminal_command') {
      const cmd = String(toolResult.command ?? '');
      const stdout = String(toolResult.stdout ?? '').trim();
      return (
        <div className="tool-card terminal-card">
          <div className="tool-card-header">
            <Terminal className="w-4 h-4 text-emerald-400" />
            <span>Shell Execution</span>
            <span className="text-[10px] opacity-75 font-mono ml-auto">$ {cmd}</span>
          </div>
          {stdout && (
            <pre className="terminal-stdout mt-1.5">{stdout.slice(0, 400)}</pre>
          )}
        </div>
      );
    }

    if (toolUsed === 'check_emails' || toolUsed === 'check_telegram' || toolUsed === 'send_discord_alert') {
      return (
        <div className="tool-card">
          <div className="tool-card-header">
            <MessageSquare className="w-4 h-4 text-violet-400" />
            <span>Communications Hub ({toolUsed})</span>
          </div>
          <div>Status: {String(toolResult.status ?? 'Complete')}</div>
        </div>
      );
    }

    return (
      <div className="tool-card">
        <div className="tool-card-header">
          <CheckCircle className="w-4 h-4" />
          <span>Tool: {toolUsed}</span>
        </div>
        <pre className="text-xs opacity-80 mt-1">{JSON.stringify(toolResult, null, 2)}</pre>
      </div>
    );
  };

  return (
    <div className="chat-panel">
      <div className="chat-panel-topbar">
        <span>Conversation</span>
        {onNewChat && messages.length > 0 && (
          <button type="button" className="new-chat-btn" onClick={onNewChat}>
            <PlusCircle className="w-3.5 h-3.5" />
            <span>New Chat</span>
          </button>
        )}
      </div>

      <div className="chat-feed">
        {messages.length === 0 ? (
          <div className="chat-empty-state">
            <Clock className="w-8 h-8 mb-2 text-cyan-400 opacity-75" />
            <p>Ask {companionName} anything by voice or typing below.</p>
          </div>
        ) : (
          messages.map((msg) => (
            <div key={msg.id} className={`message-bubble ${msg.sender}`}>
              <div>{msg.text}</div>
              {msg.toolUsed && renderToolCard(msg.toolUsed, msg.toolResult)}
              <div className="message-meta">
                <span>{msg.timestamp}</span>
                {msg.sender === 'assistant' && msg.audio && onReplayAudio && (
                  <button
                    type="button"
                    className="replay-voice-btn"
                    onClick={() => onReplayAudio(msg)}
                    title="Replay spoken answer"
                  >
                    <Volume2 className="w-3.5 h-3.5" />
                  </button>
                )}
              </div>
            </div>
          ))
        )}
        <div ref={bottomRef} />
      </div>
    </div>
  );
};
