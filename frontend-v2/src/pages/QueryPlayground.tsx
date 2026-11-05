import { useEffect, useState } from 'react';
import { AnimatePresence, motion } from 'motion/react';
import { Network, Activity, X } from 'lucide-react';
import clsx from 'clsx';
import { useChat } from '../contexts/ChatContext';
import type { TelemetryEvent } from '../api';
import { useIdentity } from '../useIdentity';
import { ChatPanel } from '../components/ChatPanel';
import { NetworkGraph } from '../components/NetworkGraph';
import { SecurityPanel } from '../components/SecurityPanel';
import { ModeBadge } from '../components/ModeBadge';
import { RiskMeter } from '../components/RiskMeter';

type Panel = 'graph' | 'risk' | null;

export function QueryPlayground() {
  const { messages, loading, pending, error, sendMessage } = useChat();
  // Role and risk come from the server (risk is remembered per user and survives
  // reloads); refetched after every message so the bar stays current.
  const identity = useIdentity(messages.length);
  // Desktop opens on the graph; small screens start with the chat alone.
  const [panel, setPanel] = useState<Panel>(() => (window.matchMedia('(min-width: 1024px)').matches ? 'graph' : null));

  // The whole interface takes the colour of the current mode (see index.css).
  const mode = messages.at(-1)?.telemetry?.response_mode ?? identity?.response_mode ?? 'ALLOW';
  useEffect(() => {
    document.documentElement.dataset.mode = mode;
    return () => { delete document.documentElement.dataset.mode; };
  }, [mode]);

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
          <h1 className="font-display text-lg text-slate-50">Workspace</h1>
          <div className="ml-auto flex items-center gap-2">
            {identity && (
              <div className="hidden items-center gap-3 sm:flex" title="Your remembered risk and the policy your next question will face">
                <span className="rounded-full bg-slate-800 px-2.5 py-0.5 text-xs text-slate-300">{identity.role}</span>
                <RiskMeter risk={messages.at(-1)?.telemetry?.smoothed_risk ?? identity.risk_score} className="w-28" />
                <span className="w-9 text-sm text-slate-300">{(messages.at(-1)?.telemetry?.smoothed_risk ?? identity.risk_score).toFixed(2)}</span>
                <ModeBadge mode={mode} />
              </div>
            )}
            {identity === undefined && <span className="text-xs text-red-400">Server unreachable</span>}
            {tabButton('graph', 'Graph', Network)}
            {tabButton('risk', 'My risk', Activity)}
          </div>
        </header>
        <div className="min-h-0 flex-1">
          <ChatPanel messages={messages} loading={loading} pending={pending} error={error} onSendMessage={sendMessage} />
        </div>
      </section>

      {/* Side panel: docked on large screens, full-screen overlay on small ones */}
      <AnimatePresence>
      {panel && (
        <motion.aside
          key="panel"
          initial={{ opacity: 0, x: 48 }}
          animate={{ opacity: 1, x: 0 }}
          exit={{ opacity: 0, x: 48 }}
          transition={{ duration: 0.4, ease: [0.22, 1, 0.36, 1] }}
          className="fixed inset-0 z-40 flex flex-col bg-slate-950 lg:static lg:z-auto lg:w-[42%] lg:max-w-[640px] lg:border-l lg:border-slate-800 lg:bg-slate-950/60">
          <div className="flex h-14 shrink-0 items-center justify-between border-b border-slate-800 px-4">
            <span className="text-sm font-semibold">{panel === 'graph' ? 'Knowledge graph' : 'My risk'}</span>
            <button onClick={() => setPanel(null)} className="p-1 text-slate-400 hover:text-slate-50" aria-label="Close panel">
              <X className="h-4 w-4" />
            </button>
          </div>
          <div className="min-h-0 flex-1">
            {panel === 'graph' ? <NetworkGraph /> : <SecurityPanel telemetry={history.at(-1) ?? null} history={history} />}
          </div>
        </motion.aside>
      )}
      </AnimatePresence>
    </div>
  );
}
