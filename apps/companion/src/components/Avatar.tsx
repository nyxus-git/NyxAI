import React from 'react';
import { Sparkles, Mic, Brain, Volume2 } from 'lucide-react';

export type AvatarState = 'idle' | 'listening' | 'thinking' | 'speaking';

interface AvatarProps {
  state: AvatarState;
}

export const Avatar: React.FC<AvatarProps> = ({ state }) => {
  const getStateInfo = () => {
    switch (state) {
      case 'listening':
        return { label: 'Listening...', icon: <Mic className="w-4 h-4 text-emerald-400" /> };
      case 'thinking':
        return { label: 'Thinking...', icon: <Brain className="w-4 h-4 text-purple-400" /> };
      case 'speaking':
        return { label: 'Speaking...', icon: <Volume2 className="w-4 h-4 text-cyan-400" /> };
      default:
        return { label: 'NyxAI Ready', icon: <Sparkles className="w-4 h-4 text-cyan-400" /> };
    }
  };

  const { label, icon } = getStateInfo();

  return (
    <div className="avatar-panel">
      <div className="avatar-wrapper">
        <div className={`pulse-ring ${state}`} />
        <div className={`pulse-ring ring-2 ${state}`} />
        <div className={`avatar-orb ${state}`} />
      </div>

      <div className="avatar-state-text">
        {icon}
        <span>{label}</span>
      </div>
    </div>
  );
};
