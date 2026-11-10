import { AvatarLandmarks } from '../types/companion';

export const DEFAULT_AVATAR_LANDMARKS: AvatarLandmarks = {
  left_eye: { x: 0.42, y: 0.39, rx: 0.055, ry: 0.024 },
  right_eye: { x: 0.58, y: 0.39, rx: 0.055, ry: 0.024 },
  mouth: { x: 0.50, y: 0.57, rx: 0.085, ry: 0.032 },
  chin_y: 0.71,
};

export interface DetectionOutcome {
  detected: boolean;
  landmarks: AvatarLandmarks;
  reason?: string;
}

const LOCAL_MODEL_URL = '/mediapipe/face_landmarker.task';
const CDN_MODEL_URL =
  'https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task';

function clamp(val: number, min: number, max: number): number {
  return Math.max(min, Math.min(max, val));
}

function loadImageElement(src: string): Promise<HTMLImageElement> {
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.crossOrigin = 'anonymous';
    img.onload = () => resolve(img);
    img.onerror = (err) => reject(err);
    img.src = src;
  });
}

async function resolveModelAssetPath(): Promise<string | null> {
  try {
    const head = await fetch(LOCAL_MODEL_URL, { method: 'HEAD' });
    if (head.ok) return LOCAL_MODEL_URL;
  } catch {
    // ignore local check error
  }
  return CDN_MODEL_URL;
}

/**
 * Automatically detect eye, mouth, and chin regions in a portrait photo using
 * MediaPipe FaceLandmarker when available, falling back gracefully to defaults.
 */
export async function detectPhotoFaceLandmarks(imageUrl: string): Promise<DetectionOutcome> {
  try {
    const img = await loadImageElement(imageUrl);
    const { FaceLandmarker, FilesetResolver } = await import('@mediapipe/tasks-vision');

    const vision = await FilesetResolver.forVisionTasks('/mediapipe/wasm');
    const modelPath = await resolveModelAssetPath();
    if (!modelPath) {
      return {
        detected: false,
        landmarks: DEFAULT_AVATAR_LANDMARKS,
        reason: 'Face landmark model unavailable offline — adjust points manually.',
      };
    }

    const landmarker = await FaceLandmarker.createFromOptions(vision, {
      baseOptions: {
        modelAssetPath: modelPath,
        delegate: 'CPU',
      },
      runningMode: 'IMAGE',
      numFaces: 1,
    });

    try {
      const result = landmarker.detect(img);
      const face = result.faceLandmarks?.[0];
      if (!face || face.length < 400) {
        return {
          detected: false,
          landmarks: DEFAULT_AVATAR_LANDMARKS,
          reason: 'No clear front-facing face found — you can fine-tune markers manually.',
        };
      }

      // Subject's right eye (viewer's left)
      const leOuter = face[33];
      const leInner = face[133];
      const leTop = face[159];
      const leBot = face[145];

      // Subject's left eye (viewer's right)
      const reInner = face[362];
      const reOuter = face[263];
      const reTop = face[386];
      const reBot = face[374];

      // Mouth & chin
      const mLeft = face[61];
      const mRight = face[291];
      const mTop = face[0];
      const mBot = face[17];
      const chin = face[152];

      const landmarks: AvatarLandmarks = {
        left_eye: {
          x: clamp((leOuter.x + leInner.x) / 2, 0.05, 0.95),
          y: clamp((leTop.y + leBot.y) / 2, 0.05, 0.95),
          rx: clamp(Math.abs(leInner.x - leOuter.x) * 0.65, 0.02, 0.25),
          ry: clamp(Math.max(Math.abs(leBot.y - leTop.y) * 1.35, 0.018), 0.01, 0.15),
        },
        right_eye: {
          x: clamp((reInner.x + reOuter.x) / 2, 0.05, 0.95),
          y: clamp((reTop.y + reBot.y) / 2, 0.05, 0.95),
          rx: clamp(Math.abs(reOuter.x - reInner.x) * 0.65, 0.02, 0.25),
          ry: clamp(Math.max(Math.abs(reBot.y - reTop.y) * 1.35, 0.018), 0.01, 0.15),
        },
        mouth: {
          x: clamp((mLeft.x + mRight.x) / 2, 0.05, 0.95),
          y: clamp((mTop.y + mBot.y) / 2, 0.05, 0.95),
          rx: clamp(Math.abs(mRight.x - mLeft.x) * 0.6, 0.03, 0.3),
          ry: clamp(Math.max(Math.abs(mBot.y - mTop.y) * 0.85, 0.022), 0.012, 0.2),
        },
        chin_y: clamp(chin.y, 0.2, 0.98),
      };

      return { detected: true, landmarks };
    } finally {
      landmarker.close();
    }
  } catch (err) {
    return {
      detected: false,
      landmarks: DEFAULT_AVATAR_LANDMARKS,
      reason: err instanceof Error ? err.message : 'Auto-alignment skipped — adjust manually.',
    };
  }
}

