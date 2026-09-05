/**
 * components/StatusIndicator.tsx
 *
 * Status bar showing backend connection, memory count, and mode.
 * Displayed in the Header or as a bottom bar in the companion interface.
 */

import React, { useEffect, useState } from 'react';
import { Database, Wifi, WifiOff, Brain } from 'lucide-react';

interface MemoryStatus {
  long_term_count: number;
  conversation_count: number;
  episodic_count: number;
  long_term_enabled: boolean;
  episodic_enabled: boolean;
  semantic_enabled: boolean;
}

interface StatusIndicatorProps {
  isConnected: boolean;
  apiBaseUrl?: string;
}

export const StatusIndicator: React.FC<StatusIndicatorProps> = ({
  isConnected,
  apiBaseUrl = 'http://localhost:8000',
}) => {
  const [memStatus, setMemStatus] = useState<MemoryStatus | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!isConnected) return;

    const fetchStatus = async () => {
      setLoading(true);
      try {
        const res = await fetch(`${apiBaseUrl}/memory/status`);
        if (res.ok) {
          const data = await res.json();
          setMemStatus(data);
        }
      } catch {
        // Silently ignore — backend may still be starting
      } finally {
        setLoading(false);
      }
    };

    fetchStatus();
    const interval = setInterval(fetchStatus, 30_000); // Refresh every 30s
    return () => clearInterval(interval);
  }, [isConnected, apiBaseUrl]);

  return (
    <div className="status-indicator">
      {/* Connection dot */}
      <div className={`status-dot ${isConnected ? 'connected' : 'disconnected'}`}>
        {isConnected ? (
          <Wifi className="w-3 h-3" />
        ) : (
          <WifiOff className="w-3 h-3" />
        )}
        <span>{isConnected ? 'Connected' : 'Offline'}</span>
      </div>

      {/* Memory stats */}
      {memStatus && (
        <>
          <div className="status-divider" />
          <div className="status-memory">
            <Brain className="w-3 h-3" />
            <span>{memStatus.long_term_count} memories</span>
          </div>
          <div className="status-memory">
            <Database className="w-3 h-3" />
            <span>{memStatus.conversation_count} conversations</span>
          </div>
        </>
      )}
    </div>
  );
};
