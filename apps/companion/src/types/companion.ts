export type AvatarState =
  | 'idle'
  | 'listening'
  | 'thinking'
  | 'speaking'
  | 'happy'
  | 'excited'
  | 'confused'
  | 'concerned';

export type AvatarMode = 'photo' | 'vrm' | 'stylized';

export type VisemeKind = 'closed' | 'slight' | 'open' | 'wide';

export interface VisemeFrame {
  time_seconds: number;
  mouth_open: number;
  viseme: VisemeKind;
}

export interface LandmarkPoint {
  x: number;
  y: number;
  rx: number;
  ry: number;
}

export interface AvatarLandmarks {
  left_eye: LandmarkPoint;
  right_eye: LandmarkPoint;
  mouth: LandmarkPoint;
  chin_y: number;
}

export interface VoiceOption {
  id: string;
  label: string;
}

export interface AvatarConfig {
  mode: AvatarMode;
  name: string;
  tagline: string;
  voice: string;
  photo_url: string | null;
  model_url: string | null;
  landmarks: AvatarLandmarks;
  available_voices?: VoiceOption[];
}

export interface ChatMessage {
  id: string;
  sender: 'user' | 'assistant';
  text: string;
  toolUsed?: string | null;
  toolResult?: Record<string, unknown> | null;
  audio?: string | null;
  visemes?: VisemeFrame[];
  emotion?: AvatarState;
  timestamp: string;
}

export interface HealthInfo {
  status: string;
  version: string;
  model: string;
  ollama_connected: boolean;
}

export interface ConversationSummary {
  id: string;
  mode: string;
  title: string | null;
  created_at: string;
  updated_at: string;
  message_count: number;
}

export interface ConversationMessageDTO {
  id: number;
  conversation_id: string;
  role: string;
  content: string;
  tool_name: string | null;
  created_at: string;
}

export interface ConversationDetail {
  id: string;
  mode: string;
  title: string | null;
  created_at: string;
  updated_at: string;
  messages: ConversationMessageDTO[];
}

export interface AgentTelemetryInfo {
  id: string;
  name: string;
  status: 'active' | 'ready' | 'busy' | string;
  role: string;
}

export interface SystemTelemetry {
  cpu: {
    percent: number;
    core_count?: number;
  };
  ram: {
    used_gb: number;
    total_gb: number;
    percent: number;
    available_gb?: number;
  };
  battery: {
    percent: number;
    plugged_in: boolean;
    status: string;
  };
  gpu: {
    name?: string;
    temperature_c?: number;
    memory_used_mb?: number;
    memory_total_mb?: number;
    gpu_utilization_percent?: number;
    available?: boolean;
  };
  uptime: string;
  agents: AgentTelemetryInfo[];
}

export interface QuickActionResult {
  success: boolean;
  action: string;
  message: string;
  data: Record<string, unknown>;
}


