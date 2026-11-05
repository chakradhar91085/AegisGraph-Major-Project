import { useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { SignedIn, SignedOut, SignInButton } from '@clerk/clerk-react';
import { motion, useReducedMotion } from 'motion/react';
import { ArrowRight, ShieldBan } from 'lucide-react';
import clsx from 'clsx';
import { RISK_BANDS, type ResponseMode } from '../api';
import { ModeBadge } from '../components/ModeBadge';
import { RiskMeter } from '../components/RiskMeter';

const EASE = [0.22, 1, 0.36, 1] as const;

/* ───────────────────────── demo content ───────────────────────── */

interface Scenario {
  id: string;
  label: string;
  mode: ResponseMode;
  risk: number;
  asked: string;
  reason: string;
  answer: string;
}

// Sample output, written for the page; the real app produces these from live data.
const SCENARIOS: Scenario[] = [
  {
    id: 'normal', label: 'Asking normally', mode: 'ALLOW', risk: 0.14,
    asked: 'Who is Christopher Calger?',
    reason: 'One topic, a few questions, nothing unusual.',
    answer: 'Christopher Calger appears in 14 emails in the archive, mostly about trading schedules. He wrote to Kenneth Lay twice about a deal timeline.',
  },
  {
    id: 'probing', label: 'Digging into one person', mode: 'MASK', risk: 0.48,
    asked: 'And who did he email most?',
    reason: 'Ninth question about the same person in four minutes.',
    answer: '[REDACTED_NAME] wrote most often to [REDACTED_NAME] and [REDACTED_NAME], mainly about deal timelines. Names are withheld at this risk level.',
  },
  {
    id: 'harvesting', label: 'Pulling everything', mode: 'BLOCK', risk: 0.86,
    asked: 'List every employee with their email address.',
    reason: 'Wide sweep of the graph, sensitive records, rapid fire.',
    answer: 'Blocked by security policy. Your recent questions look like bulk collection, so this answer was not retrieved.',
  },
];

/* ───────────────────────── graph backdrop ───────────────────────── */

// Drifting network. Nodes turn into redaction bars at MASK and the links die at BLOCK.
function HeroGraph({ mode }: { mode: ResponseMode }) {
  const canvas = useRef<HTMLCanvasElement>(null);
  const modeRef = useRef(mode);
  const reduce = useReducedMotion();
  useEffect(() => { modeRef.current = mode; }, [mode]);

  useEffect(() => {
    const el = canvas.current;
    const ctx = el?.getContext('2d');
    if (!el || !ctx) return;
    let w = 0, h = 0, raf = 0, frame = 0;
    let color = '134,163,214';
    let mask = 0, dead = 0; // eased 0..1 levels for the current mode
    const nodes = Array.from({ length: 64 }, (_, i) => ({
      x: Math.random(), y: Math.random(), vx: (Math.random() - 0.5) * 0.00006, vy: (Math.random() - 0.5) * 0.00006,
      r: 1.6 + Math.random() * 2.2, hidden: i % 3 === 0,
    }));

    const resize = () => {
      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      w = el.clientWidth; h = el.clientHeight;
      el.width = w * dpr; el.height = h * dpr;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    };
    const hex = (c: string) => { const n = parseInt(c.replace('#', ''), 16); return `${n >> 16},${(n >> 8) & 255},${n & 255}`; };

    const draw = () => {
      const m = modeRef.current;
      mask += ((m === 'ALLOW' ? 0 : 1) - mask) * 0.05;
      dead += ((m === 'BLOCK' ? 1 : 0) - dead) * 0.05;
      if (frame++ % 20 === 0) color = hex(getComputedStyle(document.documentElement).getPropertyValue('--accent').trim() || '#86a3d6');
      ctx.clearRect(0, 0, w, h);
      const speed = 1 - dead * 0.85;
      for (const n of nodes) {
        if (!reduce) { n.x += n.vx * 16 * speed; n.y += n.vy * 16 * speed; }
        if (n.x < 0 || n.x > 1) n.vx *= -1;
        if (n.y < 0 || n.y > 1) n.vy *= -1;
      }
      const reach = Math.min(w, 900) * 0.17;
      for (let i = 0; i < nodes.length; i++) {
        for (let j = i + 1; j < nodes.length; j++) {
          const dx = (nodes[i].x - nodes[j].x) * w, dy = (nodes[i].y - nodes[j].y) * h;
          const d = Math.hypot(dx, dy);
          if (d < reach) {
            ctx.strokeStyle = `rgba(${color},${(1 - d / reach) * 0.32 * (1 - dead * 0.9)})`;
            ctx.beginPath(); ctx.moveTo(nodes[i].x * w, nodes[i].y * h); ctx.lineTo(nodes[j].x * w, nodes[j].y * h); ctx.stroke();
          }
        }
      }
      for (const n of nodes) {
        const x = n.x * w, y = n.y * h;
        if (n.hidden && mask > 0.05) {
          ctx.fillStyle = `rgba(238,242,246,${0.85 * mask})`;
          ctx.fillRect(x - 9 * mask, y - 3, 18 * mask, 6);
        }
        ctx.fillStyle = `rgba(${color},${(n.hidden ? 1 - mask : 1) * (0.85 - dead * 0.6)})`;
        ctx.beginPath(); ctx.arc(x, y, n.r, 0, Math.PI * 2); ctx.fill();
      }
      if (!reduce) raf = requestAnimationFrame(draw);
    };

    resize();
    draw();
    window.addEventListener('resize', resize);
    return () => { cancelAnimationFrame(raf); window.removeEventListener('resize', resize); };
  }, [reduce]);

  return <canvas ref={canvas} className="absolute inset-0 h-full w-full opacity-70 [mask-image:linear-gradient(to_bottom,black_55%,transparent)]" aria-hidden />;
}

/* ───────────────────────── live demo card ───────────────────────── */

function renderAnswer(text: string) {
  return text.split(/(\[REDACTED_[A-Z]+\])/g).map((part, i) =>
    part.startsWith('[REDACTED_')
      ? <span key={i} className="redaction" style={{ animationDelay: `${0.15 + i * 0.07}s` }}>{part}</span>
      : part,
  );
}

function RiskDemo({ index, onPick }: { index: number; onPick: (i: number) => void }) {
  const s = SCENARIOS[index];
  return (
    <div className="w-full max-w-[34rem] rounded-2xl border border-slate-700/70 bg-slate-900/80 shadow-[0_30px_80px_-30px_rgba(0,0,0,0.8)] backdrop-blur-xl" data-ui>
      <div role="tablist" aria-label="Example behaviours" className="flex gap-1 p-1.5">
        {SCENARIOS.map((sc, i) => (
          <button
            key={sc.id}
            role="tab"
            aria-selected={i === index}
            onClick={() => onPick(i)}
            className={clsx('relative flex-1 rounded-xl px-2 py-2 text-sm font-medium transition-colors', i === index ? 'text-slate-950' : 'text-slate-400 hover:text-slate-50')}
          >
            {i === index && <motion.span layoutId="demo-tab" className="absolute inset-0 rounded-xl bg-blue-500" transition={{ type: 'spring', stiffness: 400, damping: 34 }} />}
            <span className="relative">{sc.label}</span>
          </button>
        ))}
      </div>

      <div className="space-y-5 p-5 pt-4">
        <div className="flex items-center gap-4">
          <RiskMeter risk={s.risk} className="flex-1" />
          <span className="font-display w-12 text-2xl text-slate-50">{s.risk.toFixed(2)}</span>
          <ModeBadge mode={s.mode} />
        </div>

        <motion.div key={s.id} initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.45, ease: EASE }} className="space-y-4">
          <p className="ml-auto w-fit max-w-[85%] rounded-2xl rounded-br-md bg-slate-800 px-4 py-2.5 text-sm text-slate-100">{s.asked}</p>
          <div className={clsx('rounded-2xl border px-4 py-3.5 text-[15px] leading-relaxed', s.mode === 'BLOCK' ? 'border-red-900/60 bg-red-950/30 text-red-300' : 'border-slate-800 bg-slate-950/50 text-slate-100')}>
            {s.mode === 'BLOCK' && <ShieldBan className="mb-1.5 h-4 w-4 text-red-400" aria-hidden />}
            {renderAnswer(s.answer)}
          </div>
          <p className="text-sm text-slate-400">Why: {s.reason}</p>
        </motion.div>
        <p className="text-xs text-slate-500">Sample output. The real answers come from the Enron graph.</p>
      </div>
    </div>
  );
}

