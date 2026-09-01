import React, { useState } from 'react';
import { Mic, Send } from 'lucide-react';

interface ControlsProps {
  onSendMessage: (text: string) => void;
  isRecording: boolean;
  onToggleRecording: () => void;
}

export const Controls: React.FC<ControlsProps> = ({
  onSendMessage,
  isRecording,
  onToggleRecording,
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
    <div className="controls-bar">
      <button
        className={`mic-btn ${isRecording ? 'active' : ''}`}
        onClick={onToggleRecording}
        title={isRecording ? 'Click to stop recording' : 'Click to start recording'}
      >
        <Mic className="w-5 h-5" />
      </button>

      <form onSubmit={handleSubmit} className="text-input-wrapper">
        <input
          type="text"
          className="text-input"
          placeholder="Ask NyxAI anything or run a command..."
          value={text}
          onChange={(e) => setText(e.target.value)}
        />
        <button type="submit" className="send-btn" disabled={!text.trim()}>
          <Send className="w-4 h-4" />
        </button>
      </form>
    </div>
  );
};
