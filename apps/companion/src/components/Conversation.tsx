/**
 * components/Conversation.tsx
 *
 * Conversation history sidebar panel.
 * Lists recent conversations with message counts and timestamps.
 * Clicking a conversation could be used to restore it (future feature).
 */

import React, { useEffect, useState } from 'react';
import { MessageSquare, Clock, Trash2, ChevronRight } from 'lucide-react';

interface ConversationSummary {
  id: string;
  mode: string;
  title: string | null;
  created_at: string;
  updated_at: string;
  message_count: number;
}

interface ConversationProps {
  apiBaseUrl?: string;
  onClose?: () => void;
}

function formatRelativeTime(isoString: string): string {
  const date = new Date(isoString);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / 60_000);
  const diffHours = Math.floor(diffMins / 60);
  const diffDays = Math.floor(diffHours / 24);

  if (diffMins < 1) return 'Just now';
  if (diffMins < 60) return `${diffMins}m ago`;
  if (diffHours < 24) return `${diffHours}h ago`;
  return `${diffDays}d ago`;
}

export const Conversation: React.FC<ConversationProps> = ({
  apiBaseUrl = 'http://localhost:8000',
  onClose,
}) => {
  const [conversations, setConversations] = useState<ConversationSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [deletingId, setDeletingId] = useState<string | null>(null);

  const fetchConversations = async () => {
    setLoading(true);
    try {
      const res = await fetch(`${apiBaseUrl}/memory/conversations?limit=30`);
      if (res.ok) {
        const data = await res.json();
        setConversations(data.conversations);
      }
    } catch {
      // silently ignore
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchConversations();
  }, [apiBaseUrl]);

  const handleClear = async (id: string) => {
    if (!confirm('Clear this conversation history?')) return;
    setDeletingId(id);
    try {
      await fetch(`${apiBaseUrl}/memory/conversations/${id}`, { method: 'DELETE' });
      await fetchConversations();
    } finally {
      setDeletingId(null);
    }
  };

  return (
    <div className="memory-panel">
      <div className="memory-panel-header">
        <div className="memory-panel-title">
          <MessageSquare className="w-4 h-4" />
          <span>Conversations</span>
        </div>
        {onClose && (
          <button className="panel-close-btn" onClick={onClose} aria-label="Close">
            ×
          </button>
        )}
      </div>

      <div className="memory-panel-body">
        {loading ? (
          <div className="memory-loading">Loading conversations...</div>
        ) : conversations.length === 0 ? (
          <div className="memory-empty">
            <MessageSquare className="w-8 h-8 opacity-30" />
            <p>No conversations yet.</p>
          </div>
        ) : (
          <ul className="conversation-list">
            {conversations.map((conv) => (
              <li key={conv.id} className="conversation-item">
                <div className="conversation-info">
                  <div className="conversation-title">
                    {conv.title || `${conv.mode === 'agent' ? '🤖' : '💬'} Session`}
                  </div>
                  <div className="conversation-meta">
                    <Clock className="w-3 h-3" />
                    <span>{formatRelativeTime(conv.updated_at)}</span>
                    <span>·</span>
                    <span>{conv.message_count} messages</span>
                    <span>·</span>
                    <span className={`conv-mode-badge ${conv.mode}`}>{conv.mode}</span>
                  </div>
                </div>
                <button
                  className="memory-delete-btn"
                  onClick={() => handleClear(conv.id)}
                  disabled={deletingId === conv.id}
                  aria-label="Clear conversation"
                  title="Clear conversation history"
                >
                  <Trash2 className="w-3.5 h-3.5" />
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
};
