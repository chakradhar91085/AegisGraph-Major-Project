import { ChevronRight, Database } from 'lucide-react';
import clsx from 'clsx';
import { riskLevelOf, type RetrievedRecord, type TelemetryEvent } from '../api';
import { FormattedText } from './FormattedText';
import { ModeBadge } from './ModeBadge';

const RISK_STYLE = {
  LOW: 'border-green-900 bg-green-950/40 text-green-500',
  MEDIUM: 'border-amber-900 bg-amber-950/40 text-amber-400',
  HIGH: 'border-red-900 bg-red-950/40 text-red-400',
};

// Nothing is retrieved when blocked, so all of this is truly withheld.
const WITHHELD_WHEN_BLOCKED = ['names', 'emails', 'phone numbers', 'ID numbers', 'subjects', 'email text'];

const HIDDEN_WORDS: Record<string, [string, string]> = {
  names: ['name', 'names'],
  emails: ['email address', 'email addresses'],
  phones: ['phone number', 'phone numbers'],
  ids: ['ID number', 'ID numbers'],
  amounts: ['amount', 'amounts'],
};

function why(t: TelemetryEvent): string | null {
  // The rule's reason names what was asked for; otherwise the user's recent behaviour decided.
  if (t.response_mode === 'BLOCK') {
    return `${t.reason ?? 'Recent questions pushed this user past the block limit'}. Nothing was retrieved, so the AI saw no records.`;
  }
  if (t.response_mode === 'MASK') {
    return `${t.reason ?? 'Recent questions raised this user’s risk'}. Identifying details were hidden in code before the AI read the records.`;
  }
  return null;
}

// What security did for one answer: how risky it was judged, what happened and why.
export function SecurityCard({ telemetry: t }: { telemetry: TelemetryEvent }) {
  // The score that decided this answer, not the one this answer then produced.
  const risk = t.policy?.risk_score ?? t.smoothed_risk;
  const level = riskLevelOf(risk);
  const hidden = Object.entries(t.exposure?.hidden ?? {}).filter(([, n]) => n > 0);
  const quarantined = t.exposure?.quarantined ?? 0;
  const note = why(t);

  return (
    <div className="mb-3">
      <div className="flex flex-wrap items-center gap-2 text-xs">
        <span className={clsx('rounded border px-2 py-0.5 font-mono font-semibold', RISK_STYLE[level])}>
          {level} RISK · {risk.toFixed(2)}
        </span>
        <ModeBadge mode={t.response_mode} />
        <span className="rounded border border-slate-800 px-2 py-0.5 font-mono text-slate-400">Role: {t.role}</span>
      </div>

      {(t.response_mode === 'BLOCK' || hidden.length > 0 || quarantined > 0) && (
        <div className="mt-2 flex flex-wrap gap-1.5 text-xs">
          {t.response_mode === 'BLOCK' && WITHHELD_WHEN_BLOCKED.map((item) => (
            <span key={item} className="rounded border border-red-900/60 px-2 py-0.5 font-mono text-red-400">Withheld: {item}</span>
          ))}
          {hidden.map(([kind, n]) => {
            const [one, many] = HIDDEN_WORDS[kind] ?? [kind, kind];
            return (
              <span key={kind} className="rounded border border-amber-900 px-2 py-0.5 font-mono text-amber-400">
                Hidden: {n} {n === 1 ? one : many}
              </span>
            );
          })}
          {quarantined > 0 && (
            <span className="rounded border border-red-900/60 px-2 py-0.5 font-mono text-red-400"
              title="These retrieved emails contained text that looked like instructions to the AI">
              Withheld: {quarantined} suspicious email{quarantined === 1 ? '' : 's'}
            </span>
          )}
        </div>
      )}

      {note && <p className="mt-2 text-xs leading-relaxed text-slate-400">{note}</p>}
    </div>
  );
}

// The records behind the answer. In MASK mode they arrive already masked by the server.
export function RetrievedRecords({ records, masked }: { records: RetrievedRecord[]; masked: boolean }) {
  if (!records.length) return null;
  return (
    <details className="group mb-3 rounded-lg border border-slate-800 text-xs">
      <summary className="flex cursor-pointer select-none items-center gap-2 px-3 py-2 text-slate-300 hover:text-slate-50">
        <ChevronRight className="h-3.5 w-3.5 transition-transform group-open:rotate-90" />
        <Database className="h-3.5 w-3.5" />
        Retrieved from Neo4j · {records.length} record{records.length === 1 ? '' : 's'}{masked ? ' · masked' : ''}
      </summary>
      <ul className="max-h-72 divide-y divide-slate-800 overflow-y-auto border-t border-slate-800">
        {records.map((record, i) => (
          <li key={i} className="px-3 py-2.5">
            <div className="break-words text-sm text-slate-100"><FormattedText text={record.title} /></div>
            {(record.date || record.labels.length > 0) && (
              <div className="mt-1 flex flex-wrap items-center gap-1.5 font-mono text-slate-500">
                {record.date && <span>{record.date}</span>}
                {record.labels.map((label) => (
                  <span key={label} className="rounded border border-amber-900 px-1.5 text-amber-400">{label}</span>
                ))}
              </div>
            )}
            {record.fields.length > 0 && (
              <dl className="mt-1 space-y-0.5">
                {record.fields.map((field) => (
                  <div key={field.name} className="flex gap-2">
                    <dt className="shrink-0 text-slate-500">{field.name}</dt>
                    <dd className="min-w-0 break-words text-slate-300"><FormattedText text={field.value} /></dd>
                  </div>
                ))}
              </dl>
            )}
            {record.snippet && (
              <div className="mt-1 whitespace-pre-wrap break-words leading-relaxed text-slate-400"><FormattedText text={record.snippet} /></div>
            )}
          </li>
        ))}
      </ul>
    </details>
  );
}
