import React, { createContext, useContext, useState, useCallback } from 'react';
import axios from 'axios';
import { chatApi, ChatStreamError } from '../api';
import type { TelemetryEvent, GraphVisualizationPayload, LlmProvider } from '../api';

export interface Message {
  id: string;
  sender: 'user' | 'agent';
  text: string;
  telemetry?: TelemetryEvent;
  graph_data?: GraphVisualizationPayload;
  llm_provider?: string;
  llm_model?: string;
}

// Plain-language explanation of a failed chat request.
function describeError(err: unknown): string {
  // HTTP status of the failure; 0 = never reached the server; null = not an HTTP failure.
  const status = axios.isAxiosError(err) ? (err.response?.status ?? 0)
    : err instanceof ChatStreamError ? err.status : null;
  if (status === null) return 'Something went wrong while sending your question.';
  if (status === 0) return "Can't reach the AegisGraph server. Check that the backend is running.";
  if (status === 401) return 'Your sign-in has expired. Please sign in again.';
  if (status === 403) return "Your account isn't allowed to do that.";
  if (status === 429) return 'Please wait for your previous question to finish.';
  if (status === 422) return 'That question could not be read. Try rephrasing it (max 2000 characters).';
  if (status >= 500) return 'The server ran into a problem while answering. Please try again.';
  return `The request failed (HTTP ${status}).`;
}

// The answer being written right now: progress text, then the words as they arrive.
export interface PendingAnswer {
  status: string;
  text: string;
}

interface ChatContextType {
  messages: Message[];
  loading: boolean;
  pending: PendingAnswer | null;
  error: string | null;

  llmProvider: LlmProvider;
  setLlmProvider: (p: LlmProvider) => void;
  sendMessage: (text: string) => Promise<void>;
  clearSession: () => void;
  resetConversation: () => void;
  endActiveSession: () => Promise<void>;
  activeGraphData: GraphVisualizationPayload | null;
  setActiveGraphData: (data: GraphVisualizationPayload | null) => void;
}

const ChatContext = createContext<ChatContextType | undefined>(undefined);

export function ChatProvider({ children }: { children: React.ReactNode }) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [loading, setLoading] = useState(false);
  const [pending, setPending] = useState<PendingAnswer | null>(null);
  const [error, setError] = useState<string | null>(null);

  const [activeGraphData, setActiveGraphData] = useState<GraphVisualizationPayload | null>(null);

  // Which model answers. Llama (Ollama) unless the user switches; remembered in this browser.
  const [llmProvider, setLlmProviderState] = useState<LlmProvider>(() => {
    try {
      return localStorage.getItem('aegis_llm_provider') === 'openrouter' ? 'openrouter' : 'ollama';
    } catch {
      return 'ollama';
    }
  });
  const setLlmProvider = useCallback((p: LlmProvider) => {
    setLlmProviderState(p);
    try {
      localStorage.setItem('aegis_llm_provider', p);
    } catch { /* storage blocked: the choice just won't persist */ }
  }, []);

  const sendMessage = useCallback(async (text: string) => {
    const userMessage: Message = { id: Date.now().toString(), sender: 'user', text };
    setMessages((prev) => [...prev, userMessage]);
    setLoading(true);
    setError(null);
    setPending({ status: 'Checking risk…', text: '' });

    try {
      const sessionToken = sessionStorage.getItem('aegis_session_token') || undefined;
      const response = await chatApi.sendMessageStream(text, sessionToken, llmProvider, {
        onStatus: (status) => setPending((p) => ({ text: '', ...p, status })),
        onToken: (piece) => setPending((p) => ({ status: '', ...p, text: (p?.text ?? '') + piece })),
      });

      // The server renews the ticket on every response; always store the
      // latest one so the session can continue securely.
      sessionStorage.setItem('aegis_session_token', response.session_token);
      sessionStorage.setItem('aegis_session_id', response.session_id);

      const agentMessage: Message = {
        id: (Date.now() + 1).toString(),
        sender: 'agent',
        text: response.answer,
        telemetry: response.telemetry,
        graph_data: response.graph_data,
        llm_provider: response.llm_provider,
        llm_model: response.llm_model,
      };

      setMessages((prev) => [...prev, agentMessage]);
      
      // Auto-visualize the new graph data if it exists
      if (response.graph_data) {
        setActiveGraphData(response.graph_data);
      }
    } catch (err) {
      setError(describeError(err));
    } finally {
      setLoading(false);
      setPending(null);
    }
  }, [llmProvider]);

  // Forget the conversation in this browser tab (used on sign-out, so the next
  // person on the same browser never sees the previous user's chat).
  const resetConversation = useCallback(() => {
    sessionStorage.removeItem('aegis_session_token');
    sessionStorage.removeItem('aegis_session_id');
    setMessages([]);
    setError(null);
    setActiveGraphData(null);
  }, []);

  const clearSession = useCallback(() => {
    // Best effort: the server honors this only for Auditors in demo mode.
    chatApi.resetRisk().catch(() => {});
    resetConversation();
  }, [resetConversation]);

  const endActiveSession = useCallback(async () => {
    const sessionToken = sessionStorage.getItem('aegis_session_token');
    if (sessionToken) {
      try {
        await chatApi.endSession(sessionToken);
      } catch (err) {
        console.error('Failed to end session on backend', err);
      }
      clearSession();
    }
  }, [clearSession]);

  return (
    <ChatContext.Provider value={{
      messages, loading, pending, error, llmProvider, setLlmProvider,
      sendMessage, clearSession, resetConversation, endActiveSession,
      activeGraphData, setActiveGraphData
    }}>
      {children}
    </ChatContext.Provider>
  );
}

export function useChat() {
  const context = useContext(ChatContext);
  if (context === undefined) {
    throw new Error('useChat must be used within a ChatProvider');
  }
  return context;
}
