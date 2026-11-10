import React, { useEffect, useRef, useState } from 'react';
import * as THREE from 'three';
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js';
import { VRM, VRMLoaderPlugin, VRMUtils } from '@pixiv/three-vrm';
import { AvatarState, VisemeKind } from '../../types/companion';

interface VrmAvatarCanvasProps {
  modelUrl: string;
  state: AvatarState;
  mouthOpenRef: React.MutableRefObject<number>;
  visemeRef: React.MutableRefObject<VisemeKind>;
  audioEnergyRef: React.MutableRefObject<number>;
}

export const VrmAvatarCanvas: React.FC<VrmAvatarCanvasProps> = ({
  modelUrl,
  state,
  mouthOpenRef,
  visemeRef,
  audioEnergyRef,
}) => {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const stateRef = useRef<AvatarState>(state);
  const pointerRef = useRef<{ x: number; y: number }>({ x: 0, y: 0 });
  const [loading, setLoading] = useState(true);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  useEffect(() => {
    stateRef.current = state;
  }, [state]);

  useEffect(() => {
    const onMove = (e: MouseEvent) => {
      pointerRef.current = {
        x: (e.clientX / Math.max(window.innerWidth, 1)) * 2 - 1,
        y: -((e.clientY / Math.max(window.innerHeight, 1)) * 2 - 1),
      };
    };
    window.addEventListener('mousemove', onMove, { passive: true });
    return () => window.removeEventListener('mousemove', onMove);
  }, []);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    let disposed = false;
    setLoading(true);
    setErrorMsg(null);

    const width = container.clientWidth || 360;
    const height = container.clientHeight || 420;

    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(28, width / height, 0.1, 30);
    camera.position.set(0, 1.45, 1.35);

    const renderer = new THREE.WebGLRenderer({ alpha: true, antialias: true });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    renderer.setSize(width, height);
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    container.innerHTML = '';
    container.appendChild(renderer.domElement);

    // Three-point studio lighting
    const keyLight = new THREE.DirectionalLight(0xffffff, 2.2);
    keyLight.position.set(1.2, 2.0, 2.0);
    scene.add(keyLight);

    const rimLight = new THREE.DirectionalLight(0x00f2fe, 1.4);
    rimLight.position.set(-1.5, 1.6, -1.5);
    scene.add(rimLight);

    const fillLight = new THREE.AmbientLight(0xdbeafe, 0.9);
    scene.add(fillLight);

    let activeVrm: VRM | null = null;
    let activeRoot: THREE.Object3D | null = null;
    const morphMeshes: THREE.Mesh[] = [];
    const lookTarget = new THREE.Object3D();
    lookTarget.position.set(0, 1.45, 2.0);
    scene.add(lookTarget);

    const loader = new GLTFLoader();
    loader.register((parser) => new VRMLoaderPlugin(parser));

    loader.load(
      modelUrl,
      (gltf) => {
        if (disposed) return;
        const vrm = gltf.userData.vrm as VRM | undefined;
        if (vrm) {
          VRMUtils.removeUnnecessaryVertices(gltf.scene);
          VRMUtils.combineSkeletons(gltf.scene);
          vrm.scene.rotation.y = Math.PI; // VRM0/1 front-facing adjustment
          activeVrm = vrm;
          activeRoot = vrm.scene;
          if (vrm.lookAt) {
            vrm.lookAt.target = lookTarget;
          }
          scene.add(vrm.scene);

          // Auto-frame camera onto head/shoulders
          const headNode = vrm.humanoid?.getNormalizedBoneNode('head');
          if (headNode) {
            const headPos = new THREE.Vector3();
            headNode.getWorldPosition(headPos);
            camera.position.set(0, headPos.y - 0.02, 0.95);
            camera.lookAt(0, headPos.y - 0.04, 0);
          }
        } else {
          // Standard GLB (e.g., Avaturn photo-to-3D GLB)
          activeRoot = gltf.scene;
          scene.add(gltf.scene);
          gltf.scene.traverse((obj) => {
            if ((obj as THREE.Mesh).isMesh && (obj as THREE.Mesh).morphTargetDictionary) {
              morphMeshes.push(obj as THREE.Mesh);
            }
          });
          const box = new THREE.Box3().setFromObject(gltf.scene);
          const sizeVec = new THREE.Vector3();
          const centerVec = new THREE.Vector3();
          box.getSize(sizeVec);
          box.getCenter(centerVec);
          const eyeY = box.min.y + sizeVec.y * 0.84;
          camera.position.set(centerVec.x, eyeY, Math.max(0.75, sizeVec.y * 0.52));
          camera.lookAt(centerVec.x, eyeY - sizeVec.y * 0.04, centerVec.z);
        }
        setLoading(false);
      },
      undefined,
      (err) => {
        if (disposed) return;
        console.error('Failed to load 3D avatar:', err);
        setErrorMsg('Failed to load 3D avatar file (.vrm/.glb).');
        setLoading(false);
      }
    );

    const clock = new THREE.Clock();
    let rafId = 0;
    let nextBlink = 2.4;
    let blinkTimer = -1;

    const animate = () => {
      if (disposed) return;
      const dt = Math.min(clock.getDelta(), 0.05);
      const elapsed = clock.elapsedTime;
      const st = stateRef.current;

      // Rim color responds to state
      if (st === 'listening') rimLight.color.setHex(0x10b981);
      else if (st === 'thinking') rimLight.color.setHex(0x9d4edd);
      else if (st === 'happy' || st === 'excited') rimLight.color.setHex(0xf472b6);
      else if (st === 'concerned') rimLight.color.setHex(0xf43f5e);
      else rimLight.color.setHex(0x00f2fe);
      rimLight.intensity = 1.3 + audioEnergyRef.current * 1.4;

      // Blink timer
      let blinkVal = 0;
      if (blinkTimer < 0 && elapsed >= nextBlink) {
        blinkTimer = 0;
      }
      if (blinkTimer >= 0) {
        blinkTimer += dt * 7;
        if (blinkTimer >= 2) {
          blinkTimer = -1;
          nextBlink = elapsed + 2.5 + Math.random() * 3.0;
        } else {
          blinkVal = blinkTimer <= 1 ? blinkTimer : 2 - blinkTimer;
        }
      }

      const mouthOpen = st === 'speaking' ? mouthOpenRef.current : 0;
      const viseme = visemeRef.current;

      if (activeVrm) {
        lookTarget.position.x = pointerRef.current.x * 0.6;
        lookTarget.position.y = camera.position.y + pointerRef.current.y * 0.35;

        const expr = activeVrm.expressionManager;
        if (expr) {
          expr.setValue('blink', blinkVal);
          expr.setValue('aa', viseme === 'wide' || viseme === 'open' ? mouthOpen : mouthOpen * 0.55);
          expr.setValue('ih', viseme === 'slight' ? mouthOpen * 0.8 : 0);
          expr.setValue('ou', viseme === 'open' ? mouthOpen * 0.35 : 0);
          expr.setValue('happy', st === 'happy' || st === 'excited' ? 0.75 : 0);
          expr.setValue('relaxed', st === 'listening' ? 0.35 : 0);
          expr.setValue('sad', st === 'concerned' ? 0.45 : 0);
        }

        const head = activeVrm.humanoid?.getNormalizedBoneNode('head');
        const spine = activeVrm.humanoid?.getNormalizedBoneNode('spine');
        if (spine) {
          spine.rotation.x = Math.sin(elapsed * 1.7) * 0.018;
        }
        if (head) {
          head.rotation.y = Math.sin(elapsed * 0.7) * 0.05 + pointerRef.current.x * 0.08;
          head.rotation.z =
            st === 'listening'
              ? 0.06
              : st === 'thinking'
                ? -0.06
                : Math.sin(elapsed * 0.9) * 0.02;
        }
        activeVrm.update(dt);
      } else if (activeRoot) {
        activeRoot.rotation.y = Math.sin(elapsed * 0.7) * 0.05 + pointerRef.current.x * 0.1;
        activeRoot.position.y = Math.sin(elapsed * 1.8) * 0.008;

        for (const mesh of morphMeshes) {
          const dict = mesh.morphTargetDictionary;
          const infl = mesh.morphTargetInfluences;
          if (!dict || !infl) continue;
          const applyMorph = (keys: string[], value: number) => {
            for (const key of keys) {
              if (dict[key] !== undefined) {
                infl[dict[key]] = value;
              }
            }
          };
          applyMorph(['jawOpen', 'mouthOpen', 'viseme_aa'], mouthOpen);
          applyMorph(['eyeBlinkLeft', 'eyeBlinkRight', 'blink'], blinkVal);
          applyMorph(['mouthSmileLeft', 'mouthSmileRight'], st === 'happy' || st === 'excited' ? 0.6 : 0.1);
        }
      }

      renderer.render(scene, camera);
      rafId = requestAnimationFrame(animate);
    };

    const handleResize = () => {
      if (!container) return;
      const w = container.clientWidth || 360;
      const h = container.clientHeight || 420;
      camera.aspect = w / h;
      camera.updateProjectionMatrix();
      renderer.setSize(w, h);
    };
    window.addEventListener('resize', handleResize);
    rafId = requestAnimationFrame(animate);

    return () => {
      disposed = true;
      cancelAnimationFrame(rafId);
      window.removeEventListener('resize', handleResize);
      renderer.dispose();
      container.innerHTML = '';
    };
  }, [audioEnergyRef, modelUrl, mouthOpenRef, visemeRef]);

  return (
    <div className="vrm-avatar-wrap">
      <div ref={containerRef} className="vrm-canvas-host" />
      {loading && <div className="avatar-loading-badge">Loading 3D Companion...</div>}
      {errorMsg && <div className="avatar-error-note">{errorMsg}</div>}
    </div>
  );
};

