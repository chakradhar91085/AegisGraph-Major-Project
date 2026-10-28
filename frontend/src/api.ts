import axios from 'axios';

// Set VITE_API_URL in frontend/.env to point at another backend.
const API_BASE = `${import.meta.env.VITE_API_URL ?? 'http://localhost:8001'}/api/v1`;

// Mirrors backend/app/security/policy.py: LOW < 0.35 <= MEDIUM < 0.65 <= HIGH.
export const RISK_BANDS = { medium: 0.35, high: 0.65 };
export const riskLevelOf = (risk: number): 'LOW' | 'MEDIUM' | 'HIGH' =>
  risk >= RISK_BANDS.high ? 'HIGH' : risk >= RISK_BANDS.medium ? 'MEDIUM' : 'LOW';

// Every request carries the signed-in user's Clerk session token; the backend
// verifies it and decides the user's role. Nothing here can choose a role.
let tokenGetter: (() => Promise<string | null>) | null = null;
export const setTokenGetter = (getter: () => Promise<string | null>) => {
  tokenGetter = getter;
};
axios.interceptors.request.use(async (config) => {
  const token = tokenGetter ? await tokenGetter() : null;
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

export interface AdaptivePolicy {
  risk_score: number;
  risk_level: 'LOW' | 'MEDIUM' | 'HIGH';
  attenuation_factor: number;
  effective_context_limit: number;
  effective_graph_depth: number;
  response_mode: 'ALLOW' | 'MASK' | 'RESTRICT' | 'BLOCK';
}

export interface SignalValues {
  semantic_focus: number;
  temporal_frequency: number;
  entity_focus: number;
  graph_footprint: number;
  sensitivity_exposure?: number; // 5th signal; absent on audit rows older than it
}

// What one answer touched (counts only, no names).
export interface Exposure {
  units?: number;
  sensitive_items?: number;
  items?: number;
  max_seniority?: number;
  labels?: Record<string, number>;
  pii?: Record<string, number>;
}

export interface TelemetryEvent {
  session_id: string;
  timestamp: number;
  query: string;
  intent: string;
  retrieval_strategy: string;
  result_count: number;
  signals: SignalValues;
  instantaneous_risk: number;
  smoothed_risk: number;
  policy?: AdaptivePolicy;
  blocked_by_policy: boolean;
  role: string;
  response_mode: 'ALLOW' | 'MASK' | 'RESTRICT' | 'BLOCK';
  exposure?: Exposure;
  retrieval_model?: string | null; // MCP agent model, "fixed queries", or null
}

export type LlmProvider = 'ollama' | 'openrouter';

export interface ChatRequest {
  query: string;
  session_token?: string;
  llm_provider?: LlmProvider;
}

export interface LlmProviderInfo {
  id: LlmProvider;
  model: string;
  available: boolean;
}

export interface LlmProvidersResponse {
  default: LlmProvider;
  providers: LlmProviderInfo[];
}

export interface GraphNode {
  id: string;
  label: string;
  type: string;
}

export interface GraphEdge {
  source: string;
  target: string;
  type: string;
  weight?: number;
}

export interface GraphVisualizationPayload {
  nodes: GraphNode[];
  edges: GraphEdge[];
}

export interface ChatResponse {
  answer: string;
  session_id: string;
  session_token: string;
  intent: string;
  retrieval: {
    result_count: number;
    strategy: string;
  };
  status: string;
  telemetry: TelemetryEvent;
  graph_data?: GraphVisualizationPayload;
  llm_provider?: string;
  llm_model?: string;
}

export type ResponseMode = 'ALLOW' | 'MASK' | 'RESTRICT' | 'BLOCK';

export interface Identity {
  user_id: string;
  role: string;
  // Remembered risk (after idle decay) and the policy the next query will face.
  risk_score: number;
  response_mode: ResponseMode;
}

export const ADMIN_ROLE = 'Auditor';

export const chatApi = {
  async sendMessage(
    query: string,
    sessionToken?: string,
    llmProvider?: LlmProvider,
  ): Promise<ChatResponse> {
    const payload: ChatRequest = { query, llm_provider: llmProvider };
    if (sessionToken) {
      payload.session_token = sessionToken;
    }
    const response = await axios.post<ChatResponse>(`${API_BASE}/chat`, payload);
    return response.data;
  },

  async llmProviders(): Promise<LlmProvidersResponse> {
    return (await axios.get<LlmProvidersResponse>(`${API_BASE}/llm/providers`)).data;
  },

  async me(): Promise<Identity> {
    return (await axios.get<Identity>(`${API_BASE}/me`)).data;
  },

  async endSession(sessionToken: string): Promise<void> {
    await axios.post(`${API_BASE}/session/end`, { session_token: sessionToken });
  },

  // Only takes effect when the server runs with DEMO_ALLOW_RISK_RESET=true.
  async resetRisk(): Promise<void> {
    await axios.post(`${API_BASE}/session/reset`);
  },
};

export interface AuditSession {
  session_id: string;
  role: string;
  user_id: string | null;
  user_email: string | null;
  user_name?: string | null;
  started_at: string;
  ended_at: string | null;
  status: string;
  query_count: number;
  final_risk_score: number;
  peak_risk_score: number;
  final_behavioral_mode: string;
  highest_behavioral_mode: string;
}

export interface AuditQuery {
  id: string;
  session_id: string;
  timestamp: string;
  query: string;
  intent: string;
  risk_score: number;
  instantaneous_risk: number | null;
  behavioral_mode: string;
  retrieval_outcome: string;
  masked: boolean;
  attenuated: boolean;
  blocked: boolean;
  result_count: number;
  role: string;
  user_id: string | null;
  user_email: string | null;
  user_name?: string | null;
  llm_provider: string;
  signals: SignalValues | null;
  policy: AdaptivePolicy | null;
  cypher_queries: string[] | null;
  exposure: Exposure | null;
}

export const auditApi = {
  async getSessions(limit: number = 50): Promise<AuditSession[]> {
    const response = await axios.get<{sessions: AuditSession[]}>(`${API_BASE}/audit/sessions?limit=${limit}`);
    return response.data.sessions;
  },

  async getSessionQueries(sessionId: string): Promise<AuditQuery[]> {
    const response = await axios.get<{queries: AuditQuery[]}>(`${API_BASE}/audit/sessions/${sessionId}/queries`);
    return response.data.queries;
  },

  // Most recent queries across ALL users/sessions, newest first — the admin live feed.
  // Pass userId for one user's history (the admin user detail page).
  async getRecent(limit: number = 50, userId?: string): Promise<AuditQuery[]> {
    const response = await axios.get<{queries: AuditQuery[]}>(`${API_BASE}/audit/recent`, { params: { limit, user_id: userId } });
    return response.data.queries;
  },

  async alertChannels(): Promise<string[]> {
    return (await axios.get<{channels: string[]}>(`${API_BASE}/audit/alerts/status`)).data.channels;
  },

  async sendTestAlert(): Promise<Record<string, string>> {
    return (await axios.post<{results: Record<string, string>}>(`${API_BASE}/audit/alerts/test`)).data.results;
  },
};

// Reshape a stored audit row into the live telemetry shape that
// SecurityPanel / RiskTimeline render.
export function auditToTelemetry(q: AuditQuery): TelemetryEvent {
  return {
    session_id: q.session_id,
    timestamp: new Date(q.timestamp).getTime() / 1000,
    query: q.query,
    intent: q.intent,
    retrieval_strategy: q.retrieval_outcome,
    result_count: q.result_count,
    signals: q.signals ?? { semantic_focus: 0, temporal_frequency: 0, entity_focus: 0, graph_footprint: 0, sensitivity_exposure: 0 },
    instantaneous_risk: q.instantaneous_risk ?? q.risk_score,
    smoothed_risk: q.risk_score,
    policy: q.policy ?? undefined,
    blocked_by_policy: q.blocked,
    role: q.role,
    response_mode: q.behavioral_mode as ResponseMode,
    exposure: q.exposure ?? undefined,
  };
}

// Who asked: the email when Clerk provides it, otherwise the Clerk user id.
// Who a row belongs to, most readable first: the admin-set name (SECURITY_USER_NAMES),
// the sign-in email, then "Role · short id" (Clerk ids like user_3JzCIk... mean nothing
// on screen). Rows from before sign-in was enforced have no user at all.
export const whoOf = (row: { user_name?: string | null; user_email: string | null; user_id: string | null; role?: string }) =>
  row.user_name || row.user_email
  || (row.user_id ? `${row.role ?? 'User'} · ${row.user_id.replace(/^user_/, '').slice(0, 4)}` : 'Before sign-in (unrecorded)');
