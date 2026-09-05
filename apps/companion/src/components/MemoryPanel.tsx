/**
 * components/MemoryPanel.tsx
 *
 * Long-term memory management panel for the companion UI.
 *
 * Allows the user to:
 *   - View all stored long-term memories
 *   - Add new memories manually
 *   - Delete individual memories
 *
 * Connected to the /memory/long-term API via the useMemory hook.
 */

import React, { useState } from 'react';
import { Brain, Plus, Trash2, Loader2, AlertCircle } from 'lucide-react';
import { useMemory } from '../hooks/useMemory';

interface MemoryPanelProps {
  apiBaseUrl?: string;
  onClose?: () => void;
}

export const MemoryPanel: React.FC<MemoryPanelProps> = ({
  apiBaseUrl = 'http://localhost:8000',
  onClose,
}) => {
  const { memories, loading, error, addMemory, deleteMemory } = useMemory({ apiBaseUrl });
  const [newMemory, setNewMemory] = useState('');
  const [adding, setAdding] = useState(false);
  const [addError, setAddError] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<number | null>(null);

  const handleAdd = async () => {
    const content = newMemory.trim();
    if (!content) return;

    setAdding(true);
    setAddError(null);
    try {
      const ok = await addMemory(content);
      if (ok) {
        setNewMemory('');
      } else {
        setAddError('Failed to save memory. Is the backend running?');
      }
    } finally {
      setAdding(false);
    }
  };

  const handleDelete = async (id: number) => {
    setDeletingId(id);
    try {
      await deleteMemory(id);
    } finally {
      setDeletingId(null);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleAdd();
    }
  };

  return (
    <div className="memory-panel">
      <div className="memory-panel-header">
        <div className="memory-panel-title">
          <Brain className="w-4 h-4" />
          <span>Long-Term Memory</span>
          <span className="memory-count-badge">{memories.length}</span>
        </div>
        {onClose && (
          <button className="panel-close-btn" onClick={onClose} aria-label="Close panel">
            ×
          </button>
        )}
      </div>

      {/* Add new memory */}
      <div className="memory-add-section">
        <textarea
          id="new-memory-input"
          className="memory-input"
          placeholder="Tell NyxAI something to remember… (e.g. 'I prefer Hinglish responses')"
          value={newMemory}
          onChange={(e) => setNewMemory(e.target.value)}
          onKeyDown={handleKeyDown}
          rows={2}
          maxLength={2000}
          disabled={adding}
          aria-label="New memory content"
        />
        {addError && (
          <div className="memory-error">
            <AlertCircle className="w-3.5 h-3.5" />
            <span>{addError}</span>
          </div>
        )}
        <button
          id="add-memory-btn"
          className="memory-add-btn"
          onClick={handleAdd}
          disabled={adding || !newMemory.trim()}
          aria-label="Save memory"
        >
          {adding ? (
            <Loader2 className="w-4 h-4 animate-spin" />
          ) : (
            <Plus className="w-4 h-4" />
          )}
          <span>{adding ? 'Saving…' : 'Remember This'}</span>
        </button>
      </div>

      {/* Memory list */}
      <div className="memory-panel-body">
        {error && (
          <div className="memory-error">
            <AlertCircle className="w-4 h-4" />
            <span>{error}</span>
          </div>
        )}

        {loading ? (
          <div className="memory-loading">
            <Loader2 className="w-5 h-5 animate-spin" />
            <span>Loading memories…</span>
          </div>
        ) : memories.length === 0 ? (
          <div className="memory-empty">
            <Brain className="w-8 h-8 opacity-30" />
            <p>No memories stored yet.</p>
            <p className="memory-empty-hint">
              Add things you'd like NyxAI to always remember about you.
            </p>
          </div>
        ) : (
          <ul className="memory-list" role="list">
            {memories.map((mem) => (
              <li key={mem.id} className="memory-item" role="listitem">
                <div className="memory-item-content">
                  <p className="memory-item-text">{mem.content}</p>
                  <div className="memory-item-meta">
                    <span className={`memory-source-badge ${mem.source}`}>{mem.source}</span>
                    {mem.tags && (
                      <span className="memory-tags">
                        {mem.tags.split(',').filter(Boolean).map((tag) => (
                          <span key={tag} className="memory-tag">#{tag.trim()}</span>
                        ))}
                      </span>
                    )}
                  </div>
                </div>
                <button
                  className="memory-delete-btn"
                  onClick={() => handleDelete(mem.id)}
                  disabled={deletingId === mem.id}
                  aria-label={`Delete memory: ${mem.content}`}
                  title="Delete this memory"
                >
                  {deletingId === mem.id ? (
                    <Loader2 className="w-3.5 h-3.5 animate-spin" />
                  ) : (
                    <Trash2 className="w-3.5 h-3.5" />
                  )}
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
};