/* ───────────────────────── page sections ───────────────────────── */

function CtaButton({ children, large }: { children: React.ReactNode; large?: boolean }) {
  const cls = clsx('btn-sheen group inline-flex items-center gap-2 rounded-xl bg-blue-600 font-semibold text-white transition-transform hover:-translate-y-0.5 active:translate-y-0', large ? 'px-7 py-4 text-base' : 'px-5 py-3 text-sm');
  const inner = <>{children}<ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-1" /></>;
  return (
    <>
      <SignedOut><SignInButton mode="modal" forceRedirectUrl="/app"><button className={cls}>{inner}</button></SignInButton></SignedOut>
      <SignedIn><Link to="/app" className={cls}>{inner}</Link></SignedIn>
    </>
  );
}

function Nav() {
  return (
    <header className="fixed inset-x-0 top-0 z-30 border-b border-white/5 bg-slate-950/55 backdrop-blur-xl">
      <div className="mx-auto flex h-16 max-w-[1280px] items-center justify-between px-6">
        <a href="#top" className="font-display text-xl text-slate-50">AegisGraph</a>
        <nav className="hidden items-center gap-8 text-sm text-slate-300 md:flex">
          <a href="#scoring" className="transition-colors hover:text-slate-50">How it scores</a>
          <a href="#levels" className="transition-colors hover:text-slate-50">What changes</a>
          <a href="#auditors" className="transition-colors hover:text-slate-50">For auditors</a>
        </nav>
        <CtaButton>Open workspace</CtaButton>
      </div>
    </header>
  );
}

