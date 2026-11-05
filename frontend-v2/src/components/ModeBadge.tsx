import clsx from 'clsx';
import type { Exposure, ResponseMode, SignalValues } from '../api';

// One place that says how each policy mode looks, used on every page.
const MODE_STYLES: Record<ResponseMode, { label: string; tone: string; dot: string }> = {
  ALLOW: { label: 'Normal access', tone: 'text-emerald-400 border-emerald-900 bg-emerald-950/40', dot: 'bg-emerald-400' },
  MASK: { label: 'Masking names', tone: 'text-amber-400 border-amber-900 bg-amber-950/40', dot: 'bg-amber-400' },
  RESTRICT: { label: 'Restricted', tone: 'text-amber-400 border-amber-900 bg-amber-950/40', dot: 'bg-amber-400' },
  BLOCK: { label: 'Blocked', tone: 'text-red-400 border-red-900 bg-red-950/40', dot: 'bg-red-400' },
};

const FALLBACK = { label: 'Unknown', tone: 'text-slate-400 border-slate-700 bg-slate-900', dot: 'bg-slate-400' };

const modeStyle = (mode: string) => MODE_STYLES[mode as ResponseMode] ?? FALLBACK;

export function ModeBadge({ mode, className }: { mode: string; className?: string }) {
  const style = modeStyle(mode);
  return (
    <span className={clsx('inline-flex items-center gap-1.5 rounded border px-2 py-0.5 text-xs font-mono whitespace-nowrap', style.tone, className)}>
      <span className={clsx('h-1.5 w-1.5 rounded-full', style.dot)} aria-hidden />
      {style.label}
    </span>
  );
}

const PII_WORDS: Record<string, string> = { ssn: 'SSN', card: 'Card no.', dob: 'Birth date' };

// Sensitivity labels of what one answer touched, e.g. "3 Legal · 1 HR · SSN".
// Phone numbers and street addresses are left out: they are mostly office details.
export function SensitivityBadges({ exposure }: { exposure?: Exposure | null }) {
  const labels = Object.entries(exposure?.labels ?? {}).sort((a, b) => b[1] - a[1]);
  const pii = Object.keys(exposure?.pii ?? {}).filter((k) => k in PII_WORDS);
  if (!labels.length && !pii.length) return null;
  return (
    <>
      {labels.map(([label, n]) => (
        <span key={label} className="rounded border border-amber-900 bg-amber-950/40 px-2 py-0.5 text-xs font-mono text-amber-400"
          title={`${n} retrieved email${n === 1 ? '' : 's'} labelled ${label}`}>
          {n} {label}
        </span>
      ))}
      {pii.map((k) => (
        <span key={k} className="rounded border border-red-900 bg-red-950/40 px-2 py-0.5 text-xs font-mono text-red-400"
          title="Retrieved text contains this kind of personal data">
          {PII_WORDS[k]}
        </span>
      ))}
    </>
  );
}

const SIGNAL_WORDS: Record<keyof SignalValues, string> = {
  semantic_focus: 'staying on one narrow topic',
  temporal_frequency: 'asking many questions quickly',
  entity_focus: 'repeatedly targeting the same person',
  graph_footprint: 'pulling a wide slice of the graph',
  sensitivity_exposure: 'pulling sensitive (legal, HR, personal) data, especially about senior people',
};

// Plain-language reason for a risk score: which behaviour contributed most.
export function explainSignals(signals: SignalValues): string {
  const [key, value] = (Object.entries(signals) as [keyof SignalValues, number][])
    .sort((a, b) => b[1] - a[1])[0];
  if (value < 0.2) return 'No unusual behaviour so far.';
  return `Mostly from ${SIGNAL_WORDS[key]} (${value.toFixed(2)}).`;
}
