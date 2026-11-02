import { useState, useRef, useEffect } from 'react';
import { useChat, type Message, type PendingAnswer } from '../contexts/ChatContext';
import { Send, Loader2, ShieldBan, Database, Network, ArrowRight, MessagesSquare } from 'lucide-react';
import clsx from 'clsx';
import { FormattedText } from './FormattedText';
import { ModeBadge, SensitivityBadges, explainSignals } from './ModeBadge';

const INPUT_MAX_HEIGHT = 150;

// Grow the textarea with its content, scrolling only once it hits the cap.
function fitToContent(el: HTMLTextAreaElement | null) {
  if (!el) return;
  el.style.height = 'auto';
  el.style.height = `${Math.min(el.scrollHeight, INPUT_MAX_HEIGHT)}px`;
  el.style.overflowY = el.scrollHeight > INPUT_MAX_HEIGHT ? 'auto' : 'hidden';
}

interface ChatPanelProps {
  messages: Message[];
  loading: boolean;
  pending?: PendingAnswer | null;
  error?: string | null;
  onSendMessage: (msg: string) => void;
}

const QUICK_START_QUERIES = [
  'What can I explore in this knowledge graph?',
  'Who are the employees?',
  'Who is Christopher Calger?',
  'What emails did he send?',
];

function AgentMeta({ msg }: { msg: Message }) {
  const { setActiveGraphData, activeGraphData } = useChat();
  const t = msg.telemetry;
  if (!t) return null;
  const showing = activeGraphData === msg.graph_data;

  return (
    <div className="mt-3 border-t border-slate-800 pt-3">
      <div className="flex flex-wrap items-center gap-2 text-xs text-slate-400">
        <ModeBadge mode={t.response_mode} />
        <span className="inline-flex items-center gap-1 rounded border border-slate-800 px-2 py-0.5 font-mono" title="Records retrieved from the knowledge graph">
          <Database className="h-3 w-3" /> {t.result_count} records
        </span>
        {t.retrieval_model && (
          <span className="rounded border border-slate-800 px-2 py-0.5 font-mono"
            title="Fetched by the AI agent writing read-only Cypher through the Neo4j MCP server">
            Data: {t.retrieval_model.split('/').pop()}
          </span>
        )}
        {msg.llm_model && (
          <span className="rounded border border-slate-800 px-2 py-0.5 font-mono" title="Answer written by Ollama (local)">
            Answer: {msg.llm_model.split('/').pop()}
          </span>
        )}
        <SensitivityBadges exposure={t.exposure} />
        {msg.graph_data && (
          <button
            onClick={() => setActiveGraphData(msg.graph_data!)}
            className={clsx(
              'inline-flex items-center gap-1 rounded border px-2 py-0.5 transition-colors',
              showing ? 'border-blue-500/50 bg-blue-500/10 text-blue-400' : 'border-slate-700 hover:border-blue-500/50 hover:text-slate-50',
            )}
          >
            <Network className="h-3 w-3" /> {showing ? 'Shown in graph' : 'Show in graph'}
          </button>
        )}
      </div>
      <details className="mt-2 text-xs text-slate-400">
        <summary className="cursor-pointer select-none hover:text-slate-200">Why this policy?</summary>
        <p className="mt-1.5 leading-relaxed">
          Risk after this question: <span className="font-mono text-slate-200">{t.smoothed_risk.toFixed(2)}</span>{' '}
          (this question alone: <span className="font-mono text-slate-200">{t.instantaneous_risk.toFixed(2)}</span>).{' '}
          {explainSignals(t.signals)}
        </p>
      </details>
    </div>
  );
}

