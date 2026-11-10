import React, { useEffect, useState } from 'react';
import { MessageSquare, Clock, Trash2, ArrowUpRight } from 'lucide-react';
import { API_BASE, deleteConversation, fetchConversations } from '../services/api';
import { ConversationSummary } from '../types/companion';

interface ConversationProps {
  apiBaseUrl?: string;
  onSelectConversation?: (id: string) => void;
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
  apiBaseUrl = API_BASE,
  onSelectConversation,
  onClose,
}) => {
  const [conversations, setConversations] = useState<ConversationSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [deletingId, setDeletingId] = useState<string | null>(null);

  const loadList = async () => {
    setLoading(true);
    try {
      const list = await fetchConversations(30);
      setConversations(list);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadList();
  }, [apiBaseUrl]);

  const handleClear = async (e: React.MouseEvent, id: string) => {
    e.stopPropagation();
    setDeletingId(id);
    try {
      await deleteConversation(id);
      await loadList();
    } finally {
      setDeletingId(null);
    }
  };

  return (
    <div className="memory-panel">
      <div className="memory-panel-header">
        <div className="memory-panel-title">
          <MessageSquare className="w-4 h-4" />
          <span>History</span>
        </div>
        {onClose && (
          <button type="button" className="panel-close-btn" onClick={onClose} aria-label="Close">
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
              <li
                key={conv.id}
                className="conversation-item clickable"
                onClick={() => onSelectConversation?.(conv.id)}
              >
                <div className="conversation-info">
                  <div className="conversation-title">
                    {conv.title || `${conv.mode === 'agent' ? 'Agent' : 'Companion'} Session`}
                  </div>
                  <div className="conversation-meta">
                    <Clock className="w-3 h-3" />
                    <span>{formatRelativeTime(conv.updated_at)}</span>
                    <span>·</span>
                    <span>{conv.message_count} msgs</span>
                    <span>·</span>
                    <span className={`conv-mode-badge ${conv.mode}`}>{conv.mode}</span>
                  </div>
                </div>
                <div className="conversation-actions">
                  {onSelectConversation && (
                    <ArrowUpRight className="w-3.5 h-3.5 text-cyan-400 opacity-70" />
                  )}
                  <button
                    type="button"
                    className="memory-delete-btn"
                    onClick={(e) => handleClear(e, conv.id)}
                    disabled={deletingId === conv.id}
                    aria-label="Clear conversation"
                    title="Delete conversation history"
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                  </button>
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
};
