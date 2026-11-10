import React, { useEffect, useRef } from 'react';
import { AvatarState, VisemeKind } from '../../types/companion';

interface StylizedGirlCanvasProps {
  state: AvatarState;
  mouthOpenRef: React.MutableRefObject<number>;
  visemeRef: React.MutableRefObject<VisemeKind>;
  audioEnergyRef: React.MutableRefObject<number>;
}

const AURA_COLORS: Record<AvatarState, string> = {
  idle: '#00f2fe',
  listening: '#10b981',
  thinking: '#a855f7',
  speaking: '#00f2fe',
  happy: '#f472b6',
  excited: '#facc15',
  confused: '#f59e0b',
  concerned: '#f43f5e',
};

export const StylizedGirlCanvas: React.FC<StylizedGirlCanvasProps> = ({
  state,
  mouthOpenRef,
  visemeRef,
  audioEnergyRef,
}) => {
  const eyeGroupRef = useRef<SVGGElement | null>(null);
  const leftPupilRef = useRef<SVGGElement | null>(null);
  const rightPupilRef = useRef<SVGGElement | null>(null);
  const mouthPathRef = useRef<SVGPathElement | null>(null);
  const innerMouthRef = useRef<SVGEllipseElement | null>(null);
  const headGroupRef = useRef<SVGGElement | null>(null);
  const pointerRef = useRef<{ x: number; y: number }>({ x: 0, y: 0 });
  const stateRef = useRef<AvatarState>(state);

  useEffect(() => {
    stateRef.current = state;
  }, [state]);

  useEffect(() => {
    const onMove = (e: MouseEvent) => {
      pointerRef.current = {
        x: (e.clientX / Math.max(window.innerWidth, 1)) * 2 - 1,
        y: (e.clientY / Math.max(window.innerHeight, 1)) * 2 - 1,
      };
    };
    window.addEventListener('mousemove', onMove, { passive: true });
    return () => window.removeEventListener('mousemove', onMove);
  }, []);

  useEffect(() => {
    let rafId = 0;
    let nextBlink = performance.now() + 2400;
    let blinkStep = -1;
    let smoothX = 0;
    let smoothY = 0;
    let smoothMouth = 0;

    const animate = (now: number) => {
      const t = now * 0.001;
      const st = stateRef.current;

      smoothX += (pointerRef.current.x - smoothX) * 0.08;
      smoothY += (pointerRef.current.y - smoothY) * 0.08;

      const targetMouth = st === 'speaking' ? mouthOpenRef.current : 0;
      smoothMouth += (targetMouth - smoothMouth) * 0.45;

      // Eye blink animation
      if (blinkStep < 0 && now >= nextBlink) {
        blinkStep = 0;
      }
      let eyeScaleY = 1;
      if (blinkStep >= 0) {
        blinkStep += 0.16;
        if (blinkStep >= 2) {
          blinkStep = -1;
          nextBlink = now + 2600 + Math.random() * 2800;
        } else {
          const b = blinkStep <= 1 ? blinkStep : 2 - blinkStep;
          eyeScaleY = Math.max(0.06, 1 - b * 0.94);
        }
      }

      if (eyeGroupRef.current) {
        eyeGroupRef.current.style.transform = `scaleY(${eyeScaleY.toFixed(3)})`;
      }

      // Gaze tracking (upward glance while thinking)
      const gazeX = st === 'thinking' ? Math.sin(t * 1.3) * 2.5 : smoothX * 3.2;
      const gazeY = st === 'thinking' ? -2.2 : smoothY * 2.2;
      const pupilTransform = `translate(${gazeX.toFixed(2)}px, ${gazeY.toFixed(2)}px)`;
      if (leftPupilRef.current) leftPupilRef.current.style.transform = pupilTransform;
      if (rightPupilRef.current) rightPupilRef.current.style.transform = pupilTransform;

      // Head breathing & state tilt
      if (headGroupRef.current) {
        const tilt =
          st === 'listening'
            ? 3.2
            : st === 'thinking'
              ? -2.8
              : st === 'confused'
                ? 4.2
                : Math.sin(t * 0.9) * 1.1 + smoothX * 1.4;
        const bobY = Math.sin(t * 1.9) * 2.4 - audioEnergyRef.current * 1.8;
        headGroupRef.current.style.transform = `translateY(${bobY.toFixed(2)}px) rotate(${tilt.toFixed(2)}deg)`;
      }

      // Dynamic mouth lip-sync & emotional expressions
      if (innerMouthRef.current && mouthPathRef.current) {
        if (st === 'speaking' && smoothMouth > 0.04) {
          const viseme = visemeRef.current;
          const rx = viseme === 'wide' ? 11.5 : viseme === 'slight' ? 7.5 : 9.5;
          const ry = Math.max(2, smoothMouth * 10.5);
          innerMouthRef.current.setAttribute('rx', rx.toFixed(2));
          innerMouthRef.current.setAttribute('ry', ry.toFixed(2));
          innerMouthRef.current.style.opacity = '1';
          mouthPathRef.current.style.opacity = '0';
        } else {
          innerMouthRef.current.style.opacity = '0';
          mouthPathRef.current.style.opacity = '1';
          if (st === 'happy' || st === 'excited') {
            mouthPathRef.current.setAttribute('d', 'M 142 192 Q 160 206 178 192');
          } else if (st === 'listening') {
            mouthPathRef.current.setAttribute('d', 'M 150 194 Q 160 198 170 194');
          } else if (st === 'thinking' || st === 'confused') {
            mouthPathRef.current.setAttribute('d', 'M 148 195 Q 156 192 162 195 Q 168 198 173 193');
          } else if (st === 'concerned') {
            mouthPathRef.current.setAttribute('d', 'M 146 198 Q 160 191 174 198');
          } else {
            mouthPathRef.current.setAttribute('d', 'M 145 193 Q 160 201 175 193');
          }
        }
      }

      rafId = requestAnimationFrame(animate);
    };

    rafId = requestAnimationFrame(animate);
    return () => cancelAnimationFrame(rafId);
  }, [audioEnergyRef, mouthOpenRef, visemeRef]);

  const accent = AURA_COLORS[state] ?? '#00f2fe';

  return (
    <div className="stylized-avatar-wrap">
      <svg
        className={`stylized-girl-svg ${state}`}
        viewBox="0 0 320 360"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
        role="img"
        aria-label="Animated AI Companion Girl"
      >
        <defs>
          <radialGradient id="studioAura" cx="50%" cy="45%" r="50%">
            <stop offset="0%" stopColor={accent} stopOpacity="0.28" />
            <stop offset="100%" stopColor={accent} stopOpacity="0" />
          </radialGradient>
          <linearGradient id="girlHair" x1="20%" y1="0%" x2="80%" y2="100%">
            <stop offset="0%" stopColor="#1e1b4b" />
            <stop offset="50%" stopColor="#4338ca" />
            <stop offset="100%" stopColor="#06b6d4" />
          </linearGradient>
          <linearGradient id="girlHairShade" x1="0%" y1="0%" x2="0%" y2="100%">
            <stop offset="0%" stopColor="#17153b" />
            <stop offset="100%" stopColor="#312e81" />
          </linearGradient>
          <linearGradient id="girlSkin" x1="0%" y1="0%" x2="0%" y2="100%">
            <stop offset="0%" stopColor="#fff1f2" />
            <stop offset="100%" stopColor="#fecdd3" />
          </linearGradient>
          <linearGradient id="girlIris" x1="0%" y1="0%" x2="0%" y2="100%">
            <stop offset="0%" stopColor="#0ea5e9" />
            <stop offset="55%" stopColor="#6366f1" />
            <stop offset="100%" stopColor="#00f2fe" />
          </linearGradient>
          <linearGradient id="girlTop" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stopColor="#0f172a" />
            <stop offset="100%" stopColor="#1e293b" />
          </linearGradient>
        </defs>

        <circle cx="160" cy="170" r="148" fill="url(#studioAura)" />

        {/* Back flowing hair */}
        <path
          d="M 86 135 C 62 200, 62 285, 88 338 L 232 338 C 258 285, 258 200, 234 135 C 218 75, 102 75, 86 135 Z"
          fill="url(#girlHairShade)"
        />

        {/* Shoulders & Modern Collar */}
        <path
          d="M 74 348 C 78 272, 114 248, 160 248 C 206 248, 242 272, 246 348 Z"
          fill="url(#girlTop)"
          stroke={accent}
          strokeOpacity="0.45"
          strokeWidth="1.8"
        />
        <path d="M 122 254 L 160 286 L 198 254" stroke={accent} strokeWidth="2" strokeLinecap="round" opacity="0.85" />
        <circle cx="160" cy="298" r="5" fill={accent} />

        {/* Neck */}
        <rect x="145" y="212" width="30" height="44" rx="12" fill="url(#girlSkin)" />
        <path d="M 145 224 Q 160 236 175 224" fill="#fda4af" opacity="0.35" />

        {/* Head & Face Group */}
        <g ref={headGroupRef} style={{ transformOrigin: '160px 160px', transition: 'transform 0.08s linear' }}>
          {/* Ears */}
          <ellipse cx="100" cy="160" rx="8" ry="13" fill="url(#girlSkin)" />
          <ellipse cx="220" cy="160" rx="8" ry="13" fill="url(#girlSkin)" />

          {/* Face Contour */}
          <path
            d="M 102 142 C 102 202, 130 226, 160 226 C 190 226, 218 202, 218 142 C 218 96, 192 80, 160 80 C 128 80, 102 96, 102 142 Z"
            fill="url(#girlSkin)"
          />

          {/* Soft Blush */}
          <ellipse
            cx="122"
            cy="174"
            rx="12"
            ry="6"
            fill="#fb7185"
            opacity={state === 'happy' || state === 'excited' ? 0.55 : 0.28}
          />
          <ellipse
            cx="198"
            cy="174"
            rx="12"
            ry="6"
            fill="#fb7185"
            opacity={state === 'happy' || state === 'excited' ? 0.55 : 0.28}
          />

          {/* Expressive Eyes */}
          <g ref={eyeGroupRef} style={{ transformOrigin: '160px 154px' }}>
            {/* Left Eye */}
            <ellipse cx="131" cy="154" rx="14" ry="15" fill="#ffffff" />
            <g ref={leftPupilRef}>
              <ellipse cx="132" cy="155" rx="9.5" ry="11.5" fill="url(#girlIris)" />
              <circle cx="132" cy="155" r="4.5" fill="#090d16" />
              <circle cx="128" cy="150" r="3.2" fill="#ffffff" />
              <circle cx="136" cy="159" r="1.5" fill="#ffffff" opacity="0.85" />
            </g>
            <path d="M 115 148 Q 131 136 146 149" stroke="#1e1b4b" strokeWidth="3.2" strokeLinecap="round" />

            {/* Right Eye */}
            <ellipse cx="189" cy="154" rx="14" ry="15" fill="#ffffff" />
            <g ref={rightPupilRef}>
              <ellipse cx="188" cy="155" rx="9.5" ry="11.5" fill="url(#girlIris)" />
              <circle cx="188" cy="155" r="4.5" fill="#090d16" />
              <circle cx="184" cy="150" r="3.2" fill="#ffffff" />
              <circle cx="192" cy="159" r="1.5" fill="#ffffff" opacity="0.85" />
            </g>
            <path d="M 174 149 Q 189 136 205 148" stroke="#1e1b4b" strokeWidth="3.2" strokeLinecap="round" />
          </g>

          {/* Eyebrows */}
          <path
            d={state === 'concerned' ? 'M 117 134 Q 131 131 143 128' : 'M 117 132 Q 131 126 144 132'}
            stroke="#312e81"
            strokeWidth="2.8"
            strokeLinecap="round"
          />
          <path
            d={state === 'concerned' ? 'M 177 128 Q 189 131 203 134' : 'M 176 132 Q 189 126 203 132'}
            stroke="#312e81"
            strokeWidth="2.8"
            strokeLinecap="round"
          />

          {/* Delicate Nose */}
          <path d="M 159 170 L 160 175 L 163 175" stroke="#e11d48" strokeOpacity="0.45" strokeWidth="1.6" strokeLinecap="round" />

          {/* Lip-Sync Mouth */}
          <ellipse
            ref={innerMouthRef}
            cx="160"
            cy="195"
            rx="9"
            ry="5"
            fill="#881337"
            stroke="#fb7185"
            strokeWidth="1.6"
            style={{ opacity: 0 }}
          />
          <path
            ref={mouthPathRef}
            d="M 145 193 Q 160 201 175 193"
            stroke="#be123c"
            strokeWidth="2.6"
            strokeLinecap="round"
            fill="none"
          />

          {/* Side Hair Locks & Bangs */}
          <path
            d="M 94 148 C 90 88, 126 66, 160 66 C 194 66, 230 88, 226 148 C 216 112, 198 102, 180 112 C 170 98, 152 96, 140 114 C 122 102, 104 114, 94 148 Z"
            fill="url(#girlHair)"
          />
          <path d="M 160 66 C 164 96, 152 126, 142 138 C 156 122, 170 100, 172 70 Z" fill="#1e1b4b" opacity="0.65" />
          <path d="M 95 142 C 88 188, 92 232, 108 262 C 102 220, 102 180, 106 146 Z" fill="url(#girlHair)" />
          <path d="M 225 142 C 232 188, 228 232, 212 262 C 218 220, 218 180, 214 146 Z" fill="url(#girlHair)" />

          {/* Subtle Cyber Hair Pin */}
          <rect x="200" y="102" width="16" height="5" rx="2.5" transform="rotate(-18 200 102)" fill={accent} />
        </g>
      </svg>
    </div>
  );
};

