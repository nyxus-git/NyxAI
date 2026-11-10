import React, { useEffect, useRef } from 'react';
import {
  Battery,
  Cpu,
  HardDrive,
  Terminal,
  Search,
  CheckCircle,
  Clock,
  Volume2,
  PlusCircle,
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
