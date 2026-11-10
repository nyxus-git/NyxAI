/**
 * Downsamples captured Web Audio Float32 PCM chunks to 16 kHz mono 16-bit RIFF WAV
 * and returns a base64-encoded string ready for WhisperTranscriber.
 */

const TARGET_SAMPLE_RATE = 16000;

export function downsampleTo16k(chunks: Float32Array[], inputRate: number): Float32Array {
  let totalLength = 0;
  for (const chunk of chunks) {
    totalLength += chunk.length;
  }
  const merged = new Float32Array(totalLength);
  let offset = 0;
  for (const chunk of chunks) {
    merged.set(chunk, offset);
    offset += chunk.length;
  }

  if (inputRate === TARGET_SAMPLE_RATE || totalLength === 0) {
    return merged;
  }

  const ratio = inputRate / TARGET_SAMPLE_RATE;
  const outputLength = Math.max(1, Math.round(totalLength / ratio));
  const result = new Float32Array(outputLength);

  for (let i = 0; i < outputLength; i++) {
    const start = Math.floor(i * ratio);
    const end = Math.min(totalLength, Math.floor((i + 1) * ratio));
    let sum = 0;
    let count = 0;
    for (let j = start; j < end; j++) {
      sum += merged[j];
      count++;
    }
    result[i] = count > 0 ? sum / count : merged[Math.min(start, totalLength - 1)];
  }
  return result;
}

export function encodeWav16kBase64(chunks: Float32Array[], inputRate: number): {
  base64: string;
  durationSec: number;
  peak: number;
} {
  const samples = downsampleTo16k(chunks, inputRate);
  const numSamples = samples.length;
  const buffer = new ArrayBuffer(44 + numSamples * 2);
  const view = new DataView(buffer);

  const writeStr = (pos: number, s: string) => {
    for (let i = 0; i < s.length; i++) {
      view.setUint8(pos + i, s.charCodeAt(i));
    }
  };

  // RIFF header
  writeStr(0, 'RIFF');
  view.setUint32(4, 36 + numSamples * 2, true);
  writeStr(8, 'WAVE');
  writeStr(12, 'fmt ');
  view.setUint32(16, 16, true); // PCM chunk size
  view.setUint16(20, 1, true); // PCM format
  view.setUint16(22, 1, true); // Mono
  view.setUint32(24, TARGET_SAMPLE_RATE, true);
  view.setUint32(28, TARGET_SAMPLE_RATE * 2, true); // byte rate
  view.setUint16(32, 2, true); // block align
  view.setUint16(34, 16, true); // bits per sample
  writeStr(36, 'data');
  view.setUint32(40, numSamples * 2, true);

  let peak = 0;
  let byteOffset = 44;
  for (let i = 0; i < numSamples; i++) {
    const s = Math.max(-1, Math.min(1, samples[i]));
    const abs = Math.abs(s);
    if (abs > peak) peak = abs;
    view.setInt16(byteOffset, s < 0 ? s * 0x8000 : s * 0x7fff, true);
    byteOffset += 2;
  }

  const bytes = new Uint8Array(buffer);
  let binary = '';
  const chunkSize = 0x8000;
  for (let i = 0; i < bytes.length; i += chunkSize) {
    binary += String.fromCharCode(...bytes.subarray(i, i + chunkSize));
  }

  return {
    base64: window.btoa(binary),
    durationSec: numSamples / TARGET_SAMPLE_RATE,
    peak,
  };
}

