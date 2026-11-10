import React, { useEffect, useRef, useState } from 'react';
import { AvatarLandmarks, AvatarState, VisemeKind } from '../../types/companion';

interface PhotoAvatarCanvasProps {
  photoUrl: string;
  landmarks: AvatarLandmarks;
  state: AvatarState;
  mouthOpenRef: React.MutableRefObject<number>;
  visemeRef: React.MutableRefObject<VisemeKind>;
  audioEnergyRef: React.MutableRefObject<number>;
}

interface SampledColors {
  leftLid: string;
  rightLid: string;
  lipColor: string;
}

const STATE_GLOW: Record<AvatarState, string> = {
  idle: 'rgba(0, 242, 254, 0.35)',
  listening: 'rgba(16, 185, 129, 0.65)',
  thinking: 'rgba(157, 78, 221, 0.65)',
  speaking: 'rgba(0, 242, 254, 0.8)',
  happy: 'rgba(244, 114, 182, 0.65)',
  excited: 'rgba(250, 204, 21, 0.65)',
  confused: 'rgba(245, 158, 11, 0.6)',
  concerned: 'rgba(244, 63, 94, 0.6)',
};

function samplePixelRgb(
  ctx: CanvasRenderingContext2D,
  x: number,
  y: number,
  fallback: [number, number, number]
): string {
  try {
    const px = Math.max(2, Math.min(ctx.canvas.width - 3, Math.round(x)));
    const py = Math.max(2, Math.min(ctx.canvas.height - 3, Math.round(y)));
    const data = ctx.getImageData(px - 2, py - 2, 5, 5).data;
    let r = 0;
    let g = 0;
    let b = 0;
    const count = data.length / 4;
    for (let i = 0; i < data.length; i += 4) {
      r += data[i];
      g += data[i + 1];
      b += data[i + 2];
    }
    return `rgb(${Math.round(r / count)}, ${Math.round(g / count)}, ${Math.round(b / count)})`;
  } catch {
    return `rgb(${fallback[0]}, ${fallback[1]}, ${fallback[2]})`;
  }
}

