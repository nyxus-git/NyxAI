import React, { useState } from 'react';
import { Mic, MicOff, Send, Volume2, VolumeX, Sparkles, Radio } from 'lucide-react';

interface ControlsProps {
  companionName: string;
  onSendMessage: (text: string) => void;
  isRecording: boolean;
  onToggleRecording: () => void;
  muted: boolean;
  onToggleMute: () => void;
  handsFree: boolean;
  onToggleHandsFree: () => void;
  showQuickPrompts?: boolean;
}

const QUICK_PROMPTS = [
  'Hey! How are you doing today?',
  'Check my CPU, RAM and battery',
  'Tell me a quick fun fact',
];

export const Controls: React.FC<ControlsProps> = ({
  companionName,
  onSendMessage,
  isRecording,
  onToggleRecording,
  muted,
  onToggleMute,
  handsFree,
  onToggleHandsFree,
  showQuickPrompts = false,
}) => {
  const [text, setText] = useState('');

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (text.trim()) {
      onSendMessage(text.trim());
      setText('');
    }
  };

  return (
    <div className="controls-dock-wrap">
      {showQuickPrompts && (
        <div className="quick-prompts-row">
          {QUICK_PROMPTS.map((q) => (
            <button
              key={q}
              type="button"
              className="quick-prompt-chip"
              onClick={() => onSendMessage(q)}
            >
              <Sparkles className="w-3 h-3" />
              <span>{q}</span>
            </button>
          ))}
        </div>
      )}

      <div className="controls-bar">
        <button
          type="button"
          className={`mic-btn ${isRecording ? 'active' : ''}`}
          onClick={onToggleRecording}
          title={isRecording ? 'Stop speaking' : `Speak to ${companionName}`}
          aria-label={isRecording ? 'Stop voice recording' : 'Start voice recording'}
        >
          {isRecording ? <MicOff className="w-5 h-5" /> : <Mic className="w-5 h-5" />}
        </button>

        <button
          type="button"
          className={`dock-toggle-btn ${handsFree ? 'active' : ''}`}
          onClick={onToggleHandsFree}
          title="Auto-send when you finish speaking (Hands-Free)"
        >
          <Radio className="w-4 h-4" />
        </button>

        <button
          type="button"
          className={`dock-toggle-btn ${muted ? 'muted' : ''}`}
          onClick={onToggleMute}
          title={muted ? 'Unmute her voice' : 'Mute her voice'}
        >
          {muted ? <VolumeX className="w-4 h-4" /> : <Volume2 className="w-4 h-4" />}
        </button>

        <form onSubmit={handleSubmit} className="text-input-wrapper">
          <input
            type="text"
            className="text-input"
            placeholder={`Ask ${companionName || 'Nyx'} a question or give a command...`}
            value={text}
            onChange={(e) => setText(e.target.value)}
          />
          <button type="submit" className="send-btn" disabled={!text.trim()} aria-label="Send message">
            <Send className="w-4 h-4" />
          </button>
        </form>
      </div>
    </div>
  );
};
