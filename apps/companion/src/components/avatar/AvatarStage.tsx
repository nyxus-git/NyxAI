import React from 'react';
import {
  Camera,
  Mic,
  Brain,
  Volume2,
  Sparkles,
  Smile,
  AlertCircle,
  HelpCircle,
} from 'lucide-react';
import { resolveAssetUrl } from '../../services/api';
import { AvatarConfig, AvatarState, VisemeKind } from '../../types/companion';
import { PhotoAvatarCanvas } from './PhotoAvatarCanvas';
import { StylizedGirlCanvas } from './StylizedGirlCanvas';
import { VrmAvatarCanvas } from './VrmAvatarCanvas';

interface AvatarStageProps {
  config: AvatarConfig;
  state: AvatarState;
  liveSubtitle: string;
  modelName: string;
  mouthOpenRef: React.MutableRefObject<number>;
  visemeRef: React.MutableRefObject<VisemeKind>;
  audioEnergyRef: React.MutableRefObject<number>;
  onOpenCustomize: () => void;
}

const STATE_BADGE: Record<AvatarState, { label: string; color: string; icon: React.ReactNode }> = {
  idle: { label: 'Ready', color: '#00f2fe', icon: <Sparkles className="w-3.5 h-3.5" /> },
  listening: { label: 'Listening...', color: '#10b981', icon: <Mic className="w-3.5 h-3.5 animate-pulse" /> },
  thinking: { label: 'Thinking...', color: '#a855f7', icon: <Brain className="w-3.5 h-3.5 animate-spin" /> },
  speaking: { label: 'Speaking', color: '#00f2fe', icon: <Volume2 className="w-3.5 h-3.5 animate-pulse" /> },
  happy: { label: 'Happy', color: '#f472b6', icon: <Smile className="w-3.5 h-3.5" /> },
  excited: { label: 'Excited', color: '#facc15', icon: <Sparkles className="w-3.5 h-3.5" /> },
  confused: { label: 'Unsure', color: '#f59e0b', icon: <HelpCircle className="w-3.5 h-3.5" /> },
  concerned: { label: 'Alert', color: '#f43f5e', icon: <AlertCircle className="w-3.5 h-3.5" /> },
};

export const AvatarStage: React.FC<AvatarStageProps> = ({
  config,
  state,
  liveSubtitle,
  modelName,
  mouthOpenRef,
  visemeRef,
  audioEnergyRef,
  onOpenCustomize,
}) => {
  const badge = STATE_BADGE[state] ?? STATE_BADGE.idle;
  const resolvedPhoto = resolveAssetUrl(config.photo_url);
  const resolvedModel = resolveAssetUrl(config.model_url);

  const renderCharacter = () => {
    if (config.mode === 'photo' && resolvedPhoto) {
      return (
        <PhotoAvatarCanvas
          photoUrl={resolvedPhoto}
          landmarks={config.landmarks}
          state={state}
          mouthOpenRef={mouthOpenRef}
          visemeRef={visemeRef}
          audioEnergyRef={audioEnergyRef}
        />
      );
    }

    if (config.mode === 'vrm' && resolvedModel) {
      return (
        <VrmAvatarCanvas
          modelUrl={resolvedModel}
          state={state}
          mouthOpenRef={mouthOpenRef}
          visemeRef={visemeRef}
          audioEnergyRef={audioEnergyRef}
        />
      );
    }

    return (
      <StylizedGirlCanvas
        state={state}
        mouthOpenRef={mouthOpenRef}
        visemeRef={visemeRef}
        audioEnergyRef={audioEnergyRef}
      />
    );
  };

  const defaultGreeting =
    state === 'listening'
      ? "I'm listening — go ahead and ask..."
      : state === 'thinking'
        ? 'Let me think about that...'
        : `Hi! I'm ${config.name}. Ask me anything by voice or text.`;

  const subtitleText = liveSubtitle.trim() || defaultGreeting;

  return (
    <section className={`companion-stage ${state}`} aria-label="Animated AI Companion Stage">
      <div className="stage-ambient-grid" />
      <div className={`stage-orbit-ring outer ${state}`} />
      <div className={`stage-orbit-ring inner ${state}`} />

      {/* Top overlay bar */}
      <div className="stage-top-bar">
        <div className="stage-identity-pill">
          <span className="stage-state-dot" style={{ backgroundColor: badge.color, boxShadow: `0 0 10px ${badge.color}` }} />
          <span className="stage-name">{config.name}</span>
          <span className="stage-state-tag" style={{ color: badge.color }}>
            {badge.icon}
            {badge.label}
          </span>
        </div>

        <div className="stage-actions-right">
          <span className="stage-model-chip" title="Active local LLM model">
            {modelName || 'qwen2.5:3b'}
          </span>
          <button
            type="button"
            className="customize-girl-btn"
            onClick={onOpenCustomize}
            title="Upload girl photo, 3D model, or change voice"
          >
            <Camera className="w-3.5 h-3.5" />
            <span>{config.photo_url ? 'Change Photo' : 'Upload Girl Photo'}</span>
          </button>
        </div>
      </div>

      {/* Center Animated Girl Viewport */}
      <div className={`character-viewport ${state}`}>{renderCharacter()}</div>

      {/* Live Spoken Subtitle Caption */}
      <div className={`live-subtitle-card ${state === 'speaking' ? 'speaking' : ''}`}>
        <p className="live-subtitle-text">{subtitleText}</p>
      </div>
    </section>
  );
};

