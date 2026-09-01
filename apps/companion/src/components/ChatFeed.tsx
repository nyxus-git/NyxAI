import React from 'react';
import { Battery, Cpu, HardDrive, Terminal, Search, CheckCircle, Clock } from 'lucide-react';

export interface ChatMessage {
  id: string;
  sender: 'user' | 'assistant';
  text: string;
  toolUsed?: string | null;
  toolResult?: any;
  timestamp: string;
}

interface ChatFeedProps {
  messages: ChatMessage[];
}

export const ChatFeed: React.FC<ChatFeedProps> = ({ messages }) => {
  const renderToolCard = (toolUsed: string, toolResult: any) => {
    if (!toolResult) return null;

    if (toolUsed === 'get_battery_status') {
      return (
        <div className="tool-card">
          <div className="tool-card-header">
            <Battery className="w-4 h-4" />
            <span>Battery Status</span>
          </div>
          <div>Level: {toolResult.percent}% ({toolResult.status})</div>
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
          <div>Used: {toolResult.used_gb} GB / {toolResult.total_gb} GB ({toolResult.percent}%)</div>
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
          <div>Load: {toolResult.percent}% ({toolResult.core_count} cores)</div>
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
          <div>App: {toolResult.application || 'App'} (Pending Approval)</div>
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
          <div>Query: "{toolResult.query}"</div>
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
      <div className="chat-feed">
        {messages.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full text-center opacity-60 my-auto">
            <Clock className="w-8 h-8 mb-2 text-cyan-400" />
            <p>Start a conversation or click the mic to speak to NyxAI.</p>
          </div>
        ) : (
          messages.map((msg) => (
            <div key={msg.id} className={`message-bubble ${msg.sender}`}>
              <div>{msg.text}</div>
              {msg.toolUsed && renderToolCard(msg.toolUsed, msg.toolResult)}
              <div className="message-meta">
                <span>{msg.timestamp}</span>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
};