const HEADLINE = 'The more you dig, the less it shows.'.split(' ');

function Hero({ index, onPick }: { index: number; onPick: (i: number) => void }) {
  const mode = SCENARIOS[index].mode;
  return (
    <section id="top" className="relative flex min-h-[100svh] items-center overflow-hidden pt-16">
      <HeroGraph mode={mode} />
      <div className="relative z-10 mx-auto grid w-full max-w-[1280px] items-center gap-12 px-6 py-16 lg:grid-cols-[1.05fr_0.95fr]">
        <div>
          <h1 className="font-display text-[clamp(2.7rem,6.4vw,5.6rem)] leading-[1.02] text-slate-50">
            {HEADLINE.map((word, i) => (
              <span key={i} className="mr-[0.25em] inline-block overflow-hidden pb-[0.12em] align-bottom">
                <motion.span className="inline-block" initial={{ y: '110%' }} animate={{ y: 0 }} transition={{ delay: 0.1 + i * 0.07, duration: 0.8, ease: EASE }}>{word}</motion.span>
              </span>
            ))}
          </h1>
          <motion.p initial={{ opacity: 0, y: 14 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.75, duration: 0.6, ease: EASE }} className="mt-6 max-w-[34rem] text-lg leading-relaxed text-slate-300">
            AegisGraph answers questions about the Enron email archive and watches how each person asks. Normal questions get full answers. Digging gets names blacked out. Harvesting gets blocked.
          </motion.p>
          <motion.div initial={{ opacity: 0, y: 14 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.9, duration: 0.6, ease: EASE }} className="mt-9 flex flex-wrap items-center gap-4">
            <CtaButton large>Try the workspace</CtaButton>
            <a href="#scoring" className="px-2 py-3 text-sm font-medium text-slate-300 underline-offset-4 transition-colors hover:text-slate-50 hover:underline">See how the score works</a>
          </motion.div>
        </div>
        <motion.div initial={{ opacity: 0, y: 30 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.5, duration: 0.9, ease: EASE }} className="flex justify-center lg:justify-end">
          <RiskDemo index={index} onPick={onPick} />
        </motion.div>
      </div>
    </section>
  );
}

const SIGNALS = [
  { name: 'Topic focus', text: 'Are the questions circling one narrow topic instead of exploring?', value: 0.62 },
  { name: 'Speed', text: 'How many questions arrive, and how fast, compared with recent activity.', value: 0.48 },
  { name: 'Person focus', text: 'Is one person the target of question after question?', value: 0.81 },
  { name: 'Graph footprint', text: 'How wide a slice of the knowledge graph the answers pulled in.', value: 0.37 },
  { name: 'Sensitive data', text: 'Legal, HR or personal records, weighted up when the people are senior.', value: 0.55 },
];

