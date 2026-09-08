import React, { useState, useEffect } from 'react';
import { Sparkles, Mic, Brain, Volume2, ShieldCheck, Activity } from 'lucide-react';

export type AvatarState = 'idle' | 'listening' | 'thinking' | 'speaking';

interface AvatarProps {
  state: AvatarState;
}

export const Avatar: React.FC<AvatarProps> = ({ state }) => {
  const [greeting, setGreeting] = useState("Hey! काय चाललंय?");

  useEffect(() => {
    if (state === 'listening') {
      setGreeting("Listening to you...");
    } else if (state === 'thinking') {
      setGreeting("Thinking & checking tools...");
    } else if (state === 'speaking') {
      setGreeting("Speaking...");
    } else {
      setGreeting("Hey! काय चाललंय? What can I do for you?");
    }
  }, [state]);

  const getStateInfo = () => {
    switch (state) {
      case 'listening':
        return { label: 'Listening', color: '#10b981', icon: <Mic className="w-4 h-4 text-emerald-400 animate-pulse" /> };
      case 'thinking':
        return { label: 'Processing', color: '#9d4edd', icon: <Brain className="w-4 h-4 text-purple-400 animate-spin" /> };
      case 'speaking':
        return { label: 'Speaking', color: '#00f2fe', icon: <Volume2 className="w-4 h-4 text-cyan-400 animate-bounce" /> };
      default:
        return { label: 'Jarvis Online', color: '#00f2fe', icon: <Sparkles className="w-4 h-4 text-cyan-400" /> };
    }
  };

  const { label, icon, color } = getStateInfo();

  return (
    <div className="avatar-panel">
      {/* Background Holographic HUD Grid */}
      <div className="hud-grid-overlay" />

      {/* Main Character Stage */}
      <div className={`avatar-stage ${state}`}>
        {/* Outer Jarvis Rotating Ring */}
        <div className={`jarvis-ring-outer ${state}`} />
        <div className={`jarvis-ring-middle ${state}`} />
        
        {/* SVG Animated Character: Nyx */}
        <svg
          className={`nyx-character ${state}`}
          viewBox="0 0 240 240"
          fill="none"
          xmlns="http://www.w3.org/2000/svg"
        >
          <defs>
            {/* Gradients */}
            <linearGradient id="hairGrad" x1="0%" y1="0%" x2="100%" y2="100%">
              <stop offset="0%" stopColor="#1e1b4b" />
              <stop offset="60%" stopColor="#4f46e5" />
              <stop offset="100%" stopColor="#00f2fe" />
            </linearGradient>

            <linearGradient id="skinGrad" x1="0%" y1="0%" x2="0%" y2="100%">
              <stop offset="0%" stopColor="#ffe4e6" />
              <stop offset="100%" stopColor="#fecdd3" />
            </linearGradient>

            <linearGradient id="eyeGrad" x1="0%" y1="0%" x2="100%" y2="100%">
              <stop offset="0%" stopColor="#00f2fe" />
              <stop offset="100%" stopColor="#3b82f6" />
            </linearGradient>

            <linearGradient id="hudGrad" x1="0%" y1="0%" x2="100%" y2="0%">
              <stop offset="0%" stopColor="#00f2fe" stopOpacity="0.8" />
              <stop offset="50%" stopColor="#9d4edd" stopOpacity="0.8" />
              <stop offset="100%" stopColor="#00f2fe" stopOpacity="0.8" />
            </linearGradient>

            <filter id="neonGlow" x="-20%" y="-20%" width="140%" height="140%">
              <feGaussianBlur stdDeviation="3" result="blur" />
              <feMerge>
                <feMergeNode in="blur" />
                <feMergeNode in="SourceGraphic" />
              </feMerge>
            </filter>
          </defs>

          {/* Holographic Aura Behind Head */}
          <circle cx="120" cy="120" r="95" stroke="url(#hudGrad)" strokeWidth="1.5" strokeDasharray="6 4" className="hud-dashed-orbit" />
          <circle cx="120" cy="120" r="85" stroke="rgba(0, 242, 254, 0.25)" strokeWidth="1" />

          {/* Shoulders & Collar (Cyber Suit) */}
          <path
            d="M 50 230 C 50 190, 85 180, 120 180 C 155 180, 190 190, 190 230 Z"
            fill="#0f172a"
            stroke="url(#hudGrad)"
            strokeWidth="2"
          />
          <path d="M 90 185 L 120 205 L 150 185" stroke="#00f2fe" strokeWidth="2" fill="none" opacity="0.8" />
          {/* Core Arc Reactor on Collar */}
          <circle cx="120" cy="210" r="6" fill="#00f2fe" filter="url(#neonGlow)" />

          {/* Back Hair */}
          <path
            d="M 60 110 C 50 160, 60 210, 80 220 C 70 170, 80 130, 85 110 Z"
            fill="url(#hairGrad)"
          />
          <path
            d="M 180 110 C 190 160, 180 210, 160 220 C 170 170, 160 130, 155 110 Z"
            fill="url(#hairGrad)"
          />

          {/* Neck */}
          <rect x="110" y="150" width="20" height="32" rx="4" fill="url(#skinGrad)" />

          {/* Face Base */}
          <path
            d="M 75 100 C 75 155, 100 175, 120 175 C 140 175, 165 155, 165 100 C 165 70, 140 60, 120 60 C 100 60, 75 70, 75 100 Z"
            fill="url(#skinGrad)"
          />

          {/* Soft Blush */}
          <ellipse cx="90" cy="135" rx="7" ry="3.5" fill="#fb7185" opacity="0.4" />
          <ellipse cx="150" cy="135" rx="7" ry="3.5" fill="#fb7185" opacity="0.4" />

          {/* Cybernetic Temples / Headset */}
          <rect x="62" y="95" width="14" height="28" rx="4" fill="#1e293b" stroke="#00f2fe" strokeWidth="1.5" />
          <rect x="164" y="95" width="14" height="28" rx="4" fill="#1e293b" stroke="#00f2fe" strokeWidth="1.5" />
          {/* Headset Audio Equalizer LEDs */}
          <line x1="69" y1="102" x2="69" y2="116" stroke={color} strokeWidth="2.5" className="equalizer-bar-l" />
          <line x1="171" y1="102" x2="171" y2="116" stroke={color} strokeWidth="2.5" className="equalizer-bar-r" />

          {/* Front Hair Bangs */}
          <path
            d="M 72 90 C 70 50, 100 45, 120 45 C 145 45, 170 50, 168 90 C 155 75, 140 70, 120 78 C 105 70, 85 75, 72 90 Z"
            fill="url(#hairGrad)"
          />
          <path d="M 120 45 C 122 70, 110 95, 105 105 C 115 90, 125 75, 128 50 Z" fill="#312e81" opacity="0.7" />

          {/* Eyebrows */}
          <path d="M 85 105 Q 98 102 105 106" stroke="#312e81" strokeWidth="2.5" strokeLinecap="round" />
          <path d="M 135 106 Q 142 102 155 105" stroke="#312e81" strokeWidth="2.5" strokeLinecap="round" />

          {/* Eyes Group (with Blink Animation) */}
          <g className="avatar-eyes">
            {/* Left Eye */}
            <ellipse cx="95" cy="120" rx="9" ry="11" fill="#ffffff" />
            <ellipse cx="96" cy="120" rx="6.5" ry="8.5" fill="url(#eyeGrad)" />
            <circle cx="97" cy="118" r="3.5" fill="#030712" />
            <circle cx="94" cy="116" r="2.5" fill="#ffffff" />
            {/* Cyber Ring inside Eye */}
            <circle cx="96" cy="120" r="5" stroke="#00f2fe" strokeWidth="0.8" opacity="0.8" strokeDasharray="3 2" />

            {/* Right Eye */}
            <ellipse cx="145" cy="120" rx="9" ry="11" fill="#ffffff" />
            <ellipse cx="144" cy="120" rx="6.5" ry="8.5" fill="url(#eyeGrad)" />
            <circle cx="143" cy="118" r="3.5" fill="#030712" />
            <circle cx="142" cy="116" r="2.5" fill="#ffffff" />
            {/* Cyber Ring inside Eye */}
            <circle cx="144" cy="120" r="5" stroke="#00f2fe" strokeWidth="0.8" opacity="0.8" strokeDasharray="3 2" />
          </g>

          {/* Cute Nose */}
          <path d="M 119 132 L 120 135 L 122 135" stroke="#f43f5e" strokeWidth="1.2" strokeLinecap="round" opacity="0.6" />

          {/* Mouth with Lip-Sync / Emotion Animation */}
          {state === 'speaking' ? (
            /* Animated Speaking Lip-Sync Mouth */
            <path
              className="mouth-speaking"
              d="M 112 148 Q 120 160 128 148 Q 120 144 112 148 Z"
              fill="#e11d48"
              stroke="#f43f5e"
              strokeWidth="1.5"
            />
          ) : state === 'listening' ? (
            /* Attentive slight open 'o' */
            <ellipse cx="120" cy="148" rx="4" ry="4" fill="#e11d48" stroke="#f43f5e" strokeWidth="1" />
          ) : state === 'thinking' ? (
            /* Wavy puzzled smile */
            <path d="M 113 149 Q 118 147 122 149 Q 125 151 127 148" stroke="#be123c" strokeWidth="2" strokeLinecap="round" fill="none" />
          ) : (
            /* Sweet Idle Smile */
            <path d="M 113 147 Q 120 153 127 147" stroke="#be123c" strokeWidth="2.2" strokeLinecap="round" fill="none" />
          )}

          {/* Forehead Holographic Circuit Accent */}
          <path d="M 115 70 L 120 65 L 125 70" stroke="#00f2fe" strokeWidth="1.5" opacity="0.7" fill="none" />
          <circle cx="120" cy="65" r="1.5" fill="#00f2fe" />
        </svg>
      </div>

      {/* Greeting Speech Bubble */}
      <div className="avatar-speech-bubble">
        <p className="greeting-text">{greeting}</p>
      </div>

      {/* Status Bar Indicator */}
      <div className="avatar-status-pill" style={{ borderColor: `${color}66` }}>
        {icon}
        <span className="status-label" style={{ color }}>{label}</span>
        <span className="telemetry-pill">
          <Activity className="w-3 h-3 text-cyan-400" />
          HYPRLAND AGENT
        </span>
      </div>
    </div>
  );
};
