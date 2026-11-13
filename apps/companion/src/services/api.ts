import {
  AvatarConfig,
  AvatarState,
  ConversationDetail,
  ConversationSummary,
  HealthInfo,
  QuickActionResult,
  SystemTelemetry,
  VisemeFrame,
} from '../types/companion';

export const API_BASE = import.meta.env.VITE_API_URL ?? '';

export function resolveAssetUrl(path: string | null | undefined): string | null {
  if (!path) return null;
  if (path.startsWith('http://') || path.startsWith('https://') || path.startsWith('blob:') || path.startsWith('data:')) {
    return path;
  }
  return `${API_BASE}${path}`;
}

export function getWebSocketUrl(): string {
  if (API_BASE) {
    const url = new URL(API_BASE);
    const proto = url.protocol === 'https:' ? 'wss:' : 'ws:';
    return `${proto}//${url.host}/voice`;
  }
  const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  return `${proto}//${window.location.host}/voice`;
}

export async function fetchHealth(): Promise<HealthInfo | null> {
  try {
    const res = await fetch(`${API_BASE}/health`);
    if (!res.ok) return null;
    return (await res.json()) as HealthInfo;
  } catch {
    return null;
  }
}

export interface ChatPayload {
  message: string;
  mode: 'companion' | 'agent';
  conversation_id?: string | null;
  tts?: boolean;
  voice?: string;
  auto_approve?: boolean;
}

export async function confirmAgentTool(payload: {
  tool_name: string;
  arguments: Record<string, unknown>;
  conversation_id?: string | null;
  tts?: boolean;
  voice?: string;
}): Promise<ChatApiResponse> {
  const res = await fetch(`${API_BASE}/agent/confirm`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err?.detail?.message ?? err?.detail ?? `Confirm failed (${res.status})`);
  }
  return (await res.json()) as ChatApiResponse;
}

export interface ChatApiResponse {
  response: string;
  conversation_id: string;
  model: string;
  mode: 'companion' | 'agent';
  tool_used?: string | null;
  tool_result?: Record<string, unknown> | null;
  audio?: string | null;
  visemes?: VisemeFrame[];
  emotion?: AvatarState;
}

export async function sendChat(payload: ChatPayload): Promise<ChatApiResponse> {
  const res = await fetch(`${API_BASE}/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    let detailMsg = `HTTP ${res.status}`;
    try {
      const errData = await res.json();
      detailMsg = errData?.detail?.message ?? errData?.detail ?? detailMsg;
    } catch {
      // ignore json parse failure
    }
    throw new Error(detailMsg);
  }
  return (await res.json()) as ChatApiResponse;
}

export async function fetchAvatarConfig(): Promise<AvatarConfig> {
  const res = await fetch(`${API_BASE}/avatar/config`);
  if (!res.ok) throw new Error('Failed to load avatar configuration');
  return (await res.json()) as AvatarConfig;
}

export async function saveAvatarConfig(config: AvatarConfig): Promise<AvatarConfig> {
  const res = await fetch(`${API_BASE}/avatar/config`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(config),
  });
  if (!res.ok) throw new Error('Failed to save avatar configuration');
  return (await res.json()) as AvatarConfig;
}

export async function uploadAvatarPhoto(file: File): Promise<AvatarConfig> {
  const form = new FormData();
  form.append('file', file);
  const res = await fetch(`${API_BASE}/avatar/photo`, {
    method: 'POST',
    body: form,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail ?? 'Photo upload failed');
  }
  return (await res.json()) as AvatarConfig;
}

export async function deleteAvatarPhoto(): Promise<AvatarConfig> {
  const res = await fetch(`${API_BASE}/avatar/photo`, { method: 'DELETE' });
  if (!res.ok) throw new Error('Failed to remove photo');
  return (await res.json()) as AvatarConfig;
}

export async function uploadAvatarModel(file: File): Promise<AvatarConfig> {
  const form = new FormData();
  form.append('file', file);
  const res = await fetch(`${API_BASE}/avatar/model`, {
    method: 'POST',
    body: form,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail ?? '3D model upload failed');
  }
  return (await res.json()) as AvatarConfig;
}

export async function fetchConversations(limit = 30): Promise<ConversationSummary[]> {
  const res = await fetch(`${API_BASE}/memory/conversations?limit=${limit}`);
  if (!res.ok) return [];
  const data = await res.json();
  return data.conversations ?? [];
}

export async function fetchConversationDetail(id: string): Promise<ConversationDetail | null> {
  const res = await fetch(`${API_BASE}/memory/conversations/${id}`);
  if (!res.ok) return null;
  return (await res.json()) as ConversationDetail;
}

export async function deleteConversation(id: string): Promise<boolean> {
  const res = await fetch(`${API_BASE}/memory/conversations/${id}`, { method: 'DELETE' });
  return res.ok;
}

export async function fetchSystemTelemetry(): Promise<SystemTelemetry | null> {
  try {
    const res = await fetch(`${API_BASE}/system/telemetry`);
    if (!res.ok) return null;
    return (await res.json()) as SystemTelemetry;
  } catch {
    return null;
  }
}

export async function postQuickAction(
  action: string,
  params: Record<string, unknown> = {}
): Promise<QuickActionResult> {
  const res = await fetch(`${API_BASE}/system/quick-action`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ action, params }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail ?? `Quick action '${action}' failed`);
  }
  return (await res.json()) as QuickActionResult;
}

export async function postProactiveSweep(): Promise<{ status: string; audit: Record<string, unknown> }> {
  const res = await fetch(`${API_BASE}/system/proactive/sweep`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail ?? 'Proactive sweep failed');
  }
  return await res.json();
}



