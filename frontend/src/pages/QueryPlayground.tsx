import { useEffect, useState } from 'react';
import { Network, Activity, X } from 'lucide-react';
import clsx from 'clsx';
import { useChat } from '../contexts/ChatContext';
import { chatApi } from '../api';
import type { LlmProvider, LlmProviderInfo, TelemetryEvent } from '../api';
import { useIdentity } from '../useIdentity';
import { ChatPanel } from '../components/ChatPanel';
import { NetworkGraph } from '../components/NetworkGraph';
import { SecurityPanel } from '../components/SecurityPanel';
import { ModeBadge } from '../components/ModeBadge';

type Panel = 'graph' | 'risk' | null;

export function QueryPlayground() {
  const { messages, loading, error, sendMessage, llmProvider, setLlmProvider } = useChat();
  // Models the server offers; OpenRouter is greyed out when it has no API key.
  const [llmInfo, setLlmInfo] = useState<LlmProviderInfo[]>([]);
  useEffect(() => {
    chatApi.llmProviders().then((r) => setLlmInfo(r.providers)).catch(() => {});
  }, []);
  const llmChoices: { id: LlmProvider; label: string }[] = [
    { id: 'ollama', label: 'Llama' },
    { id: 'openrouter', label: 'OpenRouter' },
  ];
  // Role and risk come from the server (risk is remembered per user and survives
  // reloads); refetched after every message so the bar stays current.
  const identity = useIdentity(messages.length);
  // Desktop opens on the graph; small screens start with the chat alone.
  const [panel, setPanel] = useState<Panel>(() => (window.matchMedia('(min-width: 1024px)').matches ? 'graph' : null));

  const history: TelemetryEvent[] = messages.flatMap((m) => (m.telemetry ? [m.telemetry] : []));
  const toggle = (p: Exclude<Panel, null>) => setPanel((cur) => (cur === p ? null : p));

  const tabButton = (p: Exclude<Panel, null>, label: string, Icon: typeof Network) => (
    <button
      onClick={() => toggle(p)}
      aria-pressed={panel === p}
      className={clsx(
        'flex items-center gap-1.5 rounded-md border px-2.5 py-1.5 text-xs font-medium transition-colors',
        panel === p ? 'border-blue-500/50 bg-blue-500/10 text-blue-400' : 'border-slate-700 text-slate-300 hover:bg-slate-800',
      )}
    >
      <Icon className="h-3.5 w-3.5" /> {label}
    </button>
  );

  return (
    <div className="flex min-h-0 flex-1">
      {/* Chat column */}
      <section className="flex min-w-0 flex-1 flex-col">
        <header className="flex h-14 shrink-0 items-center gap-3 border-b border-slate-800 px-4">
          <h1 className="text-sm font-semibold text-slate-50">Workspace</h1>
          <div className="ml-auto flex items-center gap-2">
            {identity && (
              <div className="hidden items-center gap-2 sm:flex" title="Your remembered risk and the policy your next question will face">
                <span className="rounded border border-slate-700 px-2 py-0.5 text-xs font-mono text-slate-300">{identity.role}</span>
                <span className="text-xs font-mono text-slate-400">Risk {identity.risk_score.toFixed(2)}</span>
                <ModeBadge mode={identity.response_mode} />
              </div>
            )}
            <div className="flex items-center rounded-md border border-slate-700 p-0.5" role="group" aria-label="Model that writes the answer"
              title="Writes the answer. The data itself is fetched by the NVIDIA agent (or the fixed queries if it is unavailable).">
              <span className="px-1.5 text-xs text-slate-500">Answer</span>
              {llmChoices.map(({ id, label }) => {
                const info = llmInfo.find((i) => i.id === id);
                const disabled = info ? !info.available : false;
                return (
                  <button
                    key={id}
                    onClick={() => setLlmProvider(id)}
                    disabled={disabled || loading}
                    aria-pressed={llmProvider === id}
                    title={info ? (disabled ? `${label} is not configured on the server` : info.model) : label}
                    className={clsx(
                      'rounded px-2 py-1 text-xs font-medium transition-colors disabled:cursor-not-allowed disabled:opacity-40',
                      llmProvider === id ? 'bg-blue-500/10 text-blue-400' : 'text-slate-300 hover:bg-slate-800',
                    )}
                  >
                    {label}
                  </button>
                );
              })}
            </div>
            {identity === undefined && <span className="text-xs text-red-400">Server unreachable</span>}
            {tabButton('graph', 'Graph', Network)}
            {tabButton('risk', 'My risk', Activity)}
          </div>
        </header>
        <div className="min-h-0 flex-1">
          <ChatPanel messages={messages} loading={loading} error={error} onSendMessage={sendMessage} />
        </div>
      </section>

      {/* Side panel: docked on large screens, full-screen overlay on small ones */}
      {panel && (
        <aside className="fixed inset-0 z-40 flex flex-col bg-slate-950 lg:static lg:z-auto lg:w-[42%] lg:max-w-[640px] lg:border-l lg:border-slate-800">
          <div className="flex h-14 shrink-0 items-center justify-between border-b border-slate-800 px-4">
            <span className="text-sm font-semibold">{panel === 'graph' ? 'Knowledge graph' : 'My risk'}</span>
            <button onClick={() => setPanel(null)} className="p-1 text-slate-400 hover:text-slate-50" aria-label="Close panel">
              <X className="h-4 w-4" />
            </button>
          </div>
          <div className="min-h-0 flex-1">
            {panel === 'graph' ? <NetworkGraph /> : <SecurityPanel telemetry={history.at(-1) ?? null} history={history} />}
          </div>
        </aside>
      )}
    </div>
  );
}
