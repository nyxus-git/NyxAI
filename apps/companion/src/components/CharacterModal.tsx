import React, { useRef, useState } from 'react';
import {
  Box,
  Camera,
  Check,
  Loader2,
  RotateCcw,
  Sparkles,
  Trash2,
  Upload,
  Volume2,
  Wand2,
  X,
} from 'lucide-react';
import {
  deleteAvatarPhoto,
  resolveAssetUrl,
  saveAvatarConfig,
  uploadAvatarModel,
  uploadAvatarPhoto,
} from '../services/api';
import { AvatarConfig, AvatarLandmarks, AvatarMode } from '../types/companion';
import {
  DEFAULT_AVATAR_LANDMARKS,
  detectPhotoFaceLandmarks,
} from '../utils/faceLandmarks';

interface CharacterModalProps {
  config: AvatarConfig;
  onConfigChange: (updated: AvatarConfig) => void;
  onClose: () => void;
}

type DragTarget = 'left_eye' | 'right_eye' | 'mouth' | null;

export const CharacterModal: React.FC<CharacterModalProps> = ({
  config,
  onConfigChange,
  onClose,
}) => {
  const [draft, setDraft] = useState<AvatarConfig>(config);
  const [busy, setBusy] = useState(false);
  const [statusMsg, setStatusMsg] = useState<string | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [activeMarker, setActiveMarker] = useState<DragTarget>(null);

  const photoInputRef = useRef<HTMLInputElement | null>(null);
  const modelInputRef = useRef<HTMLInputElement | null>(null);
  const previewBoxRef = useRef<HTMLDivElement | null>(null);

  const voices = config.available_voices ?? [
    { id: 'af_heart', label: 'Heart (Warm, Natural US)' },
    { id: 'af_bella', label: 'Bella (Expressive US)' },
    { id: 'af_nova', label: 'Nova (Clear, Bright US)' },
    { id: 'af_nicole', label: 'Nicole (Soft, Calm US)' },
    { id: 'bf_emma', label: 'Emma (British Warm)' },
  ];

  const handlePhotoUpload = async (file: File) => {
    setBusy(true);
    setErrorMsg(null);
    setStatusMsg('Uploading portrait photo...');
    try {
      const uploaded = await uploadAvatarPhoto(file);
      const resolvedUrl = resolveAssetUrl(uploaded.photo_url);

      let nextLandmarks: AvatarLandmarks = uploaded.landmarks ?? DEFAULT_AVATAR_LANDMARKS;
      let detectNote = 'Photo uploaded! Click markers or use Auto-Align to fine-tune.';

      if (resolvedUrl) {
        setStatusMsg('Detecting face & lip landmarks...');
        const outcome = await detectPhotoFaceLandmarks(resolvedUrl);
        nextLandmarks = outcome.landmarks;
        detectNote = outcome.detected
          ? 'Face & lip landmarks auto-aligned!'
          : outcome.reason || detectNote;
      }

      const finalCfg = await saveAvatarConfig({
        ...uploaded,
        name: draft.name,
        tagline: draft.tagline,
        voice: draft.voice,
        landmarks: nextLandmarks,
      });

      setDraft(finalCfg);
      onConfigChange(finalCfg);
      setStatusMsg(detectNote);
    } catch (err) {
      setErrorMsg(err instanceof Error ? err.message : 'Photo upload failed');
    } finally {
      setBusy(false);
    }
  };

  const handleAutoAlign = async () => {
    const resolvedUrl = resolveAssetUrl(draft.photo_url);
    if (!resolvedUrl) return;
    setBusy(true);
    setErrorMsg(null);
    setStatusMsg('Scanning eyes and lips...');
    try {
      const outcome = await detectPhotoFaceLandmarks(resolvedUrl);
      const next = { ...draft, landmarks: outcome.landmarks };
      setDraft(next);
      setStatusMsg(
        outcome.detected
          ? 'Eyes and mouth auto-aligned!'
          : outcome.reason || 'Could not auto-detect; click a marker below and click the face.'
      );
    } finally {
      setBusy(false);
    }
  };

  const handleRemovePhoto = async () => {
    setBusy(true);
    setErrorMsg(null);
    try {
      const updated = await deleteAvatarPhoto();
      setDraft(updated);
      onConfigChange(updated);
      setStatusMsg('Custom photo removed.');
    } catch (err) {
      setErrorMsg(err instanceof Error ? err.message : 'Could not remove photo');
    } finally {
      setBusy(false);
    }
  };

  const handleModelUpload = async (file: File) => {
    setBusy(true);
    setErrorMsg(null);
    setStatusMsg('Uploading 3D avatar model...');
    try {
      const uploaded = await uploadAvatarModel(file);
      const finalCfg = await saveAvatarConfig({
        ...uploaded,
        name: draft.name,
        tagline: draft.tagline,
        voice: draft.voice,
      });
      setDraft(finalCfg);
      onConfigChange(finalCfg);
      setStatusMsg('3D avatar loaded!');
    } catch (err) {
      setErrorMsg(err instanceof Error ? err.message : 'Model upload failed');
    } finally {
      setBusy(false);
    }
  };

  const handleSave = async () => {
    setBusy(true);
    setErrorMsg(null);
    try {
      const saved = await saveAvatarConfig(draft);
      setDraft(saved);
      onConfigChange(saved);
      onClose();
    } catch (err) {
      setErrorMsg(err instanceof Error ? err.message : 'Failed to save configuration');
    } finally {
      setBusy(false);
    }
  };

  const handlePreviewClick = (e: React.MouseEvent<HTMLDivElement>) => {
    if (!activeMarker || !previewBoxRef.current) return;
    const rect = previewBoxRef.current.getBoundingClientRect();
    const nx = Math.max(0.08, Math.min(0.92, (e.clientX - rect.left) / rect.width));
    const ny = Math.max(0.08, Math.min(0.92, (e.clientY - rect.top) / rect.height));
    setDraft((prev) => ({
      ...prev,
      landmarks: {
        ...prev.landmarks,
        [activeMarker]: {
          ...prev.landmarks[activeMarker],
          x: Number(nx.toFixed(3)),
          y: Number(ny.toFixed(3)),
        },
        ...(activeMarker === 'mouth'
          ? { chin_y: Number(Math.min(0.96, ny + 0.14).toFixed(3)) }
          : {}),
      },
    }));
  };

  const setMode = (mode: AvatarMode) => {
    setDraft((prev) => ({ ...prev, mode }));
  };

  const resolvedPhoto = resolveAssetUrl(draft.photo_url);

  return (
    <div className="modal-backdrop" role="dialog" aria-modal="true" aria-label="Customize Girl Avatar">
      <div className="character-modal">
        <div className="modal-header">
          <div>
            <h2>Companion Studio</h2>
            <p>Upload a portrait photo of a girl, load a 3D VRM/GLB model, or tune her voice.</p>
          </div>
          <button type="button" className="panel-close-btn" onClick={onClose} aria-label="Close">
            <X className="w-4 h-4" />
          </button>
        </div>

        <div className="modal-body">
          {/* Avatar Render Mode Selector */}
          <div className="studio-section">
            <label className="studio-label">Visual Style</label>
            <div className="studio-mode-grid">
              <button
                type="button"
                className={`studio-mode-card ${draft.mode === 'photo' ? 'active' : ''}`}
                onClick={() => (resolvedPhoto ? setMode('photo') : photoInputRef.current?.click())}
              >
                <Camera className="w-5 h-5" />
                <span>Girl Photo</span>
                <small>60 FPS Face Rig</small>
              </button>
              <button
                type="button"
                className={`studio-mode-card ${draft.mode === 'vrm' ? 'active' : ''}`}
                onClick={() => (draft.model_url ? setMode('vrm') : modelInputRef.current?.click())}
              >
                <Box className="w-5 h-5" />
                <span>3D Avatar</span>
                <small>.vrm / .glb</small>
              </button>
              <button
                type="button"
                className={`studio-mode-card ${draft.mode === 'stylized' ? 'active' : ''}`}
                onClick={() => setMode('stylized')}
              >
                <Sparkles className="w-5 h-5" />
                <span>Stylized Nyx</span>
                <small>Animated Vector</small>
              </button>
            </div>
          </div>

          {/* Photo Upload & Landmark Alignment */}
          <div className="studio-section">
            <div className="studio-row-between">
              <label className="studio-label">Portrait Photo Upload</label>
              <div className="studio-btn-group">
                <button
                  type="button"
                  className="studio-secondary-btn"
                  onClick={() => photoInputRef.current?.click()}
                  disabled={busy}
                >
                  <Upload className="w-3.5 h-3.5" />
                  <span>{resolvedPhoto ? 'Replace Photo' : 'Choose Photo'}</span>
                </button>
                {resolvedPhoto && (
                  <>
                    <button
                      type="button"
                      className="studio-secondary-btn"
                      onClick={handleAutoAlign}
                      disabled={busy}
                    >
                      <Wand2 className="w-3.5 h-3.5" />
                      <span>Auto-Align</span>
                    </button>
                    <button
                      type="button"
                      className="studio-danger-btn"
                      onClick={handleRemovePhoto}
                      disabled={busy}
                      title="Remove uploaded photo"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  </>
                )}
              </div>
            </div>

            <input
              ref={photoInputRef}
              type="file"
              accept="image/png,image/jpeg,image/webp"
              hidden
              onChange={(e) => {
                const f = e.target.files?.[0];
                if (f) handlePhotoUpload(f);
                e.target.value = '';
              }}
            />
            <input
              ref={modelInputRef}
              type="file"
              accept=".vrm,.glb"
              hidden
              onChange={(e) => {
                const f = e.target.files?.[0];
                if (f) handleModelUpload(f);
                e.target.value = '';
              }}
            />

            {resolvedPhoto && (
              <div className="alignment-editor">
                <div
                  ref={previewBoxRef}
                  className={`alignment-preview ${activeMarker ? 'picking' : ''}`}
                  onClick={handlePreviewClick}
                >
                  <img src={resolvedPhoto} alt="Uploaded companion portrait" />
                  <div
                    className={`landmark-dot eye ${activeMarker === 'left_eye' ? 'selected' : ''}`}
                    style={{
                      left: `${draft.landmarks.left_eye.x * 100}%`,
                      top: `${draft.landmarks.left_eye.y * 100}%`,
                    }}
                    title="Left Eye"
                  />
                  <div
                    className={`landmark-dot eye ${activeMarker === 'right_eye' ? 'selected' : ''}`}
                    style={{
                      left: `${draft.landmarks.right_eye.x * 100}%`,
                      top: `${draft.landmarks.right_eye.y * 100}%`,
                    }}
                    title="Right Eye"
                  />
                  <div
                    className={`landmark-dot mouth ${activeMarker === 'mouth' ? 'selected' : ''}`}
                    style={{
                      left: `${draft.landmarks.mouth.x * 100}%`,
                      top: `${draft.landmarks.mouth.y * 100}%`,
                    }}
                    title="Mouth Center"
                  />
                </div>

                <div className="alignment-controls">
                  <p className="alignment-hint">
                    Click a marker below, then click the matching spot on her photo to adjust blinking & lip-sync:
                  </p>
                  <div className="marker-pills">
                    {(['left_eye', 'right_eye', 'mouth'] as const).map((key) => (
                      <button
                        key={key}
                        type="button"
                        className={`marker-pill ${activeMarker === key ? 'active' : ''}`}
                        onClick={() => setActiveMarker(activeMarker === key ? null : key)}
                      >
                        {key === 'left_eye' ? 'Left Eye' : key === 'right_eye' ? 'Right Eye' : 'Mouth'}
                      </button>
                    ))}
                    <button
                      type="button"
                      className="marker-pill"
                      onClick={() =>
                        setDraft((prev) => ({ ...prev, landmarks: DEFAULT_AVATAR_LANDMARKS }))
                      }
                    >
                      <RotateCcw className="w-3 h-3" />
                      Reset
                    </button>
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* 3D VRM/GLB Upload */}
          <div className="studio-section">
            <div className="studio-row-between">
              <div>
                <label className="studio-label">3D Model (.vrm / .glb)</label>
                <p className="studio-subtext">
                  Works with VRoid Studio (.vrm) or Avaturn photo-to-3D (.glb) files.
                </p>
              </div>
              <button
                type="button"
                className="studio-secondary-btn"
                onClick={() => modelInputRef.current?.click()}
                disabled={busy}
              >
                <Upload className="w-3.5 h-3.5" />
                <span>{draft.model_url ? 'Replace 3D Model' : 'Upload .vrm/.glb'}</span>
              </button>
            </div>
          </div>

          {/* Name & Voice */}
          <div className="studio-two-col">
            <div className="studio-section">
              <label className="studio-label" htmlFor="girl-name-input">
                Companion Name
              </label>
              <input
                id="girl-name-input"
                type="text"
                className="studio-input"
                value={draft.name}
                maxLength={40}
                onChange={(e) => setDraft((prev) => ({ ...prev, name: e.target.value }))}
              />
            </div>
            <div className="studio-section">
              <label className="studio-label" htmlFor="girl-voice-select">
                <Volume2 className="w-3.5 h-3.5 inline mr-1" />
                Female Voice (Kokoro)
              </label>
              <select
                id="girl-voice-select"
                className="studio-input"
                value={draft.voice}
                onChange={(e) => setDraft((prev) => ({ ...prev, voice: e.target.value }))}
              >
                {voices.map((v) => (
                  <option key={v.id} value={v.id}>
                    {v.label}
                  </option>
                ))}
              </select>
            </div>
          </div>

          {statusMsg && <div className="studio-status ok">{statusMsg}</div>}
          {errorMsg && <div className="studio-status err">{errorMsg}</div>}
        </div>

        <div className="modal-footer">
          <button type="button" className="studio-secondary-btn" onClick={onClose} disabled={busy}>
            Cancel
          </button>
          <button type="button" className="studio-primary-btn" onClick={handleSave} disabled={busy}>
            {busy ? <Loader2 className="w-4 h-4 animate-spin" /> : <Check className="w-4 h-4" />}
            <span>Save & Apply</span>
          </button>
        </div>
      </div>
    </div>
  );
};