function Scoring() {
  return (
    <section id="scoring" className="mx-auto grid max-w-[1280px] gap-14 px-6 py-32 lg:grid-cols-[0.8fr_1.2fr]">
      <div className="lg:sticky lg:top-28 lg:self-start">
        <h2 className="font-display text-[clamp(2rem,4.4vw,3.6rem)] leading-[1.05] text-slate-50">Five habits add up to one score.</h2>
        <p className="mt-5 max-w-md text-lg leading-relaxed text-slate-300">
          Each question is measured on five behaviours. They blend into a single risk score that is remembered for the user, fades while they are idle, and decides what the next answer may contain.
        </p>
      </div>
      <ul className="divide-y divide-slate-800">
        {SIGNALS.map((s, i) => (
          <motion.li key={s.name} initial={{ opacity: 0, y: 24 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true, margin: '-80px' }} transition={{ duration: 0.6, delay: i * 0.05, ease: EASE }} className="grid items-center gap-x-8 gap-y-3 py-7 sm:grid-cols-[1fr_14rem]">
            <div>
              <h3 className="font-display text-2xl text-slate-50">{s.name}</h3>
              <p className="mt-1 max-w-md text-slate-400">{s.text}</p>
            </div>
            <div className="flex items-center gap-3" aria-label={`${s.name}: example reading ${s.value}`}>
              <div className="h-2 flex-1 overflow-hidden rounded-full bg-slate-800">
                <motion.div className="h-full rounded-full bg-blue-500" initial={{ width: 0 }} whileInView={{ width: `${s.value * 100}%` }} viewport={{ once: true }} transition={{ duration: 1.1, delay: 0.2 + i * 0.08, ease: EASE }} />
              </div>
              <span className="w-10 text-right text-sm text-slate-300">{s.value.toFixed(2)}</span>
            </div>
          </motion.li>
        ))}
      </ul>
    </section>
  );
}

const LEVELS = [
  { range: `Below ${RISK_BANDS.medium}`, title: 'Full answers', text: 'Names, emails and detail are shown as retrieved.', tone: 'bg-emerald-500', width: RISK_BANDS.medium },
  { range: `${RISK_BANDS.medium} to ${RISK_BANDS.high}`, title: 'Names blacked out', text: 'The answer still helps, but people and contact details are withheld.', tone: 'bg-amber-500', width: RISK_BANDS.high - RISK_BANDS.medium },
  { range: `Above ${RISK_BANDS.high}`, title: 'Blocked', text: 'Nothing is retrieved. The auditor is alerted.', tone: 'bg-red-500', width: 1 - RISK_BANDS.high },
];

function Levels() {
  return (
    <section id="levels" className="border-y border-slate-800 bg-slate-900/40 py-32">
      <div className="mx-auto max-w-[1280px] px-6">
        <h2 className="font-display max-w-3xl text-[clamp(2rem,4.4vw,3.6rem)] leading-[1.05] text-slate-50">The score decides what comes back.</h2>
        <div className="mt-14 flex h-3 gap-1">
          {LEVELS.map((l, i) => (
            <motion.div key={l.title} className={clsx('h-full origin-left rounded-full', l.tone)} style={{ width: `${l.width * 100}%` }} initial={{ scaleX: 0 }} whileInView={{ scaleX: 1 }} viewport={{ once: true }} transition={{ duration: 0.9, delay: i * 0.2, ease: EASE }} />
          ))}
        </div>
        <div className="mt-6 flex">
          {LEVELS.map((l, i) => (
            <motion.div key={l.title} style={{ width: `${l.width * 100}%` }} className="min-w-0 pr-6" initial={{ opacity: 0, y: 18 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }} transition={{ duration: 0.6, delay: 0.3 + i * 0.2, ease: EASE }}>
              <div className="text-sm text-slate-400">{l.range}</div>
              <h3 className="font-display mt-1 text-2xl text-slate-50">{l.title}</h3>
              <p className="mt-2 hidden text-slate-400 sm:block">{l.text}</p>
            </motion.div>
          ))}
        </div>
        <ul className="mt-6 space-y-4 sm:hidden">
          {LEVELS.map((l) => <li key={l.title} className="text-slate-400"><span className="text-slate-100">{l.title}.</span> {l.text}</li>)}
        </ul>
      </div>
    </section>
  );
}

const SAMPLE_USERS: { who: string; risk: number; mode: ResponseMode; seen: string }[] = [
  { who: 'analyst-07', risk: 0.86, mode: 'BLOCK', seen: '2m ago' },
  { who: 'analyst-03', risk: 0.48, mode: 'MASK', seen: '9m ago' },
  { who: 'analyst-11', risk: 0.21, mode: 'ALLOW', seen: '14m ago' },
  { who: 'analyst-02', risk: 0.09, mode: 'ALLOW', seen: '1h ago' },
];

