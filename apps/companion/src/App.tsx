import React, { useState } from 'react';
import { Header } from './components/Header';
import { Avatar } from './components/Avatar';
import { ChatFeed } from './components/ChatFeed';
import { Controls } from './components/Controls';
import { useVoiceWebSocket } from './hooks/useVoiceWebSocket';

export const App: React.FC = () => {
  const [mode, setMode] = useState<'companion' | 'agent'>('agent');
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
      <Header
        mode={mode}
        setMode={setMode}
        isBackendConnected={isConnected}
      />

      <main className="main-content">
        <Avatar state={avatarState} />
        <ChatFeed messages={messages} />
      </main>

      <Controls
        onSendMessage={sendTextMessage}
        isRecording={isRecording}
        onToggleRecording={toggleRecording}
      />
    </div>
  );
};

export default App;
