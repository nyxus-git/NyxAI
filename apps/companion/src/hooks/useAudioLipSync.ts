import { useCallback, useEffect, useMemo, useRef } from 'react';
import { VisemeFrame, VisemeKind } from '../types/companion';

export interface LipSyncLiveState {
  mouthOpenRef: React.MutableRefObject<number>;
  visemeRef: React.MutableRefObject<VisemeKind>;
  audioEnergyRef: React.MutableRefObject<number>;
  isPlayingRef: React.MutableRefObject<boolean>;
  playAudio: (
    base64Wav: string,
    visemes?: VisemeFrame[],
    onStart?: () => void,
    onEnded?: () => void
  ) => Promise<void>;
  stopAudio: () => void;
}

function base64ToArrayBuffer(b64: string): ArrayBuffer {
  const binary = window.atob(b64);
  const len = binary.length;
  const bytes = new Uint8Array(len);
  for (let i = 0; i < len; i++) {
    bytes[i] = binary.charCodeAt(i);
  }
  return bytes.buffer;
}

function classifyViseme(mouthOpen: number): VisemeKind {
  if (mouthOpen < 0.08) return 'closed';
  if (mouthOpen < 0.35) return 'slight';
  if (mouthOpen < 0.7) return 'open';
  return 'wide';
}

export function useAudioLipSync(muted: boolean): LipSyncLiveState {
  const mouthOpenRef = useRef<number>(0);
  const visemeRef = useRef<VisemeKind>('closed');
  const audioEnergyRef = useRef<number>(0);
  const isPlayingRef = useRef<boolean>(false);

  const audioCtxRef = useRef<AudioContext | null>(null);
  const sourceRef = useRef<AudioBufferSourceNode | null>(null);
  const rafRef = useRef<number | null>(null);
  const playbackSessionRef = useRef<number>(0);

  const stopAudio = useCallback(() => {
    playbackSessionRef.current += 1;
    if (rafRef.current !== null) {
      cancelAnimationFrame(rafRef.current);
      rafRef.current = null;
    }
    if (sourceRef.current) {
      try {
        sourceRef.current.onended = null;
        sourceRef.current.stop();
        sourceRef.current.disconnect();
      } catch {
        // already stopped
      }
      sourceRef.current = null;
    }
    isPlayingRef.current = false;
    mouthOpenRef.current = 0;
    audioEnergyRef.current = 0;
    visemeRef.current = 'closed';
  }, []);

  useEffect(() => {
    if (muted && isPlayingRef.current) {
      stopAudio();
    }
  }, [muted, stopAudio]);

  useEffect(() => {
    return () => {
      stopAudio();
      if (audioCtxRef.current && audioCtxRef.current.state !== 'closed') {
        audioCtxRef.current.close().catch(() => undefined);
      }
    };
  }, [stopAudio]);

  const playAudio = useCallback(
    async (
      base64Wav: string,
      visemes: VisemeFrame[] = [],
      onStart?: () => void,
      onEnded?: () => void
    ) => {
      stopAudio();
      if (muted || !base64Wav) {
        onEnded?.();
        return;
      }

      const sessionId = playbackSessionRef.current;

      try {
        const AudioCtx = window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
        if (!audioCtxRef.current || audioCtxRef.current.state === 'closed') {
          audioCtxRef.current = new AudioCtx();
        }
        const ctx = audioCtxRef.current;
        if (ctx.state === 'suspended') {
          await ctx.resume();
        }

        const buffer = await ctx.decodeAudioData(base64ToArrayBuffer(base64Wav));
        if (playbackSessionRef.current !== sessionId) return;

        const analyser = ctx.createAnalyser();
        analyser.fftSize = 256;
        analyser.smoothingTimeConstant = 0.45;
        const timeData = new Uint8Array(analyser.fftSize);

        const source = ctx.createBufferSource();
        source.buffer = buffer;
        source.connect(analyser);
        analyser.connect(ctx.destination);
        sourceRef.current = source;

        const startTime = ctx.currentTime;
        isPlayingRef.current = true;
        onStart?.();

        let visemeIdx = 0;

        const tick = () => {
          if (playbackSessionRef.current !== sessionId || !isPlayingRef.current) return;

          const elapsed = Math.max(0, ctx.currentTime - startTime);

          // Real-time RMS energy from Web Audio API
          analyser.getByteTimeDomainData(timeData);
          let sumSq = 0;
          for (let i = 0; i < timeData.length; i++) {
            const norm = (timeData[i] - 128) / 128;
            sumSq += norm * norm;
          }
          const rms = Math.sqrt(sumSq / timeData.length);
          const liveMouth = Math.min(1, Math.max(0, (rms - 0.015) * 4.5));

          // Combine with backend LipSyncEngine viseme timeline when provided
          let targetMouth = liveMouth;
          let targetViseme = classifyViseme(liveMouth);

          if (visemes.length > 0) {
            while (
              visemeIdx + 1 < visemes.length &&
              visemes[visemeIdx + 1].time_seconds <= elapsed
            ) {
              visemeIdx += 1;
            }
            const frame = visemes[visemeIdx];
            targetMouth = Math.min(1, frame.mouth_open * 0.65 + liveMouth * 0.45);
            targetViseme = targetMouth > 0.08 ? frame.viseme : 'closed';
          }

          mouthOpenRef.current = mouthOpenRef.current * 0.35 + targetMouth * 0.65;
          audioEnergyRef.current = audioEnergyRef.current * 0.4 + Math.min(1, rms * 5) * 0.6;
          visemeRef.current = targetViseme;

          rafRef.current = requestAnimationFrame(tick);
        };

        source.onended = () => {
          if (playbackSessionRef.current !== sessionId) return;
          isPlayingRef.current = false;
          if (rafRef.current !== null) {
            cancelAnimationFrame(rafRef.current);
            rafRef.current = null;
          }
          mouthOpenRef.current = 0;
          audioEnergyRef.current = 0;
          visemeRef.current = 'closed';
          sourceRef.current = null;
          onEnded?.();
        };

        source.start(0);
        rafRef.current = requestAnimationFrame(tick);
      } catch (err) {
        console.error('Web Audio playback failed:', err);
        stopAudio();
        onEnded?.();
      }
    },
    [muted, stopAudio]
  );

  return useMemo(
    () => ({
      mouthOpenRef,
      visemeRef,
      audioEnergyRef,
      isPlayingRef,
      playAudio,
      stopAudio,
    }),
    [playAudio, stopAudio]
  );
}

