import { useState, type ReactNode } from 'react';
import { NavLink, Link, Outlet } from 'react-router-dom';
import { UserButton, useAuth } from '@clerk/clerk-react';
import { ArrowLeft, Copy, Menu, X, type LucideIcon } from 'lucide-react';
import clsx from 'clsx';

export interface NavItem {
  to: string;
  label: string;
  icon: LucideIcon;
  end?: boolean;
}

interface ShellProps {
  badge?: string;
  actions?: ReactNode;
  sections: { title: string; items: NavItem[] }[];
}

function Logo() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.25" strokeLinecap="round" strokeLinejoin="round" className="h-5 w-5 text-blue-500" aria-hidden>
      <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
      <circle cx="12" cy="9" r="1.5" fill="currentColor" />
      <circle cx="8.5" cy="14" r="1.5" fill="currentColor" />
      <circle cx="15.5" cy="14" r="1.5" fill="currentColor" />
      <path d="M12 9l-3.5 5M12 9l3.5 5M8.5 14h7" strokeWidth="1" strokeDasharray="1 2" opacity="0.8" />
    </svg>
  );
}

// The Clerk user id is what goes into SECURITY_USER_ROLES, so keep it one click away.
function CopyUserId() {
  const { userId } = useAuth();
  const [copied, setCopied] = useState(false);
  if (!userId) return null;
  return (
    <button
      onClick={() => navigator.clipboard.writeText(userId).then(() => setCopied(true)).catch(() => {})}
      className="flex w-full items-center gap-2 rounded px-3 py-1.5 text-left text-xs font-mono text-slate-400 hover:bg-slate-800 hover:text-slate-200"
      title={userId}
    >
      <Copy className="h-3 w-3 shrink-0" />
      <span className="truncate">{copied ? 'Copied your user id' : 'Copy my user id'}</span>
    </button>
  );
}

// Shared app frame for the user workspace and the admin pages: one sidebar,
// one colour set, collapsing to a drawer on small screens.
export function Shell({ badge, actions, sections }: ShellProps) {
  const [open, setOpen] = useState(false);

  const sidebar = (
    <>
      <div className="flex h-14 shrink-0 items-center gap-2.5 border-b border-slate-800 px-5">
        <Logo />
        <span className="font-display text-xl text-slate-50">AegisGraph</span>
        {badge && (
          <span className="ml-auto rounded border border-blue-500/40 px-1.5 py-0.5 text-[11px] font-mono text-blue-400">
            {badge}
          </span>
        )}
        <button onClick={() => setOpen(false)} className="ml-auto p-1 text-slate-400 hover:text-slate-50 md:hidden" aria-label="Close menu">
          <X className="h-5 w-5" />
        </button>
      </div>

      {actions && <div className="px-3 pt-4">{actions}</div>}

      <nav className="flex flex-1 flex-col gap-6 overflow-y-auto px-3 py-4">
        {sections.map((section) => (
          <div key={section.title}>
            <div className="mb-2 px-3 text-xs font-mono text-slate-500">{section.title}</div>
            <div className="flex flex-col gap-0.5">
              {section.items.map((item) => (
                <NavLink
                  key={item.to}
                  to={item.to}
                  end={item.end}
                  onClick={() => setOpen(false)}
                  className={({ isActive }) =>
                    clsx(
                      'flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors',
                      isActive ? 'bg-blue-500/10 text-blue-400' : 'text-slate-400 hover:bg-slate-800 hover:text-slate-50',
                    )
                  }
                >
                  <item.icon className="h-4 w-4" />
                  {item.label}
                </NavLink>
              ))}
            </div>
          </div>
        ))}
      </nav>

      <div className="flex shrink-0 flex-col gap-1 border-t border-slate-800 p-3">
        <CopyUserId />
        <div className="flex items-center justify-between px-3 py-2">
          <UserButton appearance={{ elements: { userButtonAvatarBox: 'w-8 h-8' } }} />
          <Link to="/" className="flex items-center gap-1 text-xs font-mono text-slate-400 hover:text-slate-50">
            <ArrowLeft className="h-3 w-3" /> Exit
          </Link>
        </div>
      </div>
    </>
  );

  return (
    <div className="flex h-dvh w-full overflow-hidden bg-slate-950 font-sans text-slate-50">
      {/* Desktop sidebar */}
      <aside className="hidden w-60 shrink-0 flex-col border-r border-slate-800 bg-slate-900 md:flex">{sidebar}</aside>

      {/* Mobile drawer */}
      {open && (
        <div className="fixed inset-0 z-50 flex md:hidden">
          <aside className="flex w-64 flex-col border-r border-slate-800 bg-slate-900">{sidebar}</aside>
          <button className="flex-1 bg-black/60" onClick={() => setOpen(false)} aria-label="Close menu" />
        </div>
      )}

      <div className="flex min-w-0 flex-1 flex-col">
        <div className="flex h-12 shrink-0 items-center gap-3 border-b border-slate-800 bg-slate-900 px-4 md:hidden">
          <button onClick={() => setOpen(true)} className="p-1 text-slate-300" aria-label="Open menu">
            <Menu className="h-5 w-5" />
          </button>
          <span className="font-display">AegisGraph</span>
        </div>
        <main className="flex min-h-0 flex-1 flex-col overflow-hidden">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
