import React, { useEffect, useRef, useState } from 'react';

interface VoiceVisualizerProps {
  isRecording: boolean;
  micLevelRef?: React.MutableRefObject<number>;
  barCount?: number;
}

export const VoiceVisualizer: React.FC<VoiceVisualizerProps> = ({
  isRecording,
  micLevelRef,
  barCount = 24,
}) => {
  const [heights, setHeights] = useState<number[]>(Array(barCount).fill(4));
  const animFrameRef = useRef<number | null>(null);

  useEffect(() => {
    if (!isRecording) {
      setHeights(Array(barCount).fill(4));
      if (animFrameRef.current) cancelAnimationFrame(animFrameRef.current);
      return;
    }

    const animate = (now: number) => {
      const level = micLevelRef ? micLevelRef.current : 0.35;
      const t = now * 0.01;
      setHeights(
        Array.from({ length: barCount }, (_, i) => {
          const center = barCount / 2;
          const distFromCenter = Math.abs(i - center) / center;
          const envelope = 1 - distFromCenter * 0.65;
          const ripple = Math.sin(t + i * 0.6) * 0.35 + 0.65;
          const h = 4 + (8 + level * 34) * envelope * ripple;
          return Math.max(4, Math.min(42, h));
        })
      );
      animFrameRef.current = requestAnimationFrame(animate);
    };

    animFrameRef.current = requestAnimationFrame(animate);
    return () => {
      if (animFrameRef.current) cancelAnimationFrame(animFrameRef.current);
    };
  }, [isRecording, barCount, micLevelRef]);

  return (
    <div className="voice-visualizer" aria-hidden="true">
      {heights.map((h, i) => (
        <div
          key={i}
          className={`voice-bar ${isRecording ? 'active' : ''}`}
          style={{ height: `${h}px` }}
        />
      ))}
    </div>
  );
};