export function ChatPanel({ messages, loading, pending, error, onSendMessage }: ChatPanelProps) {
  const [input, setInput] = useState('');
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, loading, pending?.text]);

  useEffect(() => {
    if (!loading) inputRef.current?.focus();
  }, [loading]);

  // Re-fit the box whenever the text changes (typing, or cleared after sending).
  useEffect(() => {
    fitToContent(inputRef.current);
  }, [input]);

  const handleSubmit = (e: React.SyntheticEvent) => {
    e.preventDefault();
    if (!input.trim() || loading) return;
    onSendMessage(input.trim());
    setInput('');
  };

  return (
    <div className="flex h-full flex-col bg-slate-950">
      <div className="flex-1 overflow-y-auto px-4 py-6">
        <div className="mx-auto flex max-w-3xl flex-col gap-5">
          {messages.length === 0 && (
            <div className="flex flex-col items-center pt-[10vh] text-center">
              <div className="mb-5 flex h-14 w-14 items-center justify-center rounded-lg border border-slate-800 bg-slate-900">
                <MessagesSquare className="h-7 w-7 text-blue-500" />
              </div>
              <h2 className="mb-2 text-xl font-semibold text-slate-50">Ask the Enron knowledge graph</h2>
              <p className="mb-8 max-w-md text-sm leading-relaxed text-slate-400">
                Every question is checked for risky behaviour. If your pattern looks like data harvesting, names get masked and, at high risk, answers are blocked.
              </p>
              <div className="grid w-full max-w-md gap-2">
                {QUICK_START_QUERIES.map((query) => (
                  <button
                    key={query}
                    onClick={() => !loading && onSendMessage(query)}
                    disabled={loading}
                    className="group flex items-center rounded-lg border border-slate-800 bg-slate-900 px-4 py-3 text-left text-sm text-slate-100 transition-colors hover:border-blue-500/50 disabled:opacity-50"
                  >
                    <ArrowRight className="mr-3 h-4 w-4 text-slate-500 group-hover:text-blue-500" />
                    {query}
                  </button>
                ))}
              </div>
            </div>
          )}

          {messages.map((msg) => {
            const blocked = msg.telemetry?.blocked_by_policy;
            if (msg.sender === 'user') {
              return (
                <div key={msg.id} className="ml-auto max-w-[85%] whitespace-pre-wrap rounded-lg border border-slate-700 bg-slate-800 px-4 py-3 text-sm text-slate-50">
                  {msg.text}
                </div>
              );
            }
            return (
              <div
                key={msg.id}
                className={clsx('rounded-lg border px-4 py-3', blocked ? 'border-red-900/60 bg-red-950/20' : 'border-slate-800 bg-slate-900')}
              >
                {blocked && (
                  <div className="mb-2 flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-red-400">
                    <ShieldBan className="h-4 w-4" /> Blocked by security policy
                  </div>
                )}
                <div className={clsx('whitespace-pre-wrap text-sm leading-relaxed', blocked ? 'text-red-300' : 'text-slate-200')}>
                  <FormattedText text={msg.text} />
                </div>
                <AgentMeta msg={msg} />
              </div>
            );
          })}

          {loading && pending?.text ? (
            // The answer as it is being written; replaced by the finished message (with
            // badges and policy details) when the server sends it.
            <div className="rounded-lg border border-slate-800 bg-slate-900 px-4 py-3" aria-live="polite">
              <div className="whitespace-pre-wrap text-sm leading-relaxed text-slate-200">
                <FormattedText text={pending.text} />
                <span className="ml-0.5 inline-block h-3.5 w-1.5 animate-pulse bg-blue-500 align-middle" aria-hidden />
              </div>
            </div>
          ) : loading && (
            <div className="flex items-center gap-3 rounded-lg border border-slate-800 bg-slate-900 px-4 py-3" role="status">
              <Loader2 className="h-4 w-4 animate-spin text-blue-500" />
              <div>
                <div className="text-sm text-slate-100">{pending?.status || 'Working…'}</div>
                <div className="text-xs text-slate-400">Checking risk, fetching data from the graph, then writing the answer.</div>
              </div>
            </div>
          )}

          {error && (
            <div className="flex items-center gap-3 rounded-lg border border-red-900/60 bg-red-950/20 px-4 py-3" role="alert">
              <ShieldBan className="h-4 w-4 shrink-0 text-red-400" />
              <span className="text-sm text-red-300">{error}</span>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>
      </div>

      <div className="shrink-0 border-t border-slate-800 p-4">
        <form onSubmit={handleSubmit} className="relative mx-auto flex max-w-3xl items-end">
          <textarea
            ref={inputRef}
            aria-label="Your question"
            className="w-full resize-none overflow-hidden rounded-lg border border-slate-700 bg-slate-900 py-3.5 pl-4 pr-14 text-sm text-slate-50 placeholder:text-slate-500 focus:border-blue-500 focus:outline-none"
            placeholder="Ask about a person, their emails or a topic…"
            rows={1}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                handleSubmit(e);
              }
            }}
            disabled={loading}
            style={{ minHeight: '52px', maxHeight: `${INPUT_MAX_HEIGHT}px` }}
          />
          <button
            type="submit"
            disabled={loading || !input.trim()}
            aria-label="Send"
            className="absolute bottom-2 right-2 flex items-center justify-center rounded-md bg-blue-600 p-2 text-white transition-colors hover:bg-blue-500 disabled:opacity-50"
          >
            <Send className="h-4 w-4" />
          </button>
        </form>
        <p className="mt-2 text-center text-xs text-slate-500">Enter to send · Shift+Enter for a new line</p>
      </div>
    </div>
  );
}
