/**
 * App.tsx — NyxAI Companion UI (Phase 5)
 *
 * Main application layout integrating all Phase 4 + Phase 5 components:
 *   - Avatar with state animation
 *   - Chat feed
 *   - Voice controls + VoiceVisualizer
 *   - Panel navigation: Chat | Memory | Conversations
 *   - StatusIndicator in header
 *   - MemoryPanel + Conversation sidebar
 */

import React, { useState } from 'react';
import { Header } from './components/Header';
import { Avatar } from './components/Avatar';
import { ChatFeed } from './components/ChatFeed';
import { Controls } from './components/Controls';
import { VoiceVisualizer } from './components/VoiceVisualizer';
import { StatusIndicator } from './components/StatusIndicator';
import { MemoryPanel } from './components/MemoryPanel';
import { Conversation } from './components/Conversation';
import { useVoiceWebSocket } from './hooks/useVoiceWebSocket';

type PanelView = 'chat' | 'memory' | 'conversations';

const API_BASE = import.meta.env.VITE_API_URL ?? 'http://localhost:8000';

export const App: React.FC = () => {
  const [mode, setMode] = useState<'companion' | 'agent'>('agent');
  const [activePanel, setActivePanel] = useState<PanelView>('chat');

  const {
    avatarState,
    messages,
    isRecording,
    isConnected,
    toggleRecording,
    sendTextMessage,
  } = useVoiceWebSocket(mode);

  return (
    <div className="app-container">
      {/* ── Header ──────────────────────────────────────────────────────── */}
      <Header
        mode={mode}
        setMode={setMode}
        isBackendConnected={isConnected}
      />

      {/* ── Status Bar ──────────────────────────────────────────────────── */}
      <div className="status-bar">
        <StatusIndicator isConnected={isConnected} apiBaseUrl={API_BASE} />
      </div>

      {/* ── Panel Navigation Tabs ───────────────────────────────────────── */}
      <nav className="panel-tabs" aria-label="View navigation">
        {(['chat', 'memory', 'conversations'] as PanelView[]).map((panel) => (
          <button
            key={panel}
            id={`panel-tab-${panel}`}
            className={`panel-tab ${activePanel === panel ? 'active' : ''}`}
            onClick={() => setActivePanel(panel)}
            aria-selected={activePanel === panel}
          >
            {panel === 'chat' && '💬 Chat'}
            {panel === 'memory' && '🧠 Memory'}
            {panel === 'conversations' && '📚 History'}
          </button>
        ))}
      </nav>

      {/* ── Main Content ────────────────────────────────────────────────── */}
      <main className="main-content">
        {activePanel === 'chat' ? (
          <>
            <Avatar state={avatarState} />
            {isRecording && <VoiceVisualizer isRecording={isRecording} />}
            <ChatFeed messages={messages} />
          </>
        ) : activePanel === 'memory' ? (
          <MemoryPanel
            apiBaseUrl={API_BASE}
            onClose={() => setActivePanel('chat')}
          />
        ) : (
          <Conversation
            apiBaseUrl={API_BASE}
            onClose={() => setActivePanel('chat')}
          />
        )}
      </main>

      {/* ── Voice Controls (always visible) ─────────────────────────────── */}
      {activePanel === 'chat' && (
        <Controls
          onSendMessage={sendTextMessage}
          isRecording={isRecording}
          onToggleRecording={toggleRecording}
        />
      )}
    </div>
  );
};

export default App;
