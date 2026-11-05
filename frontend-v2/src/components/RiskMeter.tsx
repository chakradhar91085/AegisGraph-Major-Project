import { motion } from 'motion/react';
import { RISK_BANDS } from '../api';

// A 0..1 risk bar with ticks where the policy changes (mask at 0.35, block at 0.65).
// The fill takes the page accent, which itself follows the mode, so the bar, badge and
// glow always agree.
export function RiskMeter({ risk, className = '' }: { risk: number; className?: string }) {
  const pct = Math.min(Math.max(risk, 0), 1) * 100;
  return (
    <div className={`relative h-2 rounded-full bg-slate-800 ${className}`} role="meter" aria-valuemin={0} aria-valuemax={1} aria-valuenow={risk} aria-label="Risk score">
      <motion.div
        className="h-full rounded-full bg-[var(--signal)] transition-colors duration-500"
        initial={false}
        animate={{ width: `${pct}%` }}
        transition={{ type: 'spring', stiffness: 120, damping: 20 }}
      />
      {[RISK_BANDS.medium, RISK_BANDS.high].map((b) => (
        <span key={b} className="absolute top-[-3px] h-[14px] w-px bg-slate-500/70" style={{ left: `${b * 100}%` }} aria-hidden />
      ))}
    </div>
  );
}
