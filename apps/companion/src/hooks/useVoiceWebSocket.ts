import { useCallback, useEffect, useRef, useState } from 'react';
import {
  API_BASE,
  confirmAgentTool,
  fetchConversationDetail,
  getWebSocketUrl,
  sendChat,
} from '../services/api';
import { AvatarState, ChatMessage, VisemeFrame } from '../types/companion';
import { encodeWav16kBase64 } from '../utils/wavRecorder';
import { LipSyncLiveState, useAudioLipSync } from './useAudioLipSync';

export type VoicePhase =
  | 'off'
  | 'starting'
  | 'listening'
  | 'hearing'
  | 'processing'
  | 'speaking';

export interface PendingToolAction {
  toolName: string;
  arguments: Record<string, unknown>;
}

interface UseVoiceCompanionOptions {
  mode: 'companion' | 'agent';
  voice: string;
  muted: boolean;
  autoApprove: boolean;
}

export interface UseVoiceCompanionReturn {
  avatarState: AvatarState;
  voicePhase: VoicePhase;
  voiceSessionActive: boolean;
  messages: ChatMessage[];
  liveSubtitle: string;
  conversationId: string | null;
  isRecording: boolean;
  isConnected: boolean;
  errorBanner: string | null;
  pendingAction: PendingToolAction | null;
  micLevelRef: React.MutableRefObject<number>;
  lipSync: LipSyncLiveState;
  startVoiceSession: () => Promise<void>;
  endVoiceSession: () => void;
  sendCurrentVoiceTurn: () => void;
  interruptSpeaking: () => void;
  sendTextMessage: (text: string) => Promise<void>;
  replayMessageAudio: (msg: ChatMessage) => void;
  approvePendingAction: () => Promise<void>;
  dismissPendingAction: () => void;
  startNewConversation: () => void;
  loadConversation: (id: string) => Promise<void>;
  clearError: () => void;
}

const WORKLET_CODE = `
class NyxMicCaptureProcessor extends AudioWorkletProcessor {
  process(inputs) {
    const input = inputs[0];
    if (input && input[0] && input[0].length > 0) {
      this.port.postMessage(new Float32Array(input[0]));
    }
    return true;
  }
}
registerProcessor('nyx-mic-capture', NyxMicCaptureProcessor);
`;

