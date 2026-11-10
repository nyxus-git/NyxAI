import { useCallback, useEffect, useRef, useState } from 'react';
import {
  fetchConversationDetail,
  getWebSocketUrl,
  sendChat,
} from '../services/api';
import { AvatarState, ChatMessage, VisemeFrame } from '../types/companion';
import { LipSyncLiveState, useAudioLipSync } from './useAudioLipSync';

interface UseVoiceCompanionOptions {
  mode: 'companion' | 'agent';
  voice: string;
  muted: boolean;
  handsFree: boolean;
}

export interface UseVoiceCompanionReturn {
  avatarState: AvatarState;
  messages: ChatMessage[];
  liveSubtitle: string;
  conversationId: string | null;
  isRecording: boolean;
  isConnected: boolean;
  errorBanner: string | null;
  micLevelRef: React.MutableRefObject<number>;
  lipSync: LipSyncLiveState;
  toggleRecording: () => void;
  sendTextMessage: (text: string) => Promise<void>;
  replayMessageAudio: (msg: ChatMessage) => void;
  startNewConversation: () => void;
  loadConversation: (id: string) => Promise<void>;
  clearError: () => void;
}

export function useVoiceWebSocket({
  mode,
  voice,
  muted,
  handsFree,
}: UseVoiceCompanionOptions): UseVoiceCompanionReturn {
  const [avatarState, setAvatarState] = useState<AvatarState>('idle');
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [liveSubtitle, setLiveSubtitle] = useState<string>('');
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [isRecording, setIsRecording] = useState(false);
  const [isConnected, setIsConnected] = useState(false);
  const [errorBanner, setErrorBanner] = useState<string | null>(null);

  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimerRef = useRef<number | null>(null);
  const expressionResetRef = useRef<number | null>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);
  const micStreamRef = useRef<MediaStream | null>(null);
  const micCtxRef = useRef<AudioContext | null>(null);
  const micRafRef = useRef<number | null>(null);
  const micLevelRef = useRef<number>(0);

  const conversationIdRef = useRef<string | null>(conversationId);
  const modeRef = useRef(mode);
  const voiceRef = useRef(voice);
  const handsFreeRef = useRef(handsFree);

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
    handsFreeRef.current = handsFree;
  }, [handsFree]);

  const lipSync = useAudioLipSync(muted);

  const scheduleExpressionReset = useCallback((emotion?: AvatarState, delayMs = 2400) => {
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

      if (opts.audio && !muted) {
        lipSync.playAudio(
          opts.audio,
          opts.visemes ?? [],
          () => setAvatarState('speaking'),
          () => scheduleExpressionReset(opts.emotion, 1800)
        );
      } else {
        scheduleExpressionReset(opts.emotion, 2400);
      }
    },
    [lipSync, muted, scheduleExpressionReset]
  );

  // WebSocket lifecycle with automatic reconnect
  useEffect(() => {
    let disposed = false;

    const connect = () => {
      if (disposed) return;
      const ws = new WebSocket(getWebSocketUrl());
      wsRef.current = ws;

      ws.onopen = () => {
        if (!disposed) {
          setIsConnected(true);
          setErrorBanner(null);
        }
      };

      ws.onclose = () => {
        if (disposed) return;
        setIsConnected(false);
        reconnectTimerRef.current = window.setTimeout(connect, 3000);
      };

      ws.onerror = () => {
        if (!disposed) setIsConnected(false);
      };

      ws.onmessage = (event) => {
        try {
          const msg = JSON.parse(event.data);
          if (msg.type === 'thinking') {
            setAvatarState('thinking');
          } else if (msg.type === 'idle') {
            if (!lipSync.isPlayingRef.current) {
              setAvatarState('idle');
            }
          } else if (msg.type === 'error') {
            setErrorBanner(msg.message || 'Voice processing error.');
            setAvatarState('confused');
            window.setTimeout(() => setAvatarState('idle'), 2000);
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
            handleAssistantReply(msg.text, {
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
      if (reconnectTimerRef.current !== null) {
        window.clearTimeout(reconnectTimerRef.current);
      }
      wsRef.current?.close();
    };
  }, [handleAssistantReply, lipSync.isPlayingRef]);

  const stopMicMeter = useCallback(() => {
    if (micRafRef.current !== null) {
      cancelAnimationFrame(micRafRef.current);
      micRafRef.current = null;
    }
    micLevelRef.current = 0;
    if (micCtxRef.current && micCtxRef.current.state !== 'closed') {
      micCtxRef.current.close().catch(() => undefined);
      micCtxRef.current = null;
    }
    if (micStreamRef.current) {
      micStreamRef.current.getTracks().forEach((t) => t.stop());
      micStreamRef.current = null;
    }
  }, []);

  const stopRecording = useCallback(() => {
    if (mediaRecorderRef.current && mediaRecorderRef.current.state !== 'inactive') {
      mediaRecorderRef.current.stop();
    }
    setIsRecording(false);
  }, []);

  const startRecording = useCallback(async () => {
    try {
      lipSync.stopAudio();
      setErrorBanner(null);

      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      micStreamRef.current = stream;
      audioChunksRef.current = [];

      // Real-time mic input energy + optional hands-free silence detection
      const AudioCtx = window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
      const ctx = new AudioCtx();
      micCtxRef.current = ctx;
      const source = ctx.createMediaStreamSource(stream);
      const analyser = ctx.createAnalyser();
      analyser.fftSize = 256;
      source.connect(analyser);
      const buf = new Uint8Array(analyser.fftSize);

      let hadSpeech = false;
      let silenceStartedAt: number | null = null;
      const startedAt = performance.now();

      const mimeType = MediaRecorder.isTypeSupported('audio/webm;codecs=opus')
        ? 'audio/webm;codecs=opus'
        : MediaRecorder.isTypeSupported('audio/webm')
          ? 'audio/webm'
          : '';

      const recorder = mimeType ? new MediaRecorder(stream, { mimeType }) : new MediaRecorder(stream);
      mediaRecorderRef.current = recorder;

      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) {
          audioChunksRef.current.push(e.data);
        }
      };

      recorder.onstop = () => {
        stopMicMeter();
        const blob = new Blob(audioChunksRef.current, { type: mimeType || 'audio/webm' });
        if (blob.size < 400) {
          setAvatarState('idle');
          return;
        }
        const reader = new FileReader();
        reader.readAsDataURL(blob);
        reader.onloadend = () => {
          const resultStr = reader.result as string;
          const base64Data = resultStr.includes(',') ? resultStr.split(',')[1] : resultStr;
          if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
            wsRef.current.send(
              JSON.stringify({
                type: 'audio',
                data: base64Data,
                mode: modeRef.current,
                conversation_id: conversationIdRef.current,
                voice: voiceRef.current,
              })
            );
            setAvatarState('thinking');
          } else {
            setErrorBanner('Voice WebSocket is disconnected. Check if backend is running.');
            setAvatarState('idle');
          }
        };
      };

      const monitorMic = () => {
        if (recorder.state !== 'recording') return;
        analyser.getByteTimeDomainData(buf);
        let sumSq = 0;
        for (let i = 0; i < buf.length; i++) {
          const norm = (buf[i] - 128) / 128;
          sumSq += norm * norm;
        }
        const rms = Math.sqrt(sumSq / buf.length);
        micLevelRef.current = Math.min(1, rms * 5.5);

        if (handsFreeRef.current) {
          const now = performance.now();
          if (rms > 0.03) {
            hadSpeech = true;
            silenceStartedAt = null;
          } else if (hadSpeech && now - startedAt > 900) {
            if (silenceStartedAt === null) {
              silenceStartedAt = now;
            } else if (now - silenceStartedAt > 1300) {
              stopRecording();
              return;
            }
          }
        }

        micRafRef.current = requestAnimationFrame(monitorMic);
      };

      recorder.start();
      setIsRecording(true);
      setAvatarState('listening');
      micRafRef.current = requestAnimationFrame(monitorMic);
    } catch (err) {
      stopMicMeter();
      setIsRecording(false);
      setAvatarState('idle');
      setErrorBanner(
        err instanceof Error
          ? `Microphone error: ${err.message}`
          : 'Could not access microphone.'
      );
    }
  }, [lipSync, stopMicMeter, stopRecording]);

  useEffect(() => {
    return () => {
      stopMicMeter();
      if (expressionResetRef.current !== null) {
        window.clearTimeout(expressionResetRef.current);
      }
    };
  }, [stopMicMeter]);

  const toggleRecording = useCallback(() => {
    if (isRecording) {
      stopRecording();
    } else {
      startRecording();
    }
  }, [isRecording, startRecording, stopRecording]);

  const sendTextMessage = useCallback(
    async (text: string) => {
      lipSync.stopAudio();
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
          tts: !muted,
          voice: voiceRef.current,
        });

        handleAssistantReply(data.response, {
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
    },
    [handleAssistantReply, lipSync, muted]
  );

  const replayMessageAudio = useCallback(
    (msg: ChatMessage) => {
      if (!msg.audio) return;
      setLiveSubtitle(msg.text);
      lipSync.playAudio(
        msg.audio,
        msg.visemes ?? [],
        () => setAvatarState('speaking'),
        () => scheduleExpressionReset(msg.emotion, 1600)
      );
    },
    [lipSync, scheduleExpressionReset]
  );

  const startNewConversation = useCallback(() => {
    lipSync.stopAudio();
    setConversationId(null);
    conversationIdRef.current = null;
    setMessages([]);
    setLiveSubtitle('');
    setAvatarState('idle');
  }, [lipSync]);

  const loadConversation = useCallback(
    async (id: string) => {
      const detail = await fetchConversationDetail(id);
      if (!detail) return;
      lipSync.stopAudio();
      setConversationId(detail.id);
      conversationIdRef.current = detail.id;
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
    },
    [lipSync]
  );

  return {
    avatarState,
    messages,
    liveSubtitle,
    conversationId,
    isRecording,
    isConnected,
    errorBanner,
    micLevelRef,
    lipSync,
    toggleRecording,
    sendTextMessage,
    replayMessageAudio,
    startNewConversation,
    loadConversation,
    clearError: () => setErrorBanner(null),
  };
}
