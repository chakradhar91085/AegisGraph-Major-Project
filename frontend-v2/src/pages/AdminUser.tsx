import { Link, useParams } from 'react-router-dom';
import { ArrowLeft } from 'lucide-react';
import { auditApi, auditToTelemetry, whoOf } from '../api';
import { usePolling } from '../usePolling';
import { ModeBadge } from '../components/ModeBadge';
import { SecurityPanel } from '../components/SecurityPanel';
import { PageHeader, StatTile, Card, ErrorNote } from '../components/AdminUi';

// One user's risk history: their own timeline, never mixed with other users.
export function AdminUser() {
  const { userId = '' } = useParams();
  const { data, error, loading, reload } = usePolling(() => auditApi.getRecent(500, userId), 10000, [userId]);
  const queries = data ?? [];
  const history = [...queries].reverse().map(auditToTelemetry); // oldest -> newest
  const latest = queries[0];
  const peak = Math.max(0, ...queries.map((q) => q.risk_score));
  const escalated = queries.filter((q) => q.behavioral_mode !== 'ALLOW').length;

  return (
    <div className="flex min-h-0 flex-1 flex-col overflow-y-auto">
      <PageHeader
        title={latest ? whoOf(latest) : userId}
        subtitle={<>{latest?.role ?? 'User'} · <span className="font-mono">{userId}</span></>}
        loading={loading}
        onRefresh={reload}
      >
        <Link to="/admin" className="flex items-center gap-1 rounded-md border border-slate-700 px-3 py-1.5 text-xs text-slate-300 hover:bg-slate-800">
          <ArrowLeft className="h-3.5 w-3.5" /> Overview
        </Link>
      </PageHeader>
      <ErrorNote text={error} />

      <div className="grid grid-cols-2 gap-3 px-6 pt-5 lg:grid-cols-4">
        <StatTile label="Questions" value={queries.length} />
        <StatTile label="Risk at last question" value={latest ? latest.risk_score.toFixed(2) : '–'} />
        <StatTile label="Peak risk" value={peak.toFixed(2)} />
        <StatTile label="Masked or blocked" value={escalated} tone={escalated ? 'text-amber-400' : undefined} />
      </div>

      <div className="grid gap-4 p-6 xl:grid-cols-2">
        <div className="h-[560px] overflow-hidden rounded-lg border border-slate-800">
          <SecurityPanel telemetry={history.at(-1) ?? null} history={history} />
        </div>
        <Card title="Questions, newest first">
          {queries.length === 0 ? (
            <p className="p-4 text-sm text-slate-400">{loading ? 'Loading…' : 'No questions recorded for this user.'}</p>
          ) : (
            <ul className="max-h-[510px] divide-y divide-slate-800/60 overflow-y-auto">
              {queries.map((q) => (
                <li key={q.id} className="px-4 py-3">
                  <div className="mb-1 flex items-center justify-between gap-2 text-xs text-slate-400">
                    <span>{new Date(q.timestamp).toLocaleString()} · risk <span className="font-mono text-slate-200">{q.risk_score.toFixed(2)}</span> · {q.result_count} records</span>
                    <ModeBadge mode={q.behavioral_mode} />
                  </div>
                  <p className="text-sm text-slate-200">{q.query}</p>
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>
    </div>
  );
}
