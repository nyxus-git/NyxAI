/**
 * components/VoiceVisualizer.tsx
 *
 * Animated audio waveform displayed during voice recording.
 * Uses CSS animations driven by React state — no canvas/WebAudio needed.
 * Shows an idle flat line when not recording, and animated bars when active.
 */

import React, { useEffect, useRef, useState } from 'react';

interface VoiceVisualizerProps {
  isRecording: boolean;
  barCount?: number;
}

export const VoiceVisualizer: React.FC<VoiceVisualizerProps> = ({
  isRecording,
  barCount = 20,
}) => {
  const [heights, setHeights] = useState<number[]>(Array(barCount).fill(4));
  const animFrameRef = useRef<number | null>(null);

  useEffect(() => {
    if (!isRecording) {
      setHeights(Array(barCount).fill(4));
      if (animFrameRef.current) cancelAnimationFrame(animFrameRef.current);
      return;
    }

    const animate = () => {
      setHeights(
        Array.from({ length: barCount }, (_, i) => {
          // Center bars are taller — gives a natural voice waveform shape
          const center = barCount / 2;
          const distFromCenter = Math.abs(i - center) / center;
          const base = 8 + (1 - distFromCenter) * 20;
          const noise = (Math.random() - 0.5) * 24;
          return Math.max(4, Math.min(40, base + noise));
        })
      );
      animFrameRef.current = requestAnimationFrame(animate);
    };

    animFrameRef.current = requestAnimationFrame(animate);
    return () => {
      if (animFrameRef.current) cancelAnimationFrame(animFrameRef.current);
    };
  }, [isRecording, barCount]);

  return (
    <div className="voice-visualizer" aria-hidden="true">
      {heights.map((h, i) => (
        <div
          key={i}
          className={`voice-bar ${isRecording ? 'active' : ''}`}
          style={{
            height: `${h}px`,
            transition: isRecording ? 'height 80ms ease' : 'height 300ms ease',
          }}
        />
      ))}
    </div>
  );
};
