import { useEffect, useRef, useState } from 'react';
import { AvatarState } from '../components/Avatar';
import { ChatMessage } from '../components/ChatFeed';

export function useVoiceWebSocket(mode: 'companion' | 'agent') {
  const [avatarState, setAvatarState] = useState<AvatarState>('idle');
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isRecording, setIsRecording] = useState(false);
  const [isConnected, setIsConnected] = useState(false);

  const wsRef = useRef<WebSocket | null>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);

  useEffect(() => {
    const wsUrl = `ws://${window.location.hostname}:8000/voice`;
    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;

    ws.onopen = () => {
      setIsConnected(true);
    };

    ws.onclose = () => {
      setIsConnected(false);
      setAvatarState('idle');
    };

    ws.onerror = (err) => {
      console.error('WebSocket Error:', err);
      setIsConnected(false);
    };

    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data);

        if (msg.type === 'idle') {
          setAvatarState('idle');
        } else if (msg.type === 'thinking') {
          setAvatarState('thinking');
        } else if (msg.type === 'speaking') {
          setAvatarState('speaking');
        } else if (msg.type === 'transcript') {
          setMessages((prev) => [
            ...prev,
            {
              id: Date.now().toString(),
              sender: 'user',
              text: msg.text,
              timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
            },
          ]);
        } else if (msg.type === 'response') {
          setMessages((prev) => [
            ...prev,
            {
              id: Date.now().toString(),
              sender: 'assistant',
              text: msg.text,
              toolUsed: msg.tool_used,
              toolResult: msg.tool_result,
              timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
            },
          ]);

          if (msg.audio) {
            playBase64Audio(msg.audio);
          }
        }
      } catch (err) {
        console.error('Failed to parse WS message:', err);
      }
    };

    return () => {
      ws.close();
    };
  }, []);

  const playBase64Audio = (base64Audio: string) => {
    try {
      setAvatarState('speaking');
      const audioUrl = `data:audio/wav;base64,${base64Audio}`;
      const audio = new Audio(audioUrl);
      audio.onended = () => setAvatarState('idle');
      audio.play().catch((err) => {
        console.error('Audio playback failed:', err);
        setAvatarState('idle');
      });
    } catch (e) {
      console.error('Audio setup error:', e);
      setAvatarState('idle');
    }
  };

  const startRecording = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      audioChunksRef.current = [];
      const mediaRecorder = new MediaRecorder(stream);
      mediaRecorderRef.current = mediaRecorder;

      mediaRecorder.ondataavailable = (e) => {
        if (e.data.size > 0) {
          audioChunksRef.current.push(e.data);
        }
      };

      mediaRecorder.onstop = async () => {
        const audioBlob = new Blob(audioChunksRef.current, { type: 'audio/wav' });
        const reader = new FileReader();
        reader.readAsDataURL(audioBlob);
        reader.onloadend = () => {
          const base64Data = (reader.result as string).split(',')[1];
          if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
            wsRef.current.send(
              JSON.stringify({
                type: 'audio',
                data: base64Data,
                mode: mode,
              })
            );
            setAvatarState('thinking');
          }
        };
      };

      mediaRecorder.start();
      setIsRecording(true);
      setAvatarState('listening');
    } catch (err) {
      console.error('Microphone access failed:', err);
    }
  };

  const stopRecording = () => {
    if (mediaRecorderRef.current && isRecording) {
      mediaRecorderRef.current.stop();
      mediaRecorderRef.current.stream.getTracks().forEach((track: MediaStreamTrack) => track.stop());
      setIsRecording(false);
    }
  };

  const toggleRecording = () => {
    if (isRecording) {
      stopRecording();
    } else {
      startRecording();
    }
  };

  const sendTextMessage = async (text: string) => {
    const userMsg: ChatMessage = {
      id: Date.now().toString(),
      sender: 'user',
      text,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    };

    setMessages((prev) => [...prev, userMsg]);
    setAvatarState('thinking');

    try {
      const res = await fetch('/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: text, mode }),
      });

      const data = await res.json();

      const assistantMsg: ChatMessage = {
        id: (Date.now() + 1).toString(),
        sender: 'assistant',
        text: data.response,
        toolUsed: data.tool_used,
        toolResult: data.tool_result,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      };

      setMessages((prev) => [...prev, assistantMsg]);

      if (data.audio) {
        playBase64Audio(data.audio);
      } else {
        setAvatarState('idle');
      }
    } catch (err) {
      console.error('REST Chat Error:', err);
      setAvatarState('idle');
    }
  };

  return {
    avatarState,
    messages,
    isRecording,
    isConnected,
    toggleRecording,
    sendTextMessage,
  };
}
