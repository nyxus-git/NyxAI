import React, { useEffect, useState } from 'react';
import { AlertCircle, X } from 'lucide-react';
import { AvatarStage } from './components/avatar/AvatarStage';
import { CharacterModal } from './components/CharacterModal';
import { ChatFeed } from './components/ChatFeed';
import { Controls } from './components/Controls';
import { Conversation } from './components/Conversation';
import { Header } from './components/Header';
import { MemoryPanel } from './components/MemoryPanel';
import { StatusIndicator } from './components/StatusIndicator';
import { VoiceVisualizer } from './components/VoiceVisualizer';
import { useVoiceWebSocket } from './hooks/useVoiceWebSocket';
import { API_BASE, fetchAvatarConfig, fetchHealth } from './services/api';
import { AvatarConfig } from './types/companion';
import { DEFAULT_AVATAR_LANDMARKS } from './utils/faceLandmarks';

type DrawerTab = 'chat' | 'memory' | 'conversations';

const INITIAL_CONFIG: AvatarConfig = {
  mode: 'stylized',
  name: 'Nyx',
  tagline: 'Local Desktop AI Companion',
  voice: 'af_heart',
  photo_url: null,
  model_url: null,
  landmarks: DEFAULT_AVATAR_LANDMARKS,
};

export const App: React.FC = () => {
  const [mode, setMode] = useState<'companion' | 'agent'>('agent');
  const [autoApprove, setAutoApprove] = useState<boolean>(true);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [activeTab, setActiveTab] = useState<DrawerTab>('chat');
  const [customizeOpen, setCustomizeOpen] = useState(false);
  const [muted, setMuted] = useState(false);
  const [avatarConfig, setAvatarConfig] = useState<AvatarConfig>(INITIAL_CONFIG);
  const [modelName, setModelName] = useState<string>('qwen2.5:3b');
  const [ollamaConnected, setOllamaConnected] = useState<boolean>(true);

  useEffect(() => {
    fetchAvatarConfig()
      .then((cfg) => setAvatarConfig(cfg))
      .catch(() => undefined);

    const pollHealth = async () => {
      const info = await fetchHealth();
      if (info) {
        setModelName(info.model);
        setOllamaConnected(info.ollama_connected);
      }
    };
    pollHealth();
    const timer = window.setInterval(pollHealth, 15_000);
    return () => window.clearInterval(timer);
  }, []);

  const {
    avatarState,
    voicePhase,
    voiceSessionActive,
    messages,
    liveSubtitle,
    isRecording,
    isConnected,
    errorBanner,
    pendingAction,
    micLevelRef,
    lipSync,
    startVoiceSession,
    endVoiceSession,
    sendCurrentVoiceTurn,
    interruptSpeaking,
    sendTextMessage,
    replayMessageAudio,
    approvePendingAction,
    dismissPendingAction,
    startNewConversation,
    loadConversation,
    clearError,
  } = useVoiceWebSocket({
    mode,
    voice: avatarConfig.voice,
    muted,
    autoApprove,
  });

  const handleSelectConversation = async (id: string) => {
    await loadConversation(id);
    setActiveTab('chat');
    setDrawerOpen(true);
  };

  return (
    <div className="app-container">
      <Header
        companionName={avatarConfig.name}
        mode={mode}
        setMode={setMode}
        autoApprove={autoApprove}
        onToggleAutoApprove={() => setAutoApprove((v) => !v)}
        isBackendConnected={isConnected}
        ollamaConnected={ollamaConnected}
        drawerOpen={drawerOpen}
        onToggleDrawer={() => setDrawerOpen((v) => !v)}
        onOpenCustomize={() => setCustomizeOpen(true)}
      />

      {errorBanner && (
        <div className="error-toast" role="alert">
          <AlertCircle className="w-4 h-4 shrink-0" />
          <span>{errorBanner}</span>
          <button type="button" onClick={clearError} aria-label="Dismiss error">
            <X className="w-3.5 h-3.5" />
          </button>
        </div>
      )}

      <main className={`workspace-grid ${drawerOpen ? 'with-drawer' : 'spotlight'}`}>
        <div className="stage-column">
          <AvatarStage
            config={avatarConfig}
            state={avatarState}
            liveSubtitle={liveSubtitle}
            modelName={modelName}
            mouthOpenRef={lipSync.mouthOpenRef}
            visemeRef={lipSync.visemeRef}
            audioEnergyRef={lipSync.audioEnergyRef}
            pendingAction={pendingAction}
            onApproveAction={() => void approvePendingAction()}
            onDismissAction={dismissPendingAction}
            onOpenCustomize={() => setCustomizeOpen(true)}
          />

          {isRecording && (
            <div className="recording-visualizer-float">
              <VoiceVisualizer isRecording={isRecording} micLevelRef={micLevelRef} />
            </div>
          )}

          <Controls
            companionName={avatarConfig.name}
            voicePhase={voicePhase}
            voiceSessionActive={voiceSessionActive}
            onStartVoiceSession={() => void startVoiceSession()}
            onEndVoiceSession={endVoiceSession}
            onSendCurrentTurn={sendCurrentVoiceTurn}
            onInterruptSpeaking={interruptSpeaking}
            onSendMessage={sendTextMessage}
            muted={muted}
            onToggleMute={() => setMuted((m) => !m)}
            showQuickPrompts={!voiceSessionActive && messages.length === 0}
          />
        </div>

        {drawerOpen && (
          <aside className="side-drawer" aria-label="Conversation and memory panel">
            <div className="drawer-status-strip">
              <StatusIndicator isConnected={isConnected} apiBaseUrl={API_BASE} />
            </div>

            <nav className="panel-tabs" aria-label="Panel tabs">
              {(
                [
                  { id: 'chat', label: 'Chat' },
                  { id: 'memory', label: 'Memory' },
                  { id: 'conversations', label: 'History' },
                ] as { id: DrawerTab; label: string }[]
              ).map((tab) => (
                <button
                  key={tab.id}
                  type="button"
                  id={`panel-tab-${tab.id}`}
                  className={`panel-tab ${activeTab === tab.id ? 'active' : ''}`}
                  onClick={() => setActiveTab(tab.id)}
                  aria-selected={activeTab === tab.id}
                >
                  {tab.label}
                </button>
              ))}
            </nav>

            <div className="drawer-content">
              {activeTab === 'chat' ? (
                <ChatFeed
                  companionName={avatarConfig.name}
                  messages={messages}
                  onReplayAudio={replayMessageAudio}
                  onNewChat={startNewConversation}
                />
              ) : activeTab === 'memory' ? (
                <MemoryPanel apiBaseUrl={API_BASE} />
              ) : (
                <Conversation
                  apiBaseUrl={API_BASE}
                  onSelectConversation={handleSelectConversation}
                />
              )}
            </div>
          </aside>
        )}
      </main>

      {customizeOpen && (
        <CharacterModal
          config={avatarConfig}
          onConfigChange={setAvatarConfig}
          onClose={() => setCustomizeOpen(false)}
        />
      )}
    </div>
  );
};

export default App;
