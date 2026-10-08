import { Link } from 'react-router-dom';
import { ChevronRight } from 'lucide-react';
import { auditApi, whoOf, RISK_BANDS } from '../api';
import type { AuditQuery } from '../api';
import { usePolling } from '../usePolling';
import { ModeBadge } from '../components/ModeBadge';
import { PageHeader, StatTile, Card, ErrorNote, timeAgo } from '../components/AdminUi';

const FEED_SIZE = 200;

interface UserRow {
  key: string;
  userId: string | null;
  who: string;
  role: string;
  latest: AuditQuery;
  peak: number;
  count: number;
}

// One row per user from the newest-first feed: their latest query sets the
// current risk/mode, the max over their rows is the peak.
function groupByUser(queries: AuditQuery[]): UserRow[] {
  const rows = new Map<string, UserRow>();
  for (const q of queries) {
    const key = q.user_id ?? `session:${q.session_id}`;
    const row = rows.get(key);
    if (row) {
      row.peak = Math.max(row.peak, q.risk_score);
      row.count += 1;
    } else {
      rows.set(key, { key, userId: q.user_id, who: whoOf(q), role: q.role, latest: q, peak: q.risk_score, count: 1 });
    }
  }
  return [...rows.values()].sort((a, b) => b.latest.risk_score - a.latest.risk_score);
}

const riskTone = (r: number) => (r >= RISK_BANDS.high ? 'text-red-400' : r >= RISK_BANDS.medium ? 'text-amber-400' : 'text-slate-200');

export function AdminOverview() {
  const { data, error, loading, reload } = usePolling(() => auditApi.getRecent(FEED_SIZE), 5000);
  const queries = data ?? [];
  const users = groupByUser(queries);
  const masked = queries.filter((q) => q.behavioral_mode === 'MASK').length;
  const blocked = queries.filter((q) => q.blocked || q.behavioral_mode === 'BLOCK').length;
  const escalations = queries.filter((q) => q.behavioral_mode !== 'ALLOW').slice(0, 15);

  return (
    <div className="flex min-h-0 flex-1 flex-col overflow-y-auto">
      <PageHeader title="Overview" subtitle={`Live view of the last ${FEED_SIZE} questions across all users · refreshes every 5s`} loading={loading} onRefresh={reload} />
      <ErrorNote text={error} />

      <div className="grid grid-cols-2 gap-3 px-6 pt-5 lg:grid-cols-4">
        <StatTile label="Questions in feed" value={queries.length} />
        <StatTile label="Users" value={users.length} />
        <StatTile label="Answered with masking" value={masked} tone={masked ? 'text-amber-400' : undefined} />
        <StatTile label="Blocked" value={blocked} tone={blocked ? 'text-red-400' : undefined} />
      </div>

      <div className="grid min-h-0 gap-4 p-6 xl:grid-cols-5">
        <div className="xl:col-span-3">
          <Card title="Users by current risk">
            {users.length === 0 ? (
              <p className="p-4 text-sm text-slate-400">No questions yet.</p>
            ) : (
              <table className="w-full text-sm">
                <thead className="text-left text-xs text-slate-400">
                  <tr className="border-b border-slate-800">
                    <th className="px-4 py-2 font-medium">User</th>
                    <th className="px-2 py-2 font-medium">Risk now</th>
                    <th className="hidden px-2 py-2 font-medium sm:table-cell">Peak</th>
                    <th className="px-2 py-2 font-medium">Policy</th>
                    <th className="hidden px-2 py-2 font-medium md:table-cell">Last seen</th>
                    <th className="w-8" />
                  </tr>
                </thead>
                <tbody>
                  {users.map((u) => {
                    return (
                      <tr key={u.key} className="border-b border-slate-800/60 last:border-0 hover:bg-slate-800/50">
                        <td className="max-w-[16rem] px-4 py-2.5">
                          <div className="truncate text-slate-100" title={u.who}>{u.who}</div>
                          <div className="text-xs text-slate-500">{u.role} · {u.count} questions</div>
                        </td>
                        <td className={`px-2 py-2.5 font-mono ${riskTone(u.latest.risk_score)}`}>{u.latest.risk_score.toFixed(2)}</td>
                        <td className={`hidden px-2 py-2.5 font-mono sm:table-cell ${riskTone(u.peak)}`}>{u.peak.toFixed(2)}</td>
                        <td className="px-2 py-2.5"><ModeBadge mode={u.latest.behavioral_mode} /></td>
                        <td className="hidden px-2 py-2.5 text-xs text-slate-400 md:table-cell">{timeAgo(u.latest.timestamp)}</td>
                        <td className="pr-3">
                          {u.userId && (
                            <Link to={`/admin/users/${encodeURIComponent(u.userId)}`} className="block p-1 text-slate-500 hover:text-blue-400" aria-label={`Open ${u.who}`}>
                              <ChevronRight className="h-4 w-4" />
                            </Link>
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            )}
          </Card>
        </div>

        <div className="xl:col-span-2">
          <Card title="Escalations" action={<span className="text-xs text-slate-500">masked or blocked answers</span>}>
            {escalations.length === 0 ? (
              <p className="p-4 text-sm text-slate-400">Nothing suspicious in the feed.</p>
            ) : (
              <ul className="divide-y divide-slate-800/60">
                {escalations.map((q) => (
                  <li key={q.id} className="px-4 py-3">
                    <div className="mb-1 flex items-center justify-between gap-2">
                      <span className="truncate text-xs text-slate-300" title={whoOf(q)}>{whoOf(q)}</span>
                      <ModeBadge mode={q.behavioral_mode} />
                    </div>
                    <p className="line-clamp-2 text-sm text-slate-200">“{q.query}”</p>
                    <div className="mt-1 text-xs text-slate-500">risk {q.risk_score.toFixed(2)} · {timeAgo(q.timestamp)}</div>
                  </li>
                ))}
              </ul>
            )}
          </Card>
        </div>
      </div>
    </div>
  );
}
