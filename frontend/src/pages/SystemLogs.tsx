import { useState } from 'react';
import { ChevronDown, ChevronRight, Download, Search } from 'lucide-react';
import clsx from 'clsx';
import { auditApi, whoOf } from '../api';
import type { AuditSession, AuditQuery } from '../api';
import { usePolling } from '../usePolling';
import { ModeBadge } from '../components/ModeBadge';
import { PageHeader, ErrorNote } from '../components/AdminUi';

const SESSION_LIMIT = 200;
const MODES = ['ALL', 'ALLOW', 'MASK', 'BLOCK'] as const;

const csvCell = (v: unknown) => `"${String(v ?? '').replace(/"/g, '""')}"`;

function downloadCsv(sessions: AuditSession[]) {
  const header = ['session_id', 'user', 'role', 'started_at', 'ended_at', 'status', 'queries', 'peak_risk', 'final_risk', 'highest_mode'];
  const rows = sessions.map((s) => [s.session_id, whoOf(s), s.role, s.started_at, s.ended_at, s.status, s.query_count, s.peak_risk_score, s.final_risk_score, s.highest_behavioral_mode]);
  const csv = [header, ...rows].map((r) => r.map(csvCell).join(',')).join('\n');
  const url = URL.createObjectURL(new Blob([csv], { type: 'text/csv' }));
  const a = Object.assign(document.createElement('a'), { href: url, download: `aegisgraph-audit-${new Date().toISOString().slice(0, 10)}.csv` });
  a.click();
  URL.revokeObjectURL(url);
}