function Auditors() {
  return (
    <section id="auditors" className="mx-auto grid max-w-[1280px] items-center gap-14 px-6 py-32 lg:grid-cols-2">
      <div>
        <h2 className="font-display text-[clamp(2rem,4.4vw,3.6rem)] leading-[1.05] text-slate-50">Auditors watch every user, live.</h2>
        <p className="mt-5 max-w-md text-lg leading-relaxed text-slate-300">
          One page lists everyone by current risk, with a timeline per user and a filterable log of every question asked. When someone is masked or blocked, an alert goes out to Telegram and email.
        </p>
      </div>
      <motion.div initial={{ opacity: 0, y: 30 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true, margin: '-80px' }} transition={{ duration: 0.8, ease: EASE }} className="overflow-hidden rounded-2xl border border-slate-700/70 bg-slate-900/80" data-ui>
        <table className="w-full text-sm">
          <thead className="text-left text-slate-400">
            <tr className="border-b border-slate-800"><th className="px-5 py-3 font-medium">User</th><th className="px-2 py-3 font-medium">Risk</th><th className="px-2 py-3 font-medium">Policy</th><th className="hidden px-5 py-3 font-medium sm:table-cell">Last seen</th></tr>
          </thead>
          <tbody>
            {SAMPLE_USERS.map((u, i) => (
              <motion.tr key={u.who} className="border-b border-slate-800/60 last:border-0" initial={{ opacity: 0, x: -16 }} whileInView={{ opacity: 1, x: 0 }} viewport={{ once: true }} transition={{ delay: 0.25 + i * 0.12, duration: 0.5, ease: EASE }}>
                <td className="px-5 py-3.5 text-slate-100">{u.who}</td>
                <td className="px-2 py-3.5"><div className="flex items-center gap-3"><RiskMeter risk={u.risk} className="w-20" /><span className="w-9 text-slate-300">{u.risk.toFixed(2)}</span></div></td>
                <td className="px-2 py-3.5"><ModeBadge mode={u.mode} /></td>
                <td className="hidden px-5 py-3.5 text-slate-400 sm:table-cell">{u.seen}</td>
              </motion.tr>
            ))}
          </tbody>
        </table>
        <p className="border-t border-slate-800 px-5 py-3 text-xs text-slate-500">Sample data.</p>
      </motion.div>
    </section>
  );
}

function Closing() {
  return (
    <section className="relative overflow-hidden border-t border-slate-800 py-36 text-center">
      <div className="mx-auto max-w-3xl px-6">
        <motion.h2 initial={{ opacity: 0, y: 24 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }} transition={{ duration: 0.8, ease: EASE }} className="font-display text-[clamp(2.2rem,5.4vw,4.6rem)] leading-[1.03] text-slate-50">
          Ask it something. Then ask it too much.
        </motion.h2>
        <p className="mx-auto mt-5 max-w-xl text-lg text-slate-300">Sign in, ask a few ordinary questions, then press harder. Watch your risk score climb and the policy change.</p>
        <div className="mt-10 flex justify-center"><CtaButton large>Open the workspace</CtaButton></div>
      </div>
    </section>
  );
}

export function LandingPage() {
  const [index, setIndex] = useState(0);
  const [touched, setTouched] = useState(false);

  // The whole page takes the demo's mode colour. Cycles by itself until someone picks a tab.
  useEffect(() => {
    document.documentElement.dataset.mode = SCENARIOS[index].mode;
    return () => { delete document.documentElement.dataset.mode; };
  }, [index]);
  useEffect(() => {
    if (touched) return;
    const t = setInterval(() => setIndex((i) => (i + 1) % SCENARIOS.length), 5200);
    return () => clearInterval(t);
  }, [touched]);

  return (
    <main className="min-h-screen overflow-x-clip">
      <Nav />
      <Hero index={index} onPick={(i) => { setTouched(true); setIndex(i); }} />
      <Scoring />
      <Levels />
      <Auditors />
      <Closing />
      <footer className="border-t border-slate-800 px-6 py-8 text-center text-sm text-slate-500">
        AegisGraph is a major project at CMR Institute of Technology. Built with Neo4j, FastAPI and React.
      </footer>
    </main>
  );
}