export function useVoiceWebSocket({
  mode,
  voice,
  muted,
  autoApprove,
}: UseVoiceCompanionOptions): UseVoiceCompanionReturn {
  const [avatarState, setAvatarState] = useState<AvatarState>('idle');
  const [voicePhase, setVoicePhase] = useState<VoicePhase>('off');
  const [voiceSessionActive, setVoiceSessionActive] = useState(false);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [liveSubtitle, setLiveSubtitle] = useState<string>('');
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [isRecording, setIsRecording] = useState(false);
  const [isConnected, setIsConnected] = useState(false);
  const [errorBanner, setErrorBanner] = useState<string | null>(null);
  const [pendingAction, setPendingAction] = useState<PendingToolAction | null>(null);

  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimerRef = useRef<number | null>(null);
  const pingTimerRef = useRef<number | null>(null);
  const expressionResetRef = useRef<number | null>(null);
  const nextTurnTimerRef = useRef<number | null>(null);

  // Web Audio PCM capture refs
  const micStreamRef = useRef<MediaStream | null>(null);
  const micCtxRef = useRef<AudioContext | null>(null);
  const micSourceRef = useRef<MediaStreamAudioSourceNode | null>(null);
  const micWorkletRef = useRef<AudioWorkletNode | null>(null);
  const micProcessorRef = useRef<ScriptProcessorNode | null>(null);
  const micGainRef = useRef<GainNode | null>(null);
  const pcmChunksRef = useRef<Float32Array[]>([]);
  const sampleRateRef = useRef<number>(48000);
  const isRecordingRef = useRef<boolean>(false);
  const voiceSessionRef = useRef<boolean>(false);
  const micLevelRef = useRef<number>(0);

  const conversationIdRef = useRef<string | null>(conversationId);
  const modeRef = useRef(mode);
  const voiceRef = useRef(voice);
  const mutedRef = useRef(muted);
  const autoApproveRef = useRef(autoApprove);

  useEffect(() => {
    conversationIdRef.current = conversationId;
  }, [conversationId]);
  useEffect(() => {
    modeRef.current = mode;
  }, [mode]);
  useEffect(() => {
    voiceRef.current = voice;
  }, [voice]);
  useEffect(() => {
    mutedRef.current = muted;
  }, [muted]);
  useEffect(() => {
    autoApproveRef.current = autoApprove;
  }, [autoApprove]);

  const lipSync = useAudioLipSync(muted);
  const lipSyncRef = useRef(lipSync);
  useEffect(() => {
    lipSyncRef.current = lipSync;
  }, [lipSync]);

  const startListeningTurnRef = useRef<() => Promise<void>>(async () => undefined);

  const scheduleExpressionReset = useCallback((emotion?: AvatarState, delayMs = 2200) => {
    if (expressionResetRef.current !== null) {
      window.clearTimeout(expressionResetRef.current);
      expressionResetRef.current = null;
    }
    if (!emotion || emotion === 'idle') {
      setAvatarState('idle');
      return;
    }
    setAvatarState(emotion);
    expressionResetRef.current = window.setTimeout(() => {
      setAvatarState((curr) => (curr === emotion ? 'idle' : curr));
    }, delayMs);
  }, []);

  const scheduleNextVoiceTurn = useCallback((delayMs = 280) => {
    if (nextTurnTimerRef.current !== null) {
      window.clearTimeout(nextTurnTimerRef.current);
      nextTurnTimerRef.current = null;
    }
    if (!voiceSessionRef.current) {
      setVoicePhase('off');
      return;
    }
    nextTurnTimerRef.current = window.setTimeout(() => {
      if (voiceSessionRef.current && !isRecordingRef.current && !lipSyncRef.current.isPlayingRef.current) {
        void startListeningTurnRef.current();
      }
    }, delayMs);
  }, []);

  const handleAssistantReply = useCallback(
    (
      text: string,
      opts: {
        audio?: string | null;
        visemes?: VisemeFrame[];
        emotion?: AvatarState;
        toolUsed?: string | null;
        toolResult?: Record<string, unknown> | null;
        convId?: string | null;
      }
    ) => {
      if (opts.convId) {
        setConversationId(opts.convId);
        conversationIdRef.current = opts.convId;
      }

      if (opts.toolResult && opts.toolResult.status === 'pending_confirmation') {
        const pendingTool = String(opts.toolResult.tool_name || opts.toolUsed || '');
        let pendingArgs = (opts.toolResult.arguments as Record<string, unknown>) || {};
        if (Object.keys(pendingArgs).length === 0) {
          const match = text.match(/\(([^)]+)\)/);
          if (match) {
            const parsed: Record<string, string> = {};
            for (const pair of match[1].split(',')) {
              const eqIdx = pair.indexOf('=');
              if (eqIdx > 0) {
                parsed[pair.slice(0, eqIdx).trim()] = pair.slice(eqIdx + 1).trim();
              }
            }
            pendingArgs = parsed;
          }
        }
        if (pendingTool) {
          setPendingAction({ toolName: pendingTool, arguments: pendingArgs });
        }
      } else {
        setPendingAction(null);
      }

      const msg: ChatMessage = {
        id: `${Date.now()}-${Math.random().toString(36).slice(2, 7)}`,
        sender: 'assistant',
        text,
        toolUsed: opts.toolUsed ?? null,
        toolResult: opts.toolResult ?? null,
        audio: opts.audio ?? null,
        visemes: opts.visemes ?? [],
        emotion: opts.emotion ?? 'idle',
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      };

      setMessages((prev) => [...prev, msg]);
      setLiveSubtitle(text);

      if (opts.audio && !mutedRef.current) {
        lipSyncRef.current.playAudio(
          opts.audio,
          opts.visemes ?? [],
          () => {
            setAvatarState('speaking');
            if (voiceSessionRef.current) setVoicePhase('speaking');
          },
          () => {
            scheduleExpressionReset(opts.emotion, 1600);
            if (voiceSessionRef.current) {
              scheduleNextVoiceTurn(280);
            } else {
              setVoicePhase('off');
            }
          }
        );
      } else {
        scheduleExpressionReset(opts.emotion, 2000);
        if (voiceSessionRef.current) {
          scheduleNextVoiceTurn(450);
        } else {
          setVoicePhase('off');
        }
      }
    },
    [scheduleExpressionReset, scheduleNextVoiceTurn]
  );

  const handleReplyRef = useRef(handleAssistantReply);
  useEffect(() => {
    handleReplyRef.current = handleAssistantReply;
  }, [handleAssistantReply]);

  // Persistent single WebSocket lifecycle
  useEffect(() => {
    let disposed = false;

    const connect = () => {
      if (disposed) return;
      const ws = new WebSocket(getWebSocketUrl());
      wsRef.current = ws;

      ws.onopen = () => {
        if (disposed) return;
        setIsConnected(true);
        setErrorBanner(null);

        if (pingTimerRef.current !== null) window.clearInterval(pingTimerRef.current);
        pingTimerRef.current = window.setInterval(() => {
          if (ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify({ type: 'ping' }));
          }
        }, 25_000);
      };

      ws.onclose = () => {
        if (disposed) return;
        setIsConnected(false);
        if (pingTimerRef.current !== null) {
          window.clearInterval(pingTimerRef.current);
          pingTimerRef.current = null;
        }
        reconnectTimerRef.current = window.setTimeout(connect, 1800);
      };

      ws.onerror = () => {
        if (!disposed) setIsConnected(false);
      };

      ws.onmessage = (event) => {
        try {
          const msg = JSON.parse(event.data);
          if (msg.type === 'pong') {
            return;
          } else if (msg.type === 'thinking') {
            setAvatarState('thinking');
            if (voiceSessionRef.current) setVoicePhase('processing');
          } else if (msg.type === 'idle') {
            if (!lipSyncRef.current.isPlayingRef.current && !isRecordingRef.current) {
              setAvatarState('idle');
            }
          } else if (msg.type === 'error') {
            if (msg.code === 'empty_transcript' && voiceSessionRef.current) {
              // In live voice chat, quietly resume listening when ambient click/pause had no words
              scheduleNextVoiceTurn(220);
              return;
            }
            setErrorBanner(msg.message || 'Voice processing error.');
            setAvatarState('confused');
            if (voiceSessionRef.current) {
              scheduleNextVoiceTurn(1200);
            } else {
              setVoicePhase('off');
              window.setTimeout(() => {
                if (!isRecordingRef.current && !lipSyncRef.current.isPlayingRef.current) {
                  setAvatarState('idle');
                }
              }, 2200);
            }
          } else if (msg.type === 'transcript') {
            setMessages((prev) => [
              ...prev,
              {
                id: `${Date.now()}-u`,
                sender: 'user',
                text: msg.text,
                timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
              },
            ]);
          } else if (msg.type === 'response') {
            handleReplyRef.current(msg.text, {
              audio: msg.audio,
              visemes: msg.visemes,
              emotion: msg.emotion,
              toolUsed: msg.tool_used,
              toolResult: msg.tool_result,
              convId: msg.conversation_id,
            });
          }
        } catch (err) {
          console.error('Failed to parse WS message:', err);
        }
      };
    };

    connect();

    return () => {
      disposed = true;
      if (reconnectTimerRef.current !== null) window.clearTimeout(reconnectTimerRef.current);
      if (pingTimerRef.current !== null) window.clearInterval(pingTimerRef.current);
      if (nextTurnTimerRef.current !== null) window.clearTimeout(nextTurnTimerRef.current);
      wsRef.current?.close();
    };
  }, [scheduleNextVoiceTurn]);

  const teardownMic = useCallback(() => {
    micLevelRef.current = 0;
    try {
      micWorkletRef.current?.disconnect();
    } catch {
      // ignore
    }
    try {
      micProcessorRef.current?.disconnect();
    } catch {
      // ignore
    }
    try {
      micSourceRef.current?.disconnect();
    } catch {
      // ignore
    }
    try {
      micGainRef.current?.disconnect();
    } catch {
      // ignore
    }
    micWorkletRef.current = null;
    micProcessorRef.current = null;
    micSourceRef.current = null;
    micGainRef.current = null;

    if (micCtxRef.current && micCtxRef.current.state !== 'closed') {
      micCtxRef.current.close().catch(() => undefined);
      micCtxRef.current = null;
    }
    if (micStreamRef.current) {
      micStreamRef.current.getTracks().forEach((t) => t.stop());
      micStreamRef.current = null;
    }
  }, []);

  const sendRecordedAudio = useCallback(
    async (chunks: Float32Array[], sampleRate: number) => {
      const { base64, durationSec, peak } = encodeWav16kBase64(chunks, sampleRate);
      if (durationSec < 0.25 || peak < 0.0005) {
        if (voiceSessionRef.current) {
          scheduleNextVoiceTurn(200);
        } else {
          setErrorBanner('No microphone sound captured. Check your mic or speak louder.');
          setAvatarState('idle');
          setVoicePhase('off');
        }
        return;
      }

      setAvatarState('thinking');
      if (voiceSessionRef.current) setVoicePhase('processing');

      if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
        wsRef.current.send(
          JSON.stringify({
            type: 'audio',
            data: base64,
            mode: modeRef.current,
            conversation_id: conversationIdRef.current,
            voice: voiceRef.current,
            auto_approve: autoApproveRef.current,
          })
        );
        return;
      }

      // HTTP fallback when WebSocket isn't open
      try {
        const res = await fetch(`${API_BASE}/voice/ask`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            data: base64,
            mode: modeRef.current,
            conversation_id: conversationIdRef.current,
            voice: voiceRef.current,
            auto_approve: autoApproveRef.current,
          }),
        });
        if (!res.ok) {
          const err = await res.json().catch(() => ({}));
          const code = err?.detail?.code;
          if (code === 'empty_transcript' && voiceSessionRef.current) {
            scheduleNextVoiceTurn(200);
            return;
          }
          throw new Error(err?.detail?.message ?? err?.detail ?? `Voice HTTP ${res.status}`);
        }
        const data = await res.json();
        if (data.transcript) {
          setMessages((prev) => [
            ...prev,
            {
              id: `${Date.now()}-u`,
              sender: 'user',
              text: data.transcript,
              timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
            },
          ]);
        }
        handleReplyRef.current(data.text, {
          audio: data.audio,
          visemes: data.visemes,
          emotion: data.emotion,
          toolUsed: data.tool_used,
          toolResult: data.tool_result,
          convId: data.conversation_id,
        });
      } catch (err) {
        setErrorBanner(err instanceof Error ? err.message : 'Failed to send voice audio.');
        setAvatarState('confused');
        if (voiceSessionRef.current) {
          scheduleNextVoiceTurn(1000);
        } else {
          setVoicePhase('off');
          window.setTimeout(() => setAvatarState('idle'), 2000);
        }
      }
    },
    [scheduleNextVoiceTurn]
  );

  const stopAndSendCurrentTurn = useCallback(() => {
    if (!isRecordingRef.current) return;
    isRecordingRef.current = false;
    setIsRecording(false);

    const captured = pcmChunksRef.current.slice();
    const sr = sampleRateRef.current;
    pcmChunksRef.current = [];
    teardownMic();

    void sendRecordedAudio(captured, sr);
  }, [sendRecordedAudio, teardownMic]);

  const startListeningTurn = useCallback(async () => {
    if (isRecordingRef.current) return;
    try {
      lipSyncRef.current.stopAudio();
      setErrorBanner(null);
      setVoicePhase('starting');

      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
        },
      });
      if (!voiceSessionRef.current) {
        stream.getTracks().forEach((t) => t.stop());
        setVoicePhase('off');
        return;
      }

      micStreamRef.current = stream;
      pcmChunksRef.current = [];

      const AudioCtx =
        window.AudioContext ||
        (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
      const ctx = new AudioCtx();
      if (ctx.state === 'suspended') {
        await ctx.resume();
      }
      micCtxRef.current = ctx;
      sampleRateRef.current = ctx.sampleRate;

      const source = ctx.createMediaStreamSource(stream);
      const muteSink = ctx.createGain();
      muteSink.gain.value = 0;
      micSourceRef.current = source;
      micGainRef.current = muteSink;

      // Rolling adaptive noise floor (never poisoned by speaking right away)
      let noiseFloor = 0.004;
      let speechStreakAt: number | null = null;
      let hadSpeech = false;
      let silenceStartedAt: number | null = null;
      const startedAt = performance.now();

      const processFrame = (frame: Float32Array) => {
        if (!isRecordingRef.current) return;
        pcmChunksRef.current.push(frame);

        let sumSq = 0;
        let peak = 0;
        for (let i = 0; i < frame.length; i++) {
          const v = frame[i];
          sumSq += v * v;
          const a = Math.abs(v);
          if (a > peak) peak = a;
        }
        const rms = Math.sqrt(sumSq / Math.max(frame.length, 1));
        micLevelRef.current = Math.min(1, rms * 10);

        const now = performance.now();
        const elapsed = now - startedAt;
        if (elapsed < 60) return;

        if (!hadSpeech && rms < noiseFloor * 1.6) {
          noiseFloor = noiseFloor * 0.94 + rms * 0.06;
        } else if (!hadSpeech && rms < noiseFloor) {
          noiseFloor = rms;
        }

        const speechThresh = Math.max(0.007, Math.min(0.028, noiseFloor * 2.3));
        const silenceThresh = Math.max(0.0045, Math.min(0.02, noiseFloor * 1.6));

        if (rms > speechThresh || peak > 0.035) {
          silenceStartedAt = null;
          if (speechStreakAt === null) {
            speechStreakAt = now;
          } else if (!hadSpeech && now - speechStreakAt >= 90) {
            hadSpeech = true;
            setVoicePhase('hearing');
          }
        } else if (hadSpeech && rms > silenceThresh) {
          silenceStartedAt = null;
        } else {
          speechStreakAt = null;
          if (hadSpeech && elapsed > 450) {
            if (silenceStartedAt === null) {
              silenceStartedAt = now;
            } else if (now - silenceStartedAt > 650) {
              stopAndSendCurrentTurn();
            }
          } else if (!hadSpeech && elapsed > 35_000) {
            // Reset silent buffer periodically so memory doesn't grow while idle
            pcmChunksRef.current = [];
          }
        }
      };

      // Prefer modern AudioWorkletNode (no deprecation warning); fallback to ScriptProcessorNode
      let workletAttached = false;
      if (ctx.audioWorklet) {
        try {
          const blob = new Blob([WORKLET_CODE], { type: 'application/javascript' });
          const workletUrl = URL.createObjectURL(blob);
          await ctx.audioWorklet.addModule(workletUrl);
          URL.revokeObjectURL(workletUrl);
          const worklet = new AudioWorkletNode(ctx, 'nyx-mic-capture');
          worklet.port.onmessage = (ev) => {
            if (ev.data instanceof Float32Array) {
              processFrame(ev.data);
            }
          };
          source.connect(worklet);
          worklet.connect(muteSink);
          muteSink.connect(ctx.destination);
          micWorkletRef.current = worklet;
          workletAttached = true;
        } catch {
          workletAttached = false;
        }
      }

      if (!workletAttached) {
        const processor = ctx.createScriptProcessor(4096, 1, 1);
        processor.onaudioprocess = (ev) => {
          processFrame(new Float32Array(ev.inputBuffer.getChannelData(0)));
        };
        source.connect(processor);
        processor.connect(muteSink);
        muteSink.connect(ctx.destination);
        micProcessorRef.current = processor;
      }

      isRecordingRef.current = true;
      setIsRecording(true);
      setVoicePhase('listening');
      setAvatarState('listening');
    } catch (err) {
      teardownMic();
      isRecordingRef.current = false;
      setIsRecording(false);
      voiceSessionRef.current = false;
      setVoiceSessionActive(false);
      setVoicePhase('off');
      setAvatarState('idle');
      setErrorBanner(
        err instanceof Error ? `Microphone error: ${err.message}` : 'Could not access microphone.'
      );
    }
  }, [stopAndSendCurrentTurn, teardownMic]);

  useEffect(() => {
    startListeningTurnRef.current = startListeningTurn;
  }, [startListeningTurn]);

  const startVoiceSession = useCallback(async () => {
    if (voiceSessionRef.current) return;
    voiceSessionRef.current = true;
    setVoiceSessionActive(true);
    setErrorBanner(null);
    await startListeningTurn();
  }, [startListeningTurn]);

  const endVoiceSession = useCallback(() => {
    voiceSessionRef.current = false;
    setVoiceSessionActive(false);
    if (nextTurnTimerRef.current !== null) {
      window.clearTimeout(nextTurnTimerRef.current);
      nextTurnTimerRef.current = null;
    }
    isRecordingRef.current = false;
    setIsRecording(false);
    pcmChunksRef.current = [];
    teardownMic();
    lipSyncRef.current.stopAudio();
    setVoicePhase('off');
    setAvatarState('idle');
  }, [teardownMic]);

  const interruptSpeaking = useCallback(() => {
    lipSyncRef.current.stopAudio();
    if (voiceSessionRef.current) {
      void startListeningTurn();
    } else {
      setAvatarState('idle');
      setVoicePhase('off');
    }
  }, [startListeningTurn]);

  useEffect(() => {
    return () => {
      voiceSessionRef.current = false;
      isRecordingRef.current = false;
      teardownMic();
      if (expressionResetRef.current !== null) {
        window.clearTimeout(expressionResetRef.current);
      }
      if (nextTurnTimerRef.current !== null) {
        window.clearTimeout(nextTurnTimerRef.current);
      }
    };
  }, [teardownMic]);

  const sendTextMessage = useCallback(async (text: string) => {
    lipSyncRef.current.stopAudio();
    setErrorBanner(null);

    const userMsg: ChatMessage = {
      id: `${Date.now()}-u`,
      sender: 'user',
      text,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    };
    setMessages((prev) => [...prev, userMsg]);
    setAvatarState('thinking');

    try {
      const data = await sendChat({
        message: text,
        mode: modeRef.current,
        conversation_id: conversationIdRef.current,
        tts: !mutedRef.current,
        voice: voiceRef.current,
        auto_approve: autoApproveRef.current,
      });

      handleReplyRef.current(data.response, {
        audio: data.audio,
        visemes: data.visemes,
        emotion: data.emotion,
        toolUsed: data.tool_used,
        toolResult: data.tool_result,
        convId: data.conversation_id,
      });
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Failed to reach NyxAI backend.';
      setErrorBanner(msg);
      setAvatarState('concerned');
      window.setTimeout(() => setAvatarState('idle'), 2400);
    }
  }, []);

  const approvePendingAction = useCallback(async () => {
    if (!pendingAction) return;
    const action = pendingAction;
    setPendingAction(null);
    setAvatarState('thinking');
    try {
      const data = await confirmAgentTool({
        tool_name: action.toolName,
        arguments: action.arguments,
        conversation_id: conversationIdRef.current,
        tts: !mutedRef.current,
        voice: voiceRef.current,
      });
      handleReplyRef.current(data.response, {
        audio: data.audio,
        visemes: data.visemes,
        emotion: data.emotion,
        toolUsed: data.tool_used,
        toolResult: data.tool_result,
        convId: data.conversation_id,
      });
    } catch (err) {
      setErrorBanner(err instanceof Error ? err.message : 'Action failed.');
      setAvatarState('concerned');
      window.setTimeout(() => setAvatarState('idle'), 2000);
    }
  }, [pendingAction]);

  const dismissPendingAction = useCallback(() => {
    setPendingAction(null);
  }, []);

  const replayMessageAudio = useCallback(
    (msg: ChatMessage) => {
      if (!msg.audio) return;
      setLiveSubtitle(msg.text);
      lipSyncRef.current.playAudio(
        msg.audio,
        msg.visemes ?? [],
        () => setAvatarState('speaking'),
        () => scheduleExpressionReset(msg.emotion, 1600)
      );
    },
    [scheduleExpressionReset]
  );

  const startNewConversation = useCallback(() => {
    lipSyncRef.current.stopAudio();
    setConversationId(null);
    conversationIdRef.current = null;
    setPendingAction(null);
    setMessages([]);
    setLiveSubtitle('');
    setAvatarState('idle');
  }, []);

  const loadConversation = useCallback(async (id: string) => {
    const detail = await fetchConversationDetail(id);
    if (!detail) return;
    lipSyncRef.current.stopAudio();
    setConversationId(detail.id);
    conversationIdRef.current = detail.id;
    setPendingAction(null);
    const loaded: ChatMessage[] = detail.messages.map((m) => ({
      id: `hist-${m.id}`,
      sender: m.role === 'user' ? 'user' : 'assistant',
      text: m.content,
      toolUsed: m.tool_name,
      timestamp: new Date(m.created_at).toLocaleTimeString([], {
        hour: '2-digit',
        minute: '2-digit',
      }),
    }));
    setMessages(loaded);
    const lastAssistant = [...loaded].reverse().find((m) => m.sender === 'assistant');
    setLiveSubtitle(lastAssistant?.text ?? '');
    setAvatarState('idle');
  }, []);

  return {
    avatarState,
    voicePhase,
    voiceSessionActive,
    messages,
    liveSubtitle,
    conversationId,
    isRecording,
    isConnected,
    errorBanner,
    pendingAction,
    micLevelRef,
    lipSync,
    startVoiceSession,
    endVoiceSession,
    sendCurrentVoiceTurn: stopAndSendCurrentTurn,
    interruptSpeaking,
    sendTextMessage,
    replayMessageAudio,
    approvePendingAction,
    dismissPendingAction,
    startNewConversation,
    loadConversation,
    clearError: () => setErrorBanner(null),
  };
}
