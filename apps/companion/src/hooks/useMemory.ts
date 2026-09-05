/**
 * hooks/useMemory.ts
 *
 * React hook for managing long-term memories via the NyxAI Memory API.
 *
 * Usage:
 *   const { memories, addMemory, deleteMemory, loading } = useMemory();
 */

import { useCallback, useEffect, useState } from 'react';

export interface MemoryItem {
  id: number;
  content: string;
  source: string;
  tags: string;
  created_at: string;
  updated_at: string;
}

interface UseMemoryOptions {
  apiBaseUrl?: string;
  tag?: string;
}

interface UseMemoryReturn {
  memories: MemoryItem[];
  loading: boolean;
  error: string | null;
  addMemory: (content: string, tags?: string[]) => Promise<boolean>;
  deleteMemory: (id: number) => Promise<boolean>;
  refresh: () => Promise<void>;
}

export function useMemory({
  apiBaseUrl = 'http://localhost:8000',
  tag,
}: UseMemoryOptions = {}): UseMemoryReturn {
  const [memories, setMemories] = useState<MemoryItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const url = tag
        ? `${apiBaseUrl}/memory/long-term?tag=${encodeURIComponent(tag)}`
        : `${apiBaseUrl}/memory/long-term`;

      const controller = new AbortController();
      const timer = setTimeout(() => controller.abort(), 5000);
      const res = await fetch(url, { signal: controller.signal });
      clearTimeout(timer);

      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      setMemories(data.memories);
    } catch (err) {
      if (err instanceof Error && err.name === 'AbortError') {
        setError('Request timed out. Is the backend running?');
      } else {
        setError(err instanceof Error ? err.message : 'Failed to load memories');
      }
    } finally {
      setLoading(false);
    }
  }, [apiBaseUrl, tag]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const addMemory = useCallback(
    async (content: string, tags: string[] = []): Promise<boolean> => {
      try {
        const res = await fetch(`${apiBaseUrl}/memory/long-term`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ content, source: 'manual', tags }),
        });
        if (!res.ok) return false;
        await refresh();
        return true;
      } catch {
        return false;
      }
    },
    [apiBaseUrl, refresh]
  );

  const deleteMemory = useCallback(
    async (id: number): Promise<boolean> => {
      try {
        const res = await fetch(`${apiBaseUrl}/memory/long-term/${id}`, {
          method: 'DELETE',
        });
        if (!res.ok) return false;
        setMemories((prev) => prev.filter((m) => m.id !== id));
        return true;
      } catch {
        return false;
      }
    },
    [apiBaseUrl]
  );

  return { memories, loading, error, addMemory, deleteMemory, refresh };
}