export const PhotoAvatarCanvas: React.FC<PhotoAvatarCanvasProps> = ({
  photoUrl,
  landmarks,
  state,
  mouthOpenRef,
  visemeRef,
  audioEnergyRef,
}) => {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const stateRef = useRef<AvatarState>(state);
  const landmarksRef = useRef<AvatarLandmarks>(landmarks);
  const pointerRef = useRef<{ x: number; y: number }>({ x: 0, y: 0 });
  const imgRef = useRef<HTMLImageElement | null>(null);
  const sampledRef = useRef<SampledColors>({
    leftLid: 'rgb(225, 185, 168)',
    rightLid: 'rgb(225, 185, 168)',
    lipColor: 'rgb(185, 95, 105)',
  });
  const [loadError, setLoadError] = useState<string | null>(null);

  useEffect(() => {
    stateRef.current = state;
  }, [state]);

  useEffect(() => {
    landmarksRef.current = landmarks;
  }, [landmarks]);

  useEffect(() => {
    const onMove = (e: MouseEvent) => {
      const nx = (e.clientX / Math.max(window.innerWidth, 1)) * 2 - 1;
      const ny = (e.clientY / Math.max(window.innerHeight, 1)) * 2 - 1;
      pointerRef.current = { x: nx, y: ny };
    };
    window.addEventListener('mousemove', onMove, { passive: true });
    return () => window.removeEventListener('mousemove', onMove);
  }, []);

  // Load portrait image and sample eyelid + lip skin tones
  useEffect(() => {
    let active = true;
    setLoadError(null);
    const img = new Image();
    img.crossOrigin = 'anonymous';
    img.onload = () => {
      if (!active) return;
      imgRef.current = img;

      const off = document.createElement('canvas');
      off.width = img.naturalWidth || img.width;
      off.height = img.naturalHeight || img.height;
      const offCtx = off.getContext('2d');
      if (offCtx && off.width > 0 && off.height > 0) {
        offCtx.drawImage(img, 0, 0);
        const lm = landmarksRef.current;
        sampledRef.current = {
          leftLid: samplePixelRgb(
            offCtx,
            lm.left_eye.x * off.width,
            (lm.left_eye.y - lm.left_eye.ry * 1.15) * off.height,
            [225, 185, 168]
          ),
          rightLid: samplePixelRgb(
            offCtx,
            lm.right_eye.x * off.width,
            (lm.right_eye.y - lm.right_eye.ry * 1.15) * off.height,
            [225, 185, 168]
          ),
          lipColor: samplePixelRgb(
            offCtx,
            lm.mouth.x * off.width,
            (lm.mouth.y + lm.mouth.ry * 0.35) * off.height,
            [185, 95, 105]
          ),
        };
      }
    };
    img.onerror = () => {
      if (active) setLoadError('Could not load uploaded portrait photo.');
    };
    img.src = photoUrl;
    return () => {
      active = false;
    };
  }, [photoUrl, landmarks]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    let rafId = 0;
    let nextBlinkAt = performance.now() + 2600;
    let blinkProgress = -1;
    let smoothPtrX = 0;
    let smoothPtrY = 0;
    let smoothJaw = 0;

    const render = (now: number) => {
      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      const rect = canvas.getBoundingClientRect();
      const size = Math.max(240, Math.round(Math.min(rect.width || 360, rect.height || 360)));

      if (canvas.width !== size * dpr || canvas.height !== size * dpr) {
        canvas.width = size * dpr;
        canvas.height = size * dpr;
      }

      ctx.save();
      ctx.scale(dpr, dpr);
      ctx.clearRect(0, 0, size, size);

      const img = imgRef.current;
      if (!img) {
        ctx.restore();
        rafId = requestAnimationFrame(render);
        return;
      }

      const st = stateRef.current;
      const lm = landmarksRef.current;
      const colors = sampledRef.current;
      const t = now * 0.001;

      // Update blink timeline
      if (blinkProgress < 0 && now >= nextBlinkAt) {
        blinkProgress = 0;
      }
      let blinkAmt = 0;
      if (blinkProgress >= 0) {
        blinkProgress += 0.14;
        if (blinkProgress >= 2) {
          blinkProgress = -1;
          nextBlinkAt = now + 2600 + Math.random() * 2800;
          blinkAmt = 0;
        } else {
          blinkAmt = blinkProgress <= 1 ? blinkProgress : 2 - blinkProgress;
        }
      }

      // Smooth cursor gaze & state posture
      smoothPtrX += (pointerRef.current.x - smoothPtrX) * 0.06;
      smoothPtrY += (pointerRef.current.y - smoothPtrY) * 0.06;

      const energy = audioEnergyRef.current;
      const targetMouth = st === 'speaking' ? mouthOpenRef.current : 0;
      smoothJaw += (targetMouth - smoothJaw) * 0.45;

      const breathY = Math.sin(t * 1.9) * 2.5;
      const swayX = Math.sin(t * 0.9) * 2.2 + smoothPtrX * 4;
      const headTilt =
        st === 'listening'
          ? 0.032 + Math.sin(t * 1.4) * 0.008
          : st === 'thinking'
            ? -0.028 + Math.sin(t * 1.1) * 0.01
            : st === 'confused'
              ? 0.045
              : Math.sin(t * 0.85) * 0.012 + smoothPtrX * 0.015;
      const scaleBreath =
        1.03 +
        Math.sin(t * 1.9) * 0.008 +
        (st === 'speaking' ? energy * 0.015 : 0) +
        (st === 'listening' ? 0.015 : 0);

      const cx = size / 2;
      const cy = size / 2;
      const radius = size * 0.44;

      // Ambient glow ring behind portrait
      const glowColor = STATE_GLOW[st] ?? STATE_GLOW.idle;
      ctx.save();
      ctx.beginPath();
      ctx.arc(cx, cy, radius + 4 + energy * 10, 0, Math.PI * 2);
      ctx.fillStyle = 'rgba(10, 15, 28, 0.9)';
      ctx.shadowColor = glowColor;
      ctx.shadowBlur = 24 + energy * 24;
      ctx.fill();
      ctx.restore();

      // Circular portrait clip
      ctx.save();
      ctx.beginPath();
      ctx.arc(cx, cy, radius, 0, Math.PI * 2);
      ctx.clip();

      // Cover-fit image geometry
      const imgAspect = img.naturalWidth / Math.max(img.naturalHeight, 1);
      let drawW = size;
      let drawH = size;
      if (imgAspect > 1) {
        drawH = size;
        drawW = size * imgAspect;
      } else {
        drawW = size;
        drawH = size / imgAspect;
      }
      const imgX = (size - drawW) / 2;
      const imgY = (size - drawH) / 2;

      // Apply organic head & breathing transform
      ctx.translate(cx + swayX, cy + breathY + smoothPtrY * 2.5);
      ctx.rotate(headTilt);
      ctx.scale(scaleBreath, scaleBreath);
      ctx.translate(-cx, -cy);

      // Draw full portrait base
      ctx.drawImage(img, imgX, imgY, drawW, drawH);

      // Helper to map normalized photo coords into canvas coordinates
      const px = (nx: number) => imgX + nx * drawW;
      const py = (ny: number) => imgY + ny * drawH;

      // Real-time lip-sync jaw drop & mouth cavity
      if (smoothJaw > 0.015) {
        const mx = px(lm.mouth.x);
        const my = py(lm.mouth.y);
        const mrx = lm.mouth.rx * drawW;
        const mry = lm.mouth.ry * drawH;
        const viseme = visemeRef.current;
        const widthFactor = viseme === 'wide' ? 1.1 : viseme === 'slight' ? 0.88 : 1.0;
        const jawDrop = smoothJaw * Math.max(mry * 1.45, size * 0.042);

        // 1. Shift lower jaw/chin slice smoothly downward
        const chinBottom = Math.min(imgY + drawH, py(lm.chin_y) + size * 0.08);
        const sliceTop = my + mry * 0.1;
        const sliceHeight = Math.max(12, chinBottom - sliceTop);

        ctx.save();
        ctx.beginPath();
        ctx.ellipse(
          mx,
          sliceTop + sliceHeight * 0.45 + jawDrop * 0.45,
          mrx * 1.95,
          sliceHeight * 0.65,
          0,
          0,
          Math.PI * 2
        );
        ctx.clip();
        ctx.drawImage(img, imgX, imgY + jawDrop, drawW, drawH);
        ctx.restore();

        // 2. Feathered dark inner mouth cavity + subtle upper teeth highlight
        const openRx = mrx * 0.85 * widthFactor;
        const openRy = Math.max(2.2, jawDrop * 0.56 + mry * 0.28);
        const cavityY = my + jawDrop * 0.42;

        ctx.save();
        ctx.beginPath();
        ctx.ellipse(mx, cavityY, openRx, openRy, 0, 0, Math.PI * 2);
        ctx.clip();

        const mouthGrad = ctx.createRadialGradient(
          mx,
          cavityY - openRy * 0.2,
          openRx * 0.1,
          mx,
          cavityY,
          Math.max(openRx, openRy) * 1.15
        );
        mouthGrad.addColorStop(0, '#1f070c');
        mouthGrad.addColorStop(0.7, '#3a0e18');
        mouthGrad.addColorStop(1, colors.lipColor);
        ctx.fillStyle = mouthGrad;
        ctx.fillRect(mx - openRx - 2, cavityY - openRy - 2, openRx * 2 + 4, openRy * 2 + 4);

        if (smoothJaw > 0.25) {
          ctx.fillStyle = `rgba(244, 236, 234, ${Math.min(0.65, smoothJaw * 0.75)})`;
          ctx.beginPath();
          ctx.ellipse(mx, cavityY - openRy * 0.58, openRx * 0.68, openRy * 0.28, 0, 0, Math.PI * 2);
          ctx.fill();
        }
        ctx.restore();
      } else if (st === 'happy' || st === 'excited') {
        // Subtle warm smile highlight
        const mx = px(lm.mouth.x);
        const my = py(lm.mouth.y);
        const mrx = lm.mouth.rx * drawW;
        ctx.save();
        ctx.strokeStyle = 'rgba(255, 220, 228, 0.28)';
        ctx.lineWidth = 2;
        ctx.beginPath();
        ctx.moveTo(mx - mrx * 0.75, my - 1);
        ctx.quadraticCurveTo(mx, my + 5, mx + mrx * 0.75, my - 1);
        ctx.stroke();
        ctx.restore();
      }

      // Natural blinking eyelids over detected eye regions
      if (blinkAmt > 0.04) {
        const drawEyelid = (eye: AvatarLandmarks['left_eye'], lidColor: string) => {
          const ex = px(eye.x);
          const ey = py(eye.y);
          const erx = eye.rx * drawW * 1.15;
          const ery = eye.ry * drawH * 1.35;

          ctx.save();
          ctx.beginPath();
          ctx.ellipse(ex, ey, erx, ery, 0, 0, Math.PI * 2);
          ctx.clip();

          const lidH = ery * 2.1 * blinkAmt;
          ctx.fillStyle = lidColor;
          ctx.globalAlpha = Math.min(0.95, 0.35 + blinkAmt * 0.65);
          ctx.fillRect(ex - erx - 2, ey - ery - 2, erx * 2 + 4, lidH);

          // Delicate lash line at bottom of descending eyelid
          ctx.strokeStyle = 'rgba(24, 18, 22, 0.75)';
          ctx.lineWidth = 1.8;
          ctx.beginPath();
          const lashY = ey - ery + lidH;
          ctx.moveTo(ex - erx * 0.9, lashY - 1);
          ctx.quadraticCurveTo(ex, lashY + 2, ex + erx * 0.9, lashY - 1);
          ctx.stroke();
          ctx.restore();
        };

        drawEyelid(lm.left_eye, colors.leftLid);
        drawEyelid(lm.right_eye, colors.rightLid);
      }

      // Subtle studio vignette inside portrait frame
      const vignette = ctx.createRadialGradient(cx, cy, radius * 0.68, cx, cy, radius);
      vignette.addColorStop(0, 'rgba(0,0,0,0)');
      vignette.addColorStop(1, 'rgba(6, 10, 20, 0.42)');
      ctx.fillStyle = vignette;
      ctx.fillRect(0, 0, size, size);

      ctx.restore();

      // Outer crisp holographic rim stroke
      ctx.save();
      ctx.beginPath();
      ctx.arc(cx, cy, radius, 0, Math.PI * 2);
      ctx.lineWidth = 2 + energy * 2.5;
      ctx.strokeStyle = glowColor;
      ctx.stroke();
      ctx.restore();

      ctx.restore();
      rafId = requestAnimationFrame(render);
    };

    rafId = requestAnimationFrame(render);
    return () => cancelAnimationFrame(rafId);
  }, [audioEnergyRef, mouthOpenRef, visemeRef]);

  return (
    <div className="photo-avatar-wrap">
      <canvas ref={canvasRef} className="photo-avatar-canvas" aria-label="Animated girl portrait" />
      {loadError && <div className="avatar-error-note">{loadError}</div>}
    </div>
  );
};

