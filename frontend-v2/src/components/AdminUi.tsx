import type { ReactNode } from 'react';
import { RefreshCcw } from 'lucide-react';
import { animate, motion, useMotionValue, useTransform } from 'motion/react';
import { useEffect } from 'react';

// Numbers glide to their new value instead of jumping.
function CountUp({ value }: { value: number }) {
  const mv = useMotionValue(0);
  const text = useTransform(mv, (v) => Math.round(v).toLocaleString());
  useEffect(() => {
    const controls = animate(mv, value, { duration: 0.9, ease: [0.22, 1, 0.36, 1] });
    return () => controls.stop();
  }, [value, mv]);
  return <motion.span>{text}</motion.span>;
}

export function PageHeader({ title, subtitle, loading, onRefresh, children }: {
  title: string;
  subtitle?: ReactNode;
  loading?: boolean;
  onRefresh?: () => void;
  children?: ReactNode;
}) {
  return (
    <header className="flex flex-wrap items-end justify-between gap-3 border-b border-slate-800 px-6 py-5">
      <div className="min-w-0">
        <h1 className="font-display text-3xl text-slate-50">{title}</h1>
        {subtitle && <p className="mt-0.5 text-sm text-slate-400">{subtitle}</p>}
      </div>
      <div className="flex flex-wrap items-center gap-2">
        {children}
        {onRefresh && (
          <button
            onClick={onRefresh}
            className="flex items-center gap-2 rounded-md border border-slate-700 px-3 py-1.5 text-xs text-slate-300 hover:bg-slate-800"
          >
            <RefreshCcw className={`h-3.5 w-3.5 ${loading ? 'animate-spin' : ''}`} /> Refresh
          </button>
        )}
      </div>
    </header>
  );
}

export function StatTile({ label, value, tone = 'text-slate-50', hint }: { label: string; value: ReactNode; tone?: string; hint?: string }) {
  return (
    <motion.div
      className="rounded-xl border border-slate-800 bg-slate-900/70 p-4 backdrop-blur transition-colors hover:border-slate-700"
      title={hint}
      initial={{ opacity: 0, y: 14 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, ease: [0.22, 1, 0.36, 1] }}
    >
      <div className="text-sm text-slate-400">{label}</div>
      <div className={`font-display mt-1 text-4xl ${tone}`}>{typeof value === 'number' ? <CountUp value={value} /> : value}</div>
    </motion.div>
  );
}

export function Card({ title, action, children }: { title: string; action?: ReactNode; children: ReactNode }) {
  return (
    <section className="flex min-h-0 flex-col rounded-xl border border-slate-800 bg-slate-900/70">
      <div className="flex items-center justify-between gap-2 border-b border-slate-800 px-4 py-3">
        <h2 className="text-sm font-semibold text-slate-100">{title}</h2>
        {action}
      </div>
      <div className="min-h-0 flex-1 overflow-auto">{children}</div>
    </section>
  );
}

export function ErrorNote({ text }: { text: string | null }) {
  return text ? <div className="mx-6 mt-4 rounded-md border border-red-900/60 bg-red-950/20 px-4 py-2 text-sm text-red-300" role="alert">{text}</div> : null;
}

export function timeAgo(iso: string): string {
  const s = Math.max(0, (Date.now() - new Date(iso).getTime()) / 1000);
  if (s < 60) return `${Math.round(s)}s ago`;
  if (s < 3600) return `${Math.round(s / 60)}m ago`;
  if (s < 86400) return `${Math.round(s / 3600)}h ago`;
  return new Date(iso).toLocaleDateString();
}