function SessionQueries({ sessionId }: { sessionId: string }) {
  const { data, error } = usePolling(() => auditApi.getSessionQueries(sessionId), 10000, [sessionId]);
  if (error) return <p className="px-4 py-3 text-sm text-red-300">{error}</p>;
  if (!data) return <p className="px-4 py-3 text-sm text-slate-400">Loading questions…</p>;
  return (
    <table className="w-full text-sm">
      <thead className="text-left text-xs text-slate-400">
        <tr className="border-b border-slate-800">
          <th className="px-4 py-2 font-medium">Time</th>
          <th className="px-2 py-2 font-medium">Risk</th>
          <th className="px-2 py-2 font-medium">Policy</th>
          <th className="hidden px-2 py-2 font-medium md:table-cell">Outcome</th>
          <th className="hidden px-2 py-2 font-medium sm:table-cell">Records</th>
          <th className="px-2 py-2 font-medium">Question</th>
        </tr>
      </thead>
      <tbody>
        {data.map((q: AuditQuery) => (
          <tr key={q.id} className="border-b border-slate-800/50 last:border-0 align-top">
            <td className="whitespace-nowrap px-4 py-2 text-xs text-slate-400">{new Date(q.timestamp).toLocaleTimeString()}</td>
            <td className="px-2 py-2 font-mono text-slate-200">{q.risk_score.toFixed(2)}</td>
            <td className="px-2 py-2"><ModeBadge mode={q.behavioral_mode} /></td>
            <td className="hidden px-2 py-2 text-xs text-slate-300 md:table-cell">{q.retrieval_outcome}</td>
            <td className="hidden px-2 py-2 text-slate-300 sm:table-cell">{q.result_count}</td>
            <td className="px-2 py-2 text-slate-200">{q.query}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

export function SystemLogs() {
  const { data, error, loading, reload } = usePolling(() => auditApi.getSessions(SESSION_LIMIT), 10000);
  const [expanded, setExpanded] = useState<string | null>(null);
  const [search, setSearch] = useState('');
  const [mode, setMode] = useState<(typeof MODES)[number]>('ALL');
  const [activeOnly, setActiveOnly] = useState(false);

  const needle = search.trim().toLowerCase();
  const sessions = (data ?? []).filter(
    (s) =>
      (mode === 'ALL' || s.highest_behavioral_mode === mode) &&
      (!activeOnly || s.status === 'ACTIVE') &&
      (!needle || `${whoOf(s)} ${s.session_id} ${s.role}`.toLowerCase().includes(needle)),
  );

  return (
    <div className="flex min-h-0 flex-1 flex-col overflow-y-auto">
      <PageHeader title="Audit log" subtitle={`Every chat session and the questions in it · newest ${SESSION_LIMIT} sessions`} loading={loading} onRefresh={reload}>
        <button
          onClick={() => downloadCsv(sessions)}
          disabled={sessions.length === 0}
          className="flex items-center gap-2 rounded-md border border-slate-700 px-3 py-1.5 text-xs text-slate-300 hover:bg-slate-800 disabled:opacity-50"
        >
          <Download className="h-3.5 w-3.5" /> Export CSV
        </button>
      </PageHeader>
      <ErrorNote text={error} />

      <div className="flex flex-wrap items-center gap-3 px-6 pt-5">
        <label className="relative min-w-[14rem] flex-1 sm:max-w-sm">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-500" />
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search user, role or session id"
            aria-label="Search sessions"
            className="w-full rounded-md border border-slate-700 bg-slate-900 py-2 pl-9 pr-3 text-sm text-slate-100 placeholder:text-slate-500 focus:border-blue-500 focus:outline-none"
          />
        </label>
        <div className="flex rounded-md border border-slate-700 p-0.5" role="group" aria-label="Filter by highest policy">
          {MODES.map((m) => (
            <button
              key={m}
              onClick={() => setMode(m)}
              aria-pressed={mode === m}
              className={clsx('rounded px-2.5 py-1 text-xs', mode === m ? 'bg-slate-700 text-slate-50' : 'text-slate-400 hover:text-slate-100')}
            >
              {m === 'ALL' ? 'All' : m === 'ALLOW' ? 'Normal' : m === 'MASK' ? 'Masked' : 'Blocked'}
            </button>
          ))}
        </div>
        <label className="flex items-center gap-2 text-sm text-slate-300">
          <input type="checkbox" checked={activeOnly} onChange={(e) => setActiveOnly(e.target.checked)} className="accent-blue-500" />
          Active only
        </label>
        <span className="ml-auto text-xs text-slate-500">{sessions.length} shown</span>
      </div>

      <div className="flex flex-col gap-2 p-6">
        {sessions.length === 0 && !loading && (
          <p className="rounded-lg border border-slate-800 bg-slate-900 p-6 text-center text-sm text-slate-400">
            {data?.length ? 'No sessions match these filters.' : 'No sessions recorded yet.'}
          </p>
        )}
        {sessions.map((s) => {
          const open = expanded === s.session_id;
          const duration = s.ended_at ? `${Math.round((new Date(s.ended_at).getTime() - new Date(s.started_at).getTime()) / 1000)}s` : null;
          return (
            <div key={s.session_id} className="overflow-hidden rounded-lg border border-slate-800 bg-slate-900">
              <button
                onClick={() => setExpanded(open ? null : s.session_id)}
                aria-expanded={open}
                className="grid w-full grid-cols-[auto_1fr_auto] items-center gap-3 px-4 py-3 text-left hover:bg-slate-800/60 md:grid-cols-[auto_minmax(0,2fr)_1fr_1fr_auto]"
              >
                {open ? <ChevronDown className="h-4 w-4 text-slate-400" /> : <ChevronRight className="h-4 w-4 text-slate-400" />}
                <div className="min-w-0">
                  <div className="truncate text-sm text-slate-100" title={whoOf(s)}>{whoOf(s)}</div>
                  <div className="text-xs text-slate-500">{s.role} · session {s.session_id.slice(0, 8)}</div>
                </div>
                <div className="hidden text-xs text-slate-400 md:block">
                  {new Date(s.started_at).toLocaleString()}
                  <div>{s.query_count} questions{duration && ` · ${duration}`}</div>
                </div>
                <div className="hidden text-xs text-slate-400 md:block">
                  peak <span className="font-mono text-slate-200">{s.peak_risk_score.toFixed(2)}</span> · final <span className="font-mono text-slate-200">{s.final_risk_score.toFixed(2)}</span>
                </div>
                <div className="flex items-center gap-2">
                  <ModeBadge mode={s.highest_behavioral_mode} />
                  {s.status === 'ACTIVE' && <span className="hidden text-xs text-emerald-400 sm:inline">● active</span>}
                </div>
              </button>
              {open && (
                <div className="border-t border-slate-800 bg-slate-950">
                  <SessionQueries sessionId={s.session_id} />
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
