import React, { useState } from 'react';
import {
  AudioLines,
  Loader2,
  Mic,
  PhoneOff,
  Send,
  Sparkles,
  Volume2,
  VolumeX,
} from 'lucide-react';
import { VoicePhase } from '../hooks/useVoiceWebSocket';

interface ControlsProps {
  companionName: string;
  voicePhase: VoicePhase;
  voiceSessionActive: boolean;
  onStartVoiceSession: () => void;
  onEndVoiceSession: () => void;
  onSendCurrentTurn: () => void;
  onInterruptSpeaking: () => void;
  onSendMessage: (text: string) => void;
  muted: boolean;
  onToggleMute: () => void;
  showQuickPrompts?: boolean;
}

const QUICK_PROMPTS = [
  'Open Firefox for me',
  'Check my CPU, RAM and battery',
  'Hey! Tell me a fun fact',
];

const PHASE_COPY: Record<Exclude<VoicePhase, 'off'>, { label: string; badgeClass: string }> = {
  starting: { label: 'Starting microphone...', badgeClass: 'starting' },
  listening: { label: 'Listening — speak naturally', badgeClass: 'listening' },
  hearing: { label: 'Hearing you...', badgeClass: 'hearing' },
  processing: { label: 'Understanding & thinking...', badgeClass: 'processing' },
  speaking: { label: 'Speaking — real-time voice', badgeClass: 'speaking' },
};

export const Controls: React.FC<ControlsProps> = ({
  companionName,
  voicePhase,
  voiceSessionActive,
  onStartVoiceSession,
  onEndVoiceSession,
  onSendCurrentTurn,
  onInterruptSpeaking,
  onSendMessage,
  muted,
  onToggleMute,
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

  if (voiceSessionActive && voicePhase !== 'off') {
    const phaseInfo = PHASE_COPY[voicePhase];

    return (
      <div className="controls-dock-wrap">
        <div className={`live-voice-bar ${phaseInfo.badgeClass}`}>
          <div className="live-voice-left">
            <div className={`live-voice-orb ${phaseInfo.badgeClass}`}>
              {voicePhase === 'starting' || voicePhase === 'processing' ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : voicePhase === 'speaking' ? (
                <Volume2 className="w-4 h-4" />
              ) : (
                <AudioLines className="w-4 h-4" />
              )}
            </div>
            <div className="live-voice-copy">
              <span className="live-voice-title">Live Voice Mode</span>
              <span className="live-voice-status">{phaseInfo.label}</span>
            </div>
          </div>

          <div className="live-voice-actions">
            {(voicePhase === 'listening' || voicePhase === 'hearing') && (
              <button
                type="button"
                className="voice-action-pill send-now"
                onClick={onSendCurrentTurn}
              >
                <Send className="w-3.5 h-3.5" />
                <span>Send Now</span>
              </button>
            )}

            {voicePhase === 'speaking' && (
              <button
                type="button"
                className="voice-action-pill interrupt"
                onClick={onInterruptSpeaking}
              >
                <Mic className="w-3.5 h-3.5" />
                <span>Interrupt</span>
              </button>
            )}

            <button
              type="button"
              className="voice-action-pill end-call"
              onClick={onEndVoiceSession}
              aria-label="End live voice conversation"
            >
              <PhoneOff className="w-3.5 h-3.5" />
              <span>End Voice</span>
            </button>
          </div>
        </div>
      </div>
    );
  }

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
          className="voice-chat-start-btn"
          onClick={onStartVoiceSession}
          title={`Start real-time voice conversation with ${companionName}`}
        >
          <Mic className="w-4 h-4" />
          <span>Voice Chat</span>
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
            placeholder={`Ask ${companionName || 'Nyx'} anything or type "Open Firefox"...`}
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
